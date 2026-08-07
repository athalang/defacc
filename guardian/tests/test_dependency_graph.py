import unittest

import networkx as nx

from guardian.clang_utils import LibclangContext
from guardian.dependency_graph import SCCComponent, build_dependency_graph, dependency_order
from guardian.pipeline import GUARDIANPipeline
from guardian.project_scanner import build_source_graph


class DependencyGraphTests(unittest.TestCase):
    def test_build_dependency_graph_keeps_only_function_call_edges(self) -> None:
        c_code = """
        struct Node {
            struct Node *next;
        };

        typedef struct Node Node;

        int leaf(void) {
            return 1;
        }

        int caller(void) {
            Node node;
            node.next = 0;
            return leaf();
        }
        """
        graph, _ = build_dependency_graph(c_code, LibclangContext())

        edges = list(graph.edges(data=True))

        self.assertEqual([("caller", "leaf", "call")], [
            (src, dst, data.get("reason"))
            for src, dst, data in edges
        ])
        self.assertIn("Node", graph.nodes)
        self.assertEqual(0, graph.degree("Node"))

    def test_dependency_order_places_callees_before_callers(self) -> None:
        graph = nx.DiGraph()
        graph.add_edge("caller", "callee")
        graph.add_edge("entry", "caller")

        self.assertEqual([["callee"], ["caller"], ["entry"]], dependency_order(graph))

    def test_dependency_order_keeps_mutually_recursive_functions_together(self) -> None:
        graph = nx.DiGraph()
        graph.add_edge("is_even", "is_odd")
        graph.add_edge("is_odd", "is_even")
        graph.add_edge("main", "is_even")

        ordered_components = [set(component) for component in dependency_order(graph)]

        self.assertEqual({"is_even", "is_odd"}, ordered_components[0])
        self.assertEqual({"main"}, ordered_components[1])

    def test_build_source_graph_orders_single_file_sccs(self) -> None:
        c_code = """
        int leaf(void) { return 1; }
        int caller(void) { return leaf(); }
        """

        source_graph = build_source_graph(c_code)

        components = [
            [decl.name for decl in component.declarations]
            for component in source_graph.components()
        ]
        self.assertEqual([["leaf"], ["caller"]], components)

    def test_component_dependency_map_uses_callee_as_caller_dependency(self) -> None:
        graph = nx.DiGraph()
        graph.add_edge("caller-id", "callee-id")
        components = [
            SCCComponent(index=1, declaration_ids=["callee-id"], declarations=[]),
            SCCComponent(index=2, declaration_ids=["caller-id"], declarations=[]),
        ]

        dependencies = GUARDIANPipeline._map_component_dependencies(
            None,
            graph,
            components,
        )

        self.assertEqual({1}, dependencies[2])
        self.assertNotIn(1, dependencies)

    def test_dependency_context_includes_translated_rust_definitions(self) -> None:
        dependencies = {2: {1}}
        translated = {
            1: [
                {
                    "name": "callee",
                    "kind": "function",
                    "rust_code": "pub fn callee() -> i32 {\n    1\n}",
                }
            ]
        }

        context = GUARDIANPipeline._build_dependency_context(
            None,
            component_index=2,
            component_dependencies=dependencies,
            translated_declarations=translated,
        )

        self.assertIn("pub fn callee() -> i32", context)
        self.assertNotIn("Already translated dependencies", context)
        self.assertNotIn("callee (function)", context)

    def test_rust_partial_is_only_dependency_code(self) -> None:
        partial = GUARDIANPipeline._build_rust_partial(
            None,
            dependency_context="pub fn callee() -> i32 { 1 }",
        )

        self.assertEqual("pub fn callee() -> i32 { 1 }", partial)

    def test_compose_rust_fragment_appends_completion_after_dependencies(self) -> None:
        combined = GUARDIANPipeline._compose_rust_fragment(
            None,
            "pub fn callee() -> i32 { 1 }",
            "pub fn caller() -> i32 { callee() }",
        )

        self.assertEqual(
            "pub fn callee() -> i32 { 1 }\n\npub fn caller() -> i32 { callee() }",
            combined,
        )

    def test_translation_prompt_is_minimal_completion_prompt(self) -> None:
        prompt = GUARDIANPipeline._build_translation_prompt(
            None,
            c_code="int caller(void) { return callee(); }",
            rust_partial="pub fn callee() -> i32 { 1 }",
        )

        self.assertEqual(
            "Translate the following C code to Rust by completing the partial Rust code.\n\n"
            "C code:\nint caller(void) { return callee(); }\n\n"
            "Rust partial code:\npub fn callee() -> i32 { 1 }\n\n"
            "Rust completion:",
            prompt,
        )


if __name__ == "__main__":
    unittest.main()
