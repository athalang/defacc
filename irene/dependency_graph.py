from typing import Any, Callable, Dict, List, Tuple
from clang.cindex import Cursor, CursorKind, TranslationUnit
import networkx as nx

def _is_relevant_definition(node: Cursor) -> bool:
    return node.kind in {
        CursorKind.STRUCT_DECL,
        CursorKind.FUNCTION_DECL,
        CursorKind.ENUM_DECL,
        CursorKind.TYPEDEF_DECL,
    } and node.is_definition()

def _normalize_identifier(name: str) -> str:
    for prefix in ("struct ", "enum ", "union ", "class ", "typedef "):
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name

def _collect_definitions(translation_unit: TranslationUnit) -> Dict[str, Cursor]:
    """Collect top-level definitions from the translation unit."""
    return {
        _normalize_identifier(child.spelling): child
        for child in translation_unit.cursor.get_children()
        if child.location
        and child.location.file
        and child.location.file.name == "input.c"
        and _is_relevant_definition(child)
        and child.spelling  # Skip anonymous declarations
    }

def _extract_source(cursor: Cursor, c_code: str) -> str:
    """Return the source text for a cursor extent within input.c."""
    if not cursor or not cursor.extent:
        return ""

    start = cursor.extent.start
    end = cursor.extent.end

    if not (start.file and start.file.name == "input.c"):
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
    c_code: str,
    parse_translation_unit: Callable[[str], TranslationUnit],
    walk_relevant_nodes: Callable[[Cursor], List[Cursor]],
    get_called_function_name: Callable[[Cursor], str],
) -> Tuple[nx.DiGraph, Dict[str, Cursor]]:
    """
    Create a dependency graph between structs, enums, typedefs, and functions.

    Nodes are labelled with a "kind" attribute (struct, enum, typedef, function).
    Edges indicate that the source depends on the target via either a function call
    or a type reference.
    """
    translation_unit = parse_translation_unit(c_code)
    graph = nx.DiGraph()

    definitions = _collect_definitions(translation_unit)

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
                target_name = _normalize_identifier(get_called_function_name(node))
                reason = "call"
            elif node.kind == CursorKind.TYPE_REF:
                target_name = _normalize_identifier(node.spelling or node.type.spelling)
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
    graph: nx.DiGraph, definitions: Dict[str, Cursor], c_code: str
) -> List[List[Dict[str, Any]]]:
    """
    Return code snippets grouped by strongly connected component in
    condensation (dependency) order.

    Each inner list corresponds to one SCC and contains entries with:
    name, kind, code, and location.
    """
    return [
        [
            {
                "name": name,
                "kind": graph.nodes[name].get("kind", ""),
                "location": graph.nodes[name].get("location", {}),
                "code": _extract_source(cursor, c_code) if (cursor := definitions.get(name)) else "",
            }
            for name in component
        ]
        for component in dependency_order(graph)
    ]
