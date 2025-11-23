from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from clang.cindex import Cursor, CursorKind, TranslationUnit
import networkx as nx

from irene.clang_utils import (
    LibclangContext,
    cursor_in_files,
    cursor_kind_slug,
    extract_source,
    normalize_identifier,
    normalize_path,
    stable_cursor_id,
)
from irene.rule_analyzer import RuleHint


@dataclass
class DeclarationRecord:
    decl_id: str
    name: str
    kind: str
    path: str
    line: Optional[int]
    column: Optional[int]
    code: str
    rule_hints: List[RuleHint] = field(default_factory=list)
    aliases: Set[str] = field(default_factory=set)
    extra_locations: Set[Tuple[str, Optional[int], Optional[int]]] = field(default_factory=set)


@dataclass
class SCCComponent:
    index: int
    declaration_ids: List[str]
    declarations: List[DeclarationRecord]


@dataclass
class ProjectGraph:
    graph: nx.DiGraph
    declarations: Dict[str, DeclarationRecord]

    def components(self) -> List[SCCComponent]:
        order = dependency_order(self.graph)
        return [
            SCCComponent(
                index=idx,
                declaration_ids=list(component),
                declarations=[
                    self.declarations[node_id]
                    for node_id in component
                    if node_id in self.declarations
                ],
            )
            for idx, component in enumerate(order, start=1)
            if any(node_id in self.declarations for node_id in component)
        ]


class ProjectGraphBuilder:
    """Accumulate graph metadata across translation units."""

    def __init__(self) -> None:
        self.declarations: Dict[str, DeclarationRecord] = {}
        self.edges: Set[Tuple[str, str, str]] = set()

    def add_translation_unit(self, data: "TranslationUnitData") -> None:
        for record in data.records:
            existing = self.declarations.get(record.decl_id)
            if not existing:
                self.declarations[record.decl_id] = record
                continue
            self._merge_records(existing, record)
        self.edges.update(data.edges)

    def _merge_records(self, existing: DeclarationRecord, new_record: DeclarationRecord) -> None:
        if existing.name != new_record.name:
            existing.aliases.add(new_record.name)
        existing.extra_locations.update(new_record.extra_locations)
        self._merge_rule_hints(existing, new_record)

    @staticmethod
    def _merge_rule_hints(existing: DeclarationRecord, new_record: DeclarationRecord) -> None:
        seen = {
            (
                hint.category,
                hint.code_snippet,
                hint.suggested_rust,
                hint.explanation,
            )
            for hint in existing.rule_hints
        }
        for hint in new_record.rule_hints:
            key = (
                hint.category,
                hint.code_snippet,
                hint.suggested_rust,
                hint.explanation,
            )
            if key in seen:
                continue
            existing.rule_hints.append(hint)
            seen.add(key)

    def build(self) -> ProjectGraph:
        graph = nx.DiGraph()
        for decl_id, meta in self.declarations.items():
            graph.add_node(
                decl_id,
                name=meta.name,
                kind=meta.kind,
                path=meta.path,
                line=meta.line,
                column=meta.column,
            )
        for src, dst, reason in self.edges:
            graph.add_edge(src, dst, reason=reason)

        return ProjectGraph(graph=graph, declarations=self.declarations)


@dataclass
class TranslationUnitData:
    records: List[DeclarationRecord]
    edges: Set[Tuple[str, str, str]]


def collect_translation_unit_data(
    *,
    tu_graph: nx.DiGraph,
    definitions: Dict[str, Cursor],
    rule_hints: Iterable[RuleHint],
    c_code: str,
    normalized_source: str,
    normalized_source_set: Set[str],
    source_path: str,
) -> TranslationUnitData:
    """Extract declaration metadata and edges from a parsed translation unit."""
    records: List[DeclarationRecord] = []
    edges: Set[Tuple[str, str, str]] = set()
    hint_list = list(rule_hints)

    for name, cursor in definitions.items():
        func_id = stable_cursor_id(cursor, name, normalized_source)
        loc = tu_graph.nodes[name].get("location", {}) if name in tu_graph.nodes else {}
        record = DeclarationRecord(
            decl_id=func_id,
            name=name,
            kind=cursor_kind_slug(cursor.kind),
            path=source_path,
            line=loc.get("line"),
            column=loc.get("column"),
            code=extract_source(cursor, c_code, normalized_source_set),
            rule_hints=list(hint_list),
        )
        record.extra_locations.add((source_path, loc.get("line"), loc.get("column")))
        records.append(record)

    for source_name, target_name, data in tu_graph.edges(data=True):
        source_cursor = definitions.get(source_name)
        target_cursor = definitions.get(target_name)
        if not (source_cursor and target_cursor):
            continue
        source_id = stable_cursor_id(source_cursor, source_name, normalized_source)
        target_id = stable_cursor_id(target_cursor, target_name, normalized_source)
        edges.add((source_id, target_id, data.get("reason", "")))

    return TranslationUnitData(records=records, edges=edges)

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
    definitions: Dict[str, Cursor] = {}
    for child in translation_unit.cursor.get_children():
        if not (
            _is_in_target_file(child, target_files)
            and _is_relevant_definition(child)
            and child.spelling
        ):
            continue
        name = normalize_identifier(child.spelling)
        if name.startswith("("):  # skip clang's synthesized "(unnamed ...)" nodes
            continue
        definitions[name] = child
    return definitions

def build_dependency_graph(
    c_code: Optional[str],
    context: LibclangContext,
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
        translation_unit = context.parse_translation_unit(c_code)
    if target_files is None:
        target_files = {normalize_path(translation_unit.spelling)}
    graph = nx.DiGraph()

    definitions = _collect_definitions(translation_unit, target_files)

    for source_name, source_cursor in definitions.items():
        graph.add_node(
            source_name,
            kind=cursor_kind_slug(source_cursor.kind),
            location={"line": source_cursor.location.line, "column": source_cursor.location.column},
        )
        for node in context.walk_relevant_nodes(source_cursor):
            if node is source_cursor:
                continue

            target_name = ""
            reason = ""
            if node.kind == CursorKind.CALL_EXPR:
                target_name = normalize_identifier(context.get_called_function_name(node))
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
                "code": extract_source(cursor, c_code, target_files) if (cursor := definitions.get(name)) else "",
            }
            for name in component
        ]
        for component in dependency_order(graph)
    ]
