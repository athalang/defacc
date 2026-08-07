from typing import Any, Optional, Protocol, Tuple

from guardian.compiler import RustCompiler

from .prompts import (
    build_refinement_prompt,
    build_rust_partial,
    build_translation_prompt,
    clean_llm_response,
    compose_rust_fragment,
)
from .results import CompilationResult


class Reporter(Protocol):
    def __call__(self, message: str = "") -> None:
        ...


def null_reporter(message: str = "") -> None:
    return None


class TranslationEngine:
    def __init__(
        self,
        lm: Any,
        compiler: Optional[RustCompiler] = None,
        max_refinement_iterations: int = 5,
    ) -> None:
        self.lm = lm
        self.compiler = compiler or RustCompiler()
        self.max_iterations = max_refinement_iterations

    def initial_translation(
        self,
        c_code: str,
        *,
        dependency_context: Optional[str] = None,
        reporter: Reporter = null_reporter,
    ) -> str:
        reporter("Step 1: Translating to Rust...")
        rust_result = self.lm(
            build_translation_prompt(
                c_code=c_code,
                rust_partial=build_rust_partial(dependency_context=dependency_context),
            )
        )
        reporter("  Initial translation complete\n")
        return clean_llm_response(rust_result)

    def compile_with_refinement(
        self,
        rust_code: str,
        *,
        dependency_context: Optional[str] = None,
        reporter: Reporter = null_reporter,
    ) -> Tuple[str, CompilationResult]:
        reporter("Step 2: Compiling and refining...")

        errors = ""
        compiled = False
        dependency_context = dependency_context or ""
        for iteration in range(self.max_iterations):
            compilable_code = compose_rust_fragment(dependency_context, rust_code)
            success, errors = self.compiler.compile(compilable_code)
            if success:
                compiled = True
                reporter(f"  ✓ Compilation successful after {iteration + 1} iteration(s)!\n")
                break

            reporter(f"  ✗ Compilation failed (iteration {iteration + 1}/{self.max_iterations})")
            reporter(f"    Errors: {errors[:200]}...")

            if iteration < self.max_iterations - 1:
                reporter("    Refining code...")
                rust_code = clean_llm_response(
                    self.lm(
                        build_refinement_prompt(
                            rust_code=rust_code,
                            dependency_context=dependency_context,
                            errors=errors,
                        )
                    )
                )
            else:
                reporter("    Max iterations reached.\n")

        result = CompilationResult(
            success=compiled,
            iterations=iteration + 1,
            errors=None if compiled else errors,
        )
        return rust_code, result
