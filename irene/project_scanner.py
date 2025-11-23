"""
Scan a C project using libclang and the dependency_graph helpers.

Usage:
    python -m irene.project_scanner --compile-commands build/compile_commands.json

The compile_commands.json file can be produced from a Make/Ninja build with
tools like bear or intercept-build:
    bear -- make -j
"""

import argparse
import json
import os
import shlex
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

from irene.clang_utils import LibclangContext, normalize_path, stable_cursor_id
from irene.dependency_graph import build_dependency_graph, dependency_order
from irene.rule_analyzer import StaticRuleAnalyzer


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


def _load_commands(db_path: Path) -> Iterable[Tuple[Path, Path, List[str]]]:
    """
    Yield (source_path, directory, compile_args) tuples from compile_commands.json.
    """
    entries = json.loads(db_path.read_text())
    for entry in entries:
        directory = Path(entry.get("directory") or db_path.parent).resolve()
        source_path = Path(entry["file"])
        if not source_path.is_absolute():
            source_path = (directory / source_path).resolve()

        raw_args = entry.get("arguments")
        if raw_args:
            args = list(raw_args)
        else:
            command = entry.get("command", "")
            if not command:
                continue
            args = shlex.split(command)

        if not args:
            continue

        # Drop the compiler executable; retain only flags.
        _, *rest = args
        cleaned_args = _strip_compile_artifacts(rest)
        if "-working-directory" not in cleaned_args:
            cleaned_args = ["-working-directory", str(directory), *cleaned_args]

        yield source_path, directory, cleaned_args


def scan_project(db_path: Path) -> None:
    """
    Iterate over translation units in a compilation database and print declarations.
    """
    decls: Dict[str, Dict[str, object]] = {}
    edges: Set[Tuple[str, str, str]] = set()  # (src_id, dst_id, reason)

    def _extract_source(cursor: Cursor, c_code: str, target_files: Set[str]) -> str:
        """Return the source text for a cursor extent within allowed files."""
        if not cursor or not cursor.extent:
            return ""

        start = cursor.extent.start
        end = cursor.extent.end

        if not (
            start.file
            and end.file
            and normalize_path(start.file.name) in target_files
            and normalize_path(end.file.name) in target_files
        ):
            return ""

        lines = c_code.splitlines()
        if start.line < 1 or end.line > len(lines):
            return ""

        slice_lines = lines[start.line - 1 : end.line]
        if not slice_lines:
            return ""

        slice_lines[0] = slice_lines[0][start.column - 1 :]
        slice_lines[-1] = slice_lines[-1][: end.column - 1]

        return "\n".join(slice_lines).strip("\n")

    for source_path, _, compile_args in _load_commands(db_path):
        if not source_path.exists():
            print(f"[skip] {source_path} does not exist on disk.")
            continue

        c_code = source_path.read_text(errors="ignore")
        clang = LibclangContext(
            clang_args=compile_args,
            source_filename=str(source_path),
        )
        analyzer = StaticRuleAnalyzer(
            clang_args=compile_args,
            source_filename=str(source_path),
        )

        try:
            translation_unit = clang.parse_translation_unit(c_code)
            graph, definitions = build_dependency_graph(
                c_code=c_code,
                parse_translation_unit=clang.parse_translation_unit,
                walk_relevant_nodes=clang.walk_relevant_nodes,
                get_called_function_name=clang.get_called_function_name,
                target_files={os.path.abspath(source_path)},
                translation_unit=translation_unit,
            )
        except Exception as exc:
            print(f"[error] Failed to parse {source_path}: {exc}")
            continue

        # Run rule analysis once per TU and reuse for all contained declarations.
        try:
            rule_hints = analyzer.analyze_translation_unit(translation_unit)
        except Exception as exc:
            print(f"[error] Failed to analyze rules in {source_path}: {exc}")
            rule_hints = []

        # Index declarations from this TU
        for name, cursor in definitions.items():
            func_id = stable_cursor_id(cursor, name, normalize_path(source_path))
            loc = graph.nodes[name].get("location", {}) if name in graph.nodes else {}
            entry = decls.setdefault(
                func_id,
                {
                    "name": name,
                    "kind": cursor.kind.spelling.lower().replace("_decl", ""),
                    "path": os.path.abspath(source_path),
                    "line": loc.get("line"),
                    "column": loc.get("column"),
                    "aliases": set(),
                    "extra_locations": set(),
                    "rule_hints": rule_hints,
                    "code": _extract_source(
                        cursor,
                        c_code,
                        {normalize_path(source_path)},
                    ),
                },
            )
            if entry["name"] != name:
                entry["aliases"].add(name)
            entry["extra_locations"].add(
                (os.path.abspath(source_path), loc.get("line"), loc.get("column"))
            )

        # Collect edges within this TU, mapping to stable ids
        for source_name, target_name, data in graph.edges(data=True):
            source_cursor = definitions.get(source_name)
            target_cursor = definitions.get(target_name)
            if not (source_cursor and target_cursor):
                continue
            source_id = stable_cursor_id(source_cursor, source_name, normalize_path(source_path))
            target_id = stable_cursor_id(target_cursor, target_name, normalize_path(source_path))
            edges.add((source_id, target_id, data.get("reason", "")))

    if not decls:
        print("No declarations found.")
        return

    # Build a merged graph using normalized ids
    import networkx as nx  # local import to keep dependencies minimal for users not running scanner

    g = nx.DiGraph()
    for decl_id, meta in decls.items():
        g.add_node(decl_id, **meta)
    for src, dst, reason in edges:
        g.add_edge(src, dst, reason=reason)

    print("Deduped declarations (by USR when available):\n")
    for decl_id, meta in sorted(decls.items(), key=lambda item: (item[1]["path"], item[1]["line"] or 0, item[1]["name"])):
        loc_str = f'{meta["path"]}:{meta["line"]}:{meta["column"]}' if meta["line"] else meta["path"]
        alias_str = f" (aliases: {', '.join(sorted(meta['aliases']))})" if meta["aliases"] else ""
        print(f"- [{meta['kind']}] {meta['name']} @ {loc_str}{alias_str}")

    print("\nStrongly connected components (cycle groups) in dependency order:\n")
    order = dependency_order(g)
    for idx, component in enumerate(order, start=1):
        names = [decls[node_id]["name"] if node_id in decls else node_id for node_id in component]
        print(f"SCC {idx}: {', '.join(names)}")

    print("\nEdges (deduped):\n")
    for src, dst, reason in sorted(edges):
        src_meta = decls.get(src, {})
        dst_meta = decls.get(dst, {})
        src_name = src_meta.get("name", src)
        dst_name = dst_meta.get("name", dst)
        label = f" [{reason}]" if reason else ""
        print(f"- {src_name} -> {dst_name}{label}")


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
    args = parser.parse_args()
    db_path = args.compile_commands
    if not db_path.exists():
        raise SystemExit(
            f"{db_path} not found. Generate it with `bear -- make` or `intercept-build make`."
        )

    scan_project(db_path)


if __name__ == "__main__":
    main()
