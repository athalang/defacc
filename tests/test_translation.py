import unittest

from guardian.translation import (
    build_refinement_prompt,
    build_translation_prompt,
    clean_llm_response,
    compose_rust_fragment,
)


class TranslationHelperTests(unittest.TestCase):
    def test_clean_llm_response_strips_markdown_fences(self) -> None:
        self.assertEqual("fn main() {}", clean_llm_response("```rust\nfn main() {}\n```"))

    def test_compose_rust_fragment_handles_empty_dependencies(self) -> None:
        self.assertEqual("fn main() {}", compose_rust_fragment("", "fn main() {}"))

    def test_translation_prompt_is_minimal_completion_prompt(self) -> None:
        prompt = build_translation_prompt(
            c_code="int main(void) { return 0; }",
            rust_partial="",
        )

        self.assertIn("C code:\nint main(void) { return 0; }", prompt)
        self.assertTrue(prompt.endswith("Rust completion:"))

    def test_refinement_prompt_includes_combined_compile_context(self) -> None:
        prompt = build_refinement_prompt(
            rust_code="fn caller() -> i32 { callee() }",
            dependency_context="fn callee() -> i32 { 1 }",
            errors="cannot find function",
        )

        self.assertIn("Rust partial code:\nfn callee() -> i32 { 1 }", prompt)
        self.assertIn("Compiler errors:\ncannot find function", prompt)
        self.assertTrue(prompt.endswith("Fixed Rust completion:"))


if __name__ == "__main__":
    unittest.main()
