from collections import defaultdict, deque
from typing import Dict, Iterable, List, Set

import networkx as nx

from .graph import DeclarationRecord, SCCComponent


def combine_declaration_code(declarations: Iterable[DeclarationRecord]) -> str:
    chunks: List[str] = []
    for decl in declarations:
        code = (decl.code or "").strip()
        if not code:
            continue
        header = f"// Declaration: {decl.name} ({decl.kind})"
        chunks.append(f"{header}\n{code}")
    return "\n\n".join(chunks)


def build_declaration_context(
    *,
    kind: str | None = None,
    name: str | None = None,
    extra: str | None = None,
) -> str:
    parts: List[str] = []
    if kind:
        parts.append(f"kind: {kind}")
    if name:
        parts.append(f"name: {name}")
    if extra:
        parts.append(extra)
    return ", ".join(parts) if parts else "general declaration"


def map_component_dependencies(
    graph: nx.DiGraph,
    components: Iterable[SCCComponent],
) -> Dict[int, Set[int]]:
    node_to_component: Dict[str, int] = {}
    for component in components:
        for decl_id in component.declaration_ids:
            node_to_component[decl_id] = component.index

    dependencies: Dict[int, Set[int]] = defaultdict(set)
    for src, dst in graph.edges():
        src_comp = node_to_component.get(src)
        dst_comp = node_to_component.get(dst)
        if not (src_comp and dst_comp):
            continue
        if src_comp == dst_comp:
            continue
        dependencies[src_comp].add(dst_comp)
    return dependencies


def build_dependency_context(
    *,
    component_index: int,
    component_dependencies: Dict[int, Set[int]],
    translated_declarations: Dict[int, List[dict]],
    max_hops: int = 2,
    max_entries: int = 12,
) -> str:
    upstream = component_dependencies.get(component_index)
    if not upstream:
        return ""

    seen_components: Set[int] = set()
    seen_decls: Set[str] = set()
    seen_rust_blocks: Set[str] = set()
    lines: List[str] = []
    queue = deque([(idx, 1) for idx in sorted(upstream)])

    while queue and len(seen_decls) < max_entries:
        idx, depth = queue.popleft()
        if idx in seen_components or depth > max_hops:
            continue
        seen_components.add(idx)
        entries = translated_declarations.get(idx, [])
        if entries:
            for entry in entries:
                name = entry.get("name")
                if not name or name in seen_decls:
                    continue
                rust_code = (entry.get("rust_code") or "").strip()
                if rust_code and rust_code not in seen_rust_blocks:
                    lines.append(rust_code)
                    lines.append("")
                    seen_rust_blocks.add(rust_code)
                seen_decls.add(name)
                if len(seen_decls) >= max_entries:
                    break
        if depth < max_hops:
            for parent in sorted(component_dependencies.get(idx, set())):
                if parent not in seen_components:
                    queue.append((parent, depth + 1))

    if not lines:
        return ""
    return "\n".join(lines)
