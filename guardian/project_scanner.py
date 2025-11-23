"""
Scan a C project using libclang and the dependency_graph helpers.

Usage:
    python -m guardian.project_scanner --compile-commands build/compile_commands.json

The compile_commands.json file can be produced from a Make/Ninja build with
tools like bear, intercept-build, or compiledb:
    bear -- make -j
    intercept-build make -j
    compiledb -n make
"""

import argparse
import json
import shlex
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from guardian.clang_utils import LibclangContext, normalize_path
from guardian.dependency_graph import (
    ProjectGraph,
    ProjectGraphBuilder,
    SCCComponent,
    TranslationUnitData,
    build_dependency_graph,
    collect_translation_unit_data,
)
from guardian.rule_analyzer import StaticRuleAnalyzer


@dataclass
class CompileCommand:
    source_path: Path
    directory: Path
    args: List[str]

    @classmethod
    def from_entry(cls, entry: Dict[str, Any], db_path: Path) -> Optional["CompileCommand"]:
        directory = Path(entry.get("directory") or db_path.parent).resolve()
        file_field = entry.get("file")
        if not file_field:
            return None
        source_path = Path(file_field)
        if not source_path.is_absolute():
            source_path = (directory / source_path).resolve()

        raw_args = entry.get("arguments")
        if raw_args:
            args = list(raw_args)
        else:
            command = entry.get("command", "")
            if not command:
                return None
            args = shlex.split(command)

        if not args:
            return None

        _, *rest = args
        cleaned_args = _strip_compile_artifacts(rest)
        cleaned_args = _drop_source_file_arg(cleaned_args, source_path, directory)
        if "-working-directory" not in cleaned_args:
            cleaned_args = ["-working-directory", str(directory), *cleaned_args]

        return cls(source_path=source_path, directory=directory, args=cleaned_args)


def _strip_compile_artifacts(args: List[str]) -> List[str]:
    """Remove compiler invocation and output flags (-c, -o) from arguments."""
    cleaned: List[str] = []
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg == "-c":
            continue
        if arg == "-o":
            skip_next = True
            continue
        if arg.startswith("-o"):
            continue
        cleaned.append(arg)
    return cleaned


def _drop_source_file_arg(args: List[str], source_path: Path, directory: Path) -> List[str]:
    """
    Remove standalone positional arguments that point to the translation unit file.
    """
    normalized_source = normalize_path(source_path)
    cleaned: List[str] = []
    for arg in args:
        if arg.startswith("-"):
            cleaned.append(arg)
            continue
        candidate = Path(arg)
        if not candidate.is_absolute():
            candidate = (directory / candidate).resolve()
        try:
            candidate_str = normalize_path(candidate)
        except Exception:
            candidate_str = arg
        if candidate_str == normalized_source:
            continue
        cleaned.append(arg)
    return cleaned


def _read_compile_commands(db_path: Path) -> List[CompileCommand]:
    """Load compile commands from compile_commands.json with basic validation."""
    if not db_path.exists():
        raise FileNotFoundError(f"{db_path} not found.")

    try:
        entries = json.loads(db_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse {db_path}: {exc}") from exc

    commands: List[CompileCommand] = []
    for entry in entries:
        command = CompileCommand.from_entry(entry, db_path)
        if command:
            commands.append(command)
    return commands


ContextEntry = Tuple[LibclangContext, StaticRuleAnalyzer]


def _resolve_context(
    source_path: str,
    compile_args: Iterable[str],
    cache: Optional[Dict[Tuple[str, Tuple[str, ...]], ContextEntry]] = None,
) -> ContextEntry:
    """Return a LibclangContext and StaticRuleAnalyzer, caching when possible."""
    args_tuple = tuple(compile_args)
    key = (source_path, args_tuple)
    if cache is not None:
        cached = cache.get(key)
        if cached:
            return cached

    clang = LibclangContext(
        clang_args=list(args_tuple),
        source_filename=source_path,
    )
    analyzer = StaticRuleAnalyzer(clang=clang)
    if cache is not None:
        cache[key] = (clang, analyzer)
    return clang, analyzer


def _process_command(
    command: CompileCommand,
    *,
    context_cache: Optional[Dict[Tuple[str, Tuple[str, ...]], ContextEntry]] = None,
    enable_cache: bool = True,
) -> Optional[TranslationUnitData]:
    source_path = command.source_path
    compile_args = command.args
    if not source_path.exists():
        print(f"[skip] {source_path} does not exist on disk.")
        return None

    source_str = str(source_path)
    normalized_source = normalize_path(source_str)
    normalized_source_set = {normalized_source}
    try:
        c_code = source_path.read_text(errors="ignore")
    except OSError as exc:
        print(f"[error] Failed to read {source_path}: {exc}")
        return None

    cache_ref = context_cache if enable_cache else None
    clang, analyzer = _resolve_context(source_str, compile_args, cache_ref)

    try:
        translation_unit = clang.parse_translation_unit(c_code)
        tu_graph, definitions = build_dependency_graph(
            c_code=c_code,
            context=clang,
            target_files={normalized_source},
            translation_unit=translation_unit,
        )
    except Exception as exc:
        print(f"[error] Failed to parse {source_path}: {exc}")
        return None

    try:
        rule_hints = analyzer.analyze_translation_unit(translation_unit)
    except Exception as exc:
        print(f"[error] Failed to analyze rules in {source_path}: {exc}")
        rule_hints = []

    return collect_translation_unit_data(
        tu_graph=tu_graph,
        definitions=definitions,
        rule_hints=rule_hints,
        c_code=c_code,
        normalized_source=normalized_source,
        normalized_source_set=normalized_source_set,
        source_path=source_str,
    )


def build_project_graph(db_path: Path, *, max_workers: int = 1) -> ProjectGraph:
    """Return a merged dependency graph and declaration metadata for a project."""
    commands = _read_compile_commands(db_path)
    builder = ProjectGraphBuilder()
    cache: Optional[Dict[Tuple[str, Tuple[str, ...]], ContextEntry]] = {}

    if max_workers > 1:
        # Libclang contexts are not thread-safe, so disable caching when parallelising.
        cache = None
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    _process_command,
                    command,
                    context_cache=None,
                    enable_cache=False,
                )
                for command in commands
            ]
            for future in futures:
                result = future.result()
                if result:
                    builder.add_translation_unit(result)
    else:
        for command in commands:
            result = _process_command(
                command,
                context_cache=cache,
                enable_cache=True,
            )
            if result:
                builder.add_translation_unit(result)

    return builder.build()


def iter_scc_components(
    db_path: Path,
    *,
    project_graph: Optional[ProjectGraph] = None,
    max_workers: int = 1,
) -> List[SCCComponent]:
    """Return SCC components with declaration metadata for project orchestration."""
    graph = project_graph or build_project_graph(db_path, max_workers=max_workers)
    return graph.components()


def format_project_report(project_graph: ProjectGraph) -> str:
    if not project_graph.declarations:
        return "No declarations found."

    lines: List[str] = []
    lines.append("Deduped declarations (by USR when available):\n")
    for meta in sorted(
        project_graph.declarations.values(),
        key=lambda item: (item.path, item.line or 0, item.name),
    ):
        loc_str = f"{meta.path}:{meta.line}:{meta.column}" if meta.line else meta.path
        alias_str = f" (aliases: {', '.join(sorted(meta.aliases))})" if meta.aliases else ""
        lines.append(f"- [{meta.kind}] {meta.name} @ {loc_str}{alias_str}")

    lines.append("\nStrongly connected components (cycle groups) in dependency order:\n")
    for component in project_graph.components():
        names = [decl.name for decl in component.declarations]
        lines.append(f"SCC {component.index}: {', '.join(names)}")

    lines.append("\nEdges (deduped):\n")
    for src, dst, data in sorted(project_graph.graph.edges(data=True)):
        src_meta = project_graph.declarations.get(src)
        dst_meta = project_graph.declarations.get(dst)
        src_name = src_meta.name if src_meta else src
        dst_name = dst_meta.name if dst_meta else dst
        reason = data.get("reason", "")
        label = f" [{reason}]" if reason else ""
        lines.append(f"- {src_name} -> {dst_name}{label}")

    return "\n".join(lines)


def scan_project(
    db_path: Path,
    *,
    project_graph: Optional[ProjectGraph] = None,
    max_workers: int = 1,
) -> ProjectGraph:
    """Iterate over translation units in a project and print dependency metadata."""
    graph = project_graph or build_project_graph(db_path, max_workers=max_workers)
    print(format_project_report(graph))
    return graph


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Iterate over declarations in a C project using compile_commands.json"
    )
    parser.add_argument(
        "--compile-commands",
        "-c",
        type=Path,
        default=Path("compile_commands.json"),
        help="Path to compile_commands.json (generate with bear or intercept-build)",
    )
    parser.add_argument(
        "--jobs",
        "-j",
        type=int,
        default=1,
        help="Number of translation units to process in parallel",
    )
    args = parser.parse_args()
    db_path = args.compile_commands
    if not db_path.exists():
        raise SystemExit(
            f"{db_path} not found."
        )

    scan_project(db_path, max_workers=max(1, args.jobs))


if __name__ == "__main__":
    main()
