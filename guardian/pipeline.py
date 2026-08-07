from pathlib import Path
from typing import Any, Dict, List, Optional

from .analysis import (
    build_declaration_context,
    build_dependency_context,
    build_source_graph,
    combine_declaration_code,
    map_component_dependencies,
)
from .compiler import CCompiler, RustCompiler, check_c_compiler_available, check_rustc_available
from .translation import CompilationResult, Reporter, TranslationEngine, TranslationResult


class ConsoleReporter:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def __call__(self, message: str = "") -> None:
        if self.enabled:
            print(message)


class GUARDIANPipeline:
    def __init__(
        self,
        lm: Any,
        max_refinement_iterations: int = 5,
        reporter_factory: type[ConsoleReporter] = ConsoleReporter,
    ):
        self.max_iterations = max_refinement_iterations
        self.compiler = RustCompiler()
        self.c_compiler = CCompiler()
        self.lm = lm
        self.translation_engine = TranslationEngine(
            lm=lm,
            compiler=self.compiler,
            max_refinement_iterations=max_refinement_iterations,
        )
        self.reporter_factory = reporter_factory

        if not check_rustc_available():
            print("Warning: rustc not found. Compilation checks will be skipped.")
            print("Install Rust from: https://rustup.rs/")
        if not check_c_compiler_available():
            print("Warning: clang not found. Original C compilation checks will be skipped.")

    def translate(
        self,
        c_code: str,
        verbose: bool = True,
        declaration_context: Optional[str] = None,
        dependency_context: Optional[str] = None,
    ) -> TranslationResult:
        """
        Translate C code to Rust using the GUARDIAN framework.
        """
        reporter = self.reporter_factory(verbose)
        c_compilation = self._compile_c_source(c_code, reporter)
        declaration_context = declaration_context or build_declaration_context(
            kind="translation_unit",
            name="input",
        )
        rust_code = self.translation_engine.initial_translation(
            c_code,
            dependency_context=dependency_context,
            reporter=reporter,
        )
        final_code, compilation = self.translation_engine.compile_with_refinement(
            rust_code,
            dependency_context=dependency_context,
            reporter=reporter,
        )

        return TranslationResult(
            rust_code=final_code,
            compilation=compilation,
            c_compilation=c_compilation,
        )

    def translate_file(self, source_path: Path, verbose: bool = True) -> List[dict]:
        """Translate one C source file by iterating over SCCs in dependency order."""
        path = Path(source_path)
        return self.translate_source(
            path.read_text(errors="ignore"),
            source_filename=str(path),
            verbose=verbose,
        )

    def translate_source(
        self,
        c_code: str,
        *,
        source_filename: str = "input.c",
        verbose: bool = True,
    ) -> List[dict]:
        """Translate one C translation unit by iterating over SCCs in dependency order."""
        reporter = self.reporter_factory(verbose)
        source_graph = build_source_graph(c_code, source_filename=source_filename)
        components = source_graph.components()
        if not components:
            reporter("No strongly connected components found for translation.")
            return []

        component_dependencies = map_component_dependencies(source_graph.graph, components)
        translated_declarations: Dict[int, List[dict]] = {}
        results: List[dict] = []
        for component in components:
            decl_names = ", ".join(decl.name for decl in component.declarations)
            reporter("\n" + "=" * 60)
            reporter(f"Translating SCC {component.index}: {decl_names}")
            reporter("=" * 60)

            c_source = combine_declaration_code(component.declarations)
            if not c_source.strip():
                reporter("  Skipping SCC with no extractable code.")
                continue

            component_context = build_declaration_context(
                kind="scc",
                name=f"SCC {component.index}: {decl_names}",
            )
            dependency_context = build_dependency_context(
                component_index=component.index,
                component_dependencies=component_dependencies,
                translated_declarations=translated_declarations,
            )

            translation = self.translate(
                c_code=c_source,
                verbose=verbose,
                declaration_context=component_context,
                dependency_context=dependency_context or None,
            )

            results.append(
                {
                    "scc_index": component.index,
                    "declarations": [decl.name for decl in component.declarations],
                    "result": translation,
                }
            )
            translated_declarations[component.index] = [
                {"name": decl.name, "kind": decl.kind, "rust_code": translation.rust_code}
                for decl in component.declarations
            ]

        return results

    def _compile_c_source(self, c_code: str, reporter: Reporter) -> CompilationResult:
        reporter("Step 0: Compiling original C...")

        success, errors = self.c_compiler.compile(c_code)
        if success:
            reporter("  C compilation successful\n")
        else:
            reporter("  C compilation failed")
            reporter(f"    Errors: {errors[:200]}...\n")

        return CompilationResult(
            success=success,
            iterations=1,
            errors=None if success else errors,
        )
