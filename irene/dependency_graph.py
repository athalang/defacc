from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from clang.cindex import Cursor, CursorKind, TranslationUnit
import networkx as nx

from irene.clang_utils import normalize_identifier, normalize_path, cursor_in_files

def _is_relevant_definition(node: Cursor) -> bool:
    return node.kind in {
        CursorKind.STRUCT_DECL,
        CursorKind.FUNCTION_DECL,
        CursorKind.ENUM_DECL,
        CursorKind.TYPEDEF_DECL,
    } and node.is_definition()

def _is_in_target_file(cursor: Cursor, target_files: Set[str]) -> bool:
    return cursor_in_files(cursor, target_files)

def _collect_definitions(
    translation_unit: TranslationUnit, target_files: Set[str]
) -> Dict[str, Cursor]:
    """Collect top-level definitions from the translation unit for allowed files."""
    return {
        normalize_identifier(child.spelling): child
        for child in translation_unit.cursor.get_children()
        if _is_in_target_file(child, target_files)
        and _is_relevant_definition(child)
        and child.spelling  # Skip anonymous declarations
    }

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

def build_dependency_graph(
    c_code: Optional[str],
    parse_translation_unit: Callable[[str], TranslationUnit],
    walk_relevant_nodes: Callable[[Cursor], List[Cursor]],
    get_called_function_name: Callable[[Cursor], str],
    target_files: Optional[Set[str]] = None,
    translation_unit: Optional[TranslationUnit] = None,
) -> Tuple[nx.DiGraph, Dict[str, Cursor]]:
    """
    Create a dependency graph between structs, enums, typedefs, and functions.

    Nodes are labelled with a "kind" attribute (struct, enum, typedef, function).
    Edges indicate that the source depends on the target via either a function call
    or a type reference.
    """
    if translation_unit is None:
        if c_code is None:
            raise ValueError("c_code is required when translation_unit is not provided")
        translation_unit = parse_translation_unit(c_code)
    if target_files is None:
        target_files = {normalize_path(translation_unit.spelling)}
    graph = nx.DiGraph()

    definitions = _collect_definitions(translation_unit, target_files)

    for source_name, source_cursor in definitions.items():
        graph.add_node(
            source_name,
            kind=source_cursor.kind.spelling.lower().replace("_decl", ""),
            location={"line": source_cursor.location.line, "column": source_cursor.location.column},
        )
        for node in walk_relevant_nodes(source_cursor):
            if node is source_cursor:
                continue

            target_name = ""
            reason = ""
            if node.kind == CursorKind.CALL_EXPR:
                target_name = normalize_identifier(get_called_function_name(node))
                reason = "call"
            elif node.kind == CursorKind.TYPE_REF:
                target_name = normalize_identifier(node.spelling or node.type.spelling)
                if target_name == source_name:
                    continue
                reason = "type"
            else:
                continue

            if target_name and target_name in definitions:
                graph.add_edge(source_name, target_name, reason=reason)

    return graph, definitions

def dependency_order(graph: nx.DiGraph) -> List[List[str]]:
    """
    Return the condensation graph's component order (SCCs) as groups.

    Each item in the returned list is a list of node names belonging to a
    strongly connected component. Components are topologically sorted by
    dependency; member order is left as provided by NetworkX.
    """
    condensation = nx.condensation(graph)
    return [
        list(condensation.nodes[comp]["members"])
        for comp in nx.topological_sort(condensation)
    ]

def scc_snippets_with_code(
    graph: nx.DiGraph,
    definitions: Dict[str, Cursor],
    c_code: str,
    target_files: Optional[Set[str]] = None,
) -> List[List[Dict[str, Any]]]:
    """
    Return code snippets grouped by strongly connected component in
    condensation (dependency) order.

    Each inner list corresponds to one SCC and contains entries with:
    name, kind, code, and location.
    """
    if target_files is None:
        target_files = {
            normalize_path(cursor.location.file.name)
            for cursor in definitions.values()
            if cursor.location and cursor.location.file
        }

    return [
        [
            {
                "name": name,
                "kind": graph.nodes[name].get("kind", ""),
                "location": graph.nodes[name].get("location", {}),
                "code": _extract_source(cursor, c_code, target_files) if (cursor := definitions.get(name)) else "",
            }
            for name in component
        ]
        for component in dependency_order(graph)
    ]
