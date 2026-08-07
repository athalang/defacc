"""
Build dependency metadata for a single C source file.
"""

from pathlib import Path
from typing import List, Optional

from guardian.clang_utils import LibclangContext, normalize_path
from guardian.dependency_graph import (
    ProjectGraph,
    ProjectGraphBuilder,
    build_dependency_graph,
    collect_translation_unit_data,
)


def build_source_graph(
    c_code: str,
    *,
    source_filename: str = "input.c",
    clang_args: Optional[List[str]] = None,
) -> ProjectGraph:
    """Return declaration metadata and SCC ordering for one C translation unit."""
    source_path = normalize_path(source_filename)
    clang = LibclangContext(
        clang_args=clang_args,
        source_filename=source_filename,
    )
    translation_unit = clang.parse_translation_unit(c_code)
    tu_graph, definitions = build_dependency_graph(
        c_code=c_code,
        context=clang,
        target_files={source_path},
        translation_unit=translation_unit,
    )
    data = collect_translation_unit_data(
        tu_graph=tu_graph,
        definitions=definitions,
        c_code=c_code,
        normalized_source=source_path,
        normalized_source_set={source_path},
        source_path=source_filename,
    )

    builder = ProjectGraphBuilder()
    builder.add_translation_unit(data)
    return builder.build()


def build_file_graph(
    source_path: Path,
    *,
    clang_args: Optional[List[str]] = None,
) -> ProjectGraph:
    """Read one C source file and return its declaration dependency graph."""
    path = Path(source_path)
    return build_source_graph(
        path.read_text(errors="ignore"),
        source_filename=str(path),
        clang_args=clang_args,
    )


def format_source_report(source_graph: ProjectGraph) -> str:
    if not source_graph.declarations:
        return "No declarations found."

    lines: List[str] = []
    lines.append("Declarations:\n")
    for meta in sorted(
        source_graph.declarations.values(),
        key=lambda item: (item.path, item.line or 0, item.name),
    ):
        loc_str = f"{meta.path}:{meta.line}:{meta.column}" if meta.line else meta.path
        lines.append(f"- [{meta.kind}] {meta.name} @ {loc_str}")

    lines.append("\nStrongly connected components in dependency order:\n")
    for component in source_graph.components():
        names = [decl.name for decl in component.declarations]
        lines.append(f"SCC {component.index}: {', '.join(names)}")

    lines.append("\nEdges:\n")
    for src, dst, data in sorted(source_graph.graph.edges(data=True)):
        src_meta = source_graph.declarations.get(src)
        dst_meta = source_graph.declarations.get(dst)
        src_name = src_meta.name if src_meta else src
        dst_name = dst_meta.name if dst_meta else dst
        reason = data.get("reason", "")
        label = f" [{reason}]" if reason else ""
        lines.append(f"- {src_name} -> {dst_name}{label}")

    return "\n".join(lines)
