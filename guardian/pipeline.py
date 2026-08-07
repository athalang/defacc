from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import networkx as nx

from .compiler import CCompiler, RustCompiler, check_c_compiler_available, check_rustc_available
from .dependency_graph import DeclarationRecord, SCCComponent
from .project_scanner import build_source_graph

@dataclass
class CompilationResult:
    success: bool
    iterations: int
    errors: Optional[str]


@dataclass
class TranslationResult:
    rust_code: str
    compilation: CompilationResult
    c_compilation: Optional[CompilationResult] = None


class GUARDIANPipeline:
    def __init__(
        self,
        lm: Any,
        max_refinement_iterations: int = 5,
    ):
        self.max_iterations = max_refinement_iterations

        self.compiler = RustCompiler()
        self.c_compiler = CCompiler()

        # Store LM instance (caller should pass a prompt -> completion callable)
        self.lm = lm

        # Check if rustc is available
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

        Args:
            c_code: The C source code to translate
            verbose: Print progress information
            dependency_context: Optional Rust definitions for upstream declarations that already exist

        Returns:
            Dictionary containing:
                - rust_code: The final Rust code
                - compiled: Whether the code compiled successfully
                - c_compilation: Whether the original C compiled successfully
                - iterations: Number of refinement iterations used
                - errors: Final error messages (if any)
        """
        c_compilation = self._compile_c_source(c_code, verbose)
        root_context = declaration_context or self._build_context(kind="translation_unit", name="input")
        rust_code = self._initial_translation(
            c_code,
            verbose,
            declaration_context=root_context,
            dependency_context=dependency_context,
        )
        final_code, compilation = self._compile_with_refinement(
            rust_code,
            verbose,
            dependency_context=dependency_context,
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
        source_graph = build_source_graph(c_code, source_filename=source_filename)
        components = source_graph.components()
        if not components:
            if verbose:
                print("No strongly connected components found for translation.")
            return []

        component_dependencies = self._map_component_dependencies(source_graph.graph, components)
        translated_declarations: Dict[int, List[dict]] = {}
        results: List[dict] = []
        for component in components:
            decl_names = ", ".join(decl.name for decl in component.declarations)
            if verbose:
                print("\n" + "=" * 60)
                print(f"Translating SCC {component.index}: {decl_names}")
                print("=" * 60)

            c_source = self._combine_declaration_code(component.declarations)
            if not c_source.strip():
                if verbose:
                    print("  Skipping SCC with no extractable code.")
                continue

            component_context = self._build_context(
                kind="scc",
                name=f"SCC {component.index}: {decl_names}",
            )
            dependency_context = self._build_dependency_context(
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

    def _initial_translation(
        self,
        c_code: str,
        verbose: bool,
        declaration_context: Optional[str] = None,
        dependency_context: Optional[str] = None,
    ) -> str:
        if verbose:
            print("Step 1: Translating to Rust...")
        rust_result = self.lm(
            self._build_translation_prompt(
                c_code=c_code,
                rust_partial=self._build_rust_partial(dependency_context=dependency_context),
            )
        )
        if verbose:
            print("  Initial translation complete\n")
        return self._clean_llm_response(rust_result)

    def _build_translation_prompt(self, *, c_code: str, rust_partial: str) -> str:
        return (
            "Translate the following C code to Rust by completing the partial Rust code.\n\n"
            f"C code:\n{c_code.strip()}\n\n"
            f"Rust partial code:\n{rust_partial.strip()}\n\n"
            "Rust completion:"
        )

    def _clean_llm_response(self, response: Any) -> str:
        if isinstance(response, list):
            response = response[0] if response else ""
        text = str(response).strip()
        if text.startswith("```rust"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def _build_refinement_prompt(
        self,
        *,
        rust_code: str,
        dependency_context: str,
        errors: str,
    ) -> str:
        return (
            "Fix the Rust completion so the combined Rust code compiles.\n\n"
            f"Rust partial code:\n{dependency_context.strip()}\n\n"
            f"Rust completion:\n{rust_code.strip()}\n\n"
            f"Compiler errors:\n{errors.strip()}\n\n"
            "Fixed Rust completion:"
        )

    def _compile_c_source(self, c_code: str, verbose: bool) -> CompilationResult:
        if verbose:
            print("Step 0: Compiling original C...")

        success, errors = self.c_compiler.compile(c_code)
        if verbose:
            if success:
                print("  C compilation successful\n")
            else:
                print("  C compilation failed")
                print(f"    Errors: {errors[:200]}...\n")

        return CompilationResult(
            success=success,
            iterations=1,
            errors=None if success else errors,
        )

    def _compile_with_refinement(
        self,
        rust_code: str,
        verbose: bool,
        dependency_context: Optional[str] = None,
    ) -> Tuple[str, CompilationResult]:
        if verbose:
            print("Step 2: Compiling and refining...")

        errors = ""
        compiled = False
        dependency_context = dependency_context or ""
        for iteration in range(self.max_iterations):
            compilable_code = self._compose_rust_fragment(dependency_context, rust_code)
            success, errors = self.compiler.compile(compilable_code)
            if success:
                compiled = True
                if verbose:
                    print(f"  ✓ Compilation successful after {iteration + 1} iteration(s)!\n")
                break

            if verbose:
                print(f"  ✗ Compilation failed (iteration {iteration + 1}/{self.max_iterations})")
                print(f"    Errors: {errors[:200]}...")

            if iteration < self.max_iterations - 1:
                if verbose:
                    print("    Refining code...")
                rust_code = self._clean_llm_response(
                    self.lm(
                        self._build_refinement_prompt(
                            rust_code=rust_code,
                            dependency_context=dependency_context,
                            errors=errors,
                        )
                    )
                )
            else:
                if verbose:
                    print("    Max iterations reached.\n")

        result = CompilationResult(
            success=compiled,
            iterations=iteration + 1,
            errors=None if compiled else errors,
        )
        return rust_code, result

    def _build_rust_partial(
        self,
        *,
        dependency_context: Optional[str],
    ) -> str:
        return (dependency_context or "").strip()

    def _compose_rust_fragment(self, dependency_context: str, rust_code: str) -> str:
        dependency_context = (dependency_context or "").strip()
        rust_code = (rust_code or "").strip()
        if dependency_context and rust_code:
            return f"{dependency_context}\n\n{rust_code}"
        return dependency_context or rust_code

    def _combine_declaration_code(self, declarations: Iterable[DeclarationRecord]) -> str:
        chunks: List[str] = []
        for decl in declarations:
            code = (decl.code or "").strip()
            if not code:
                continue
            header = f"// Declaration: {decl.name} ({decl.kind})"
            chunks.append(f"{header}\n{code}")
        return "\n\n".join(chunks)

    def _build_context(
        self,
        *,
        kind: Optional[str] = None,
        name: Optional[str] = None,
        extra: Optional[str] = None,
    ) -> str:
        parts: List[str] = []
        if kind:
            parts.append(f"kind: {kind}")
        if name:
            parts.append(f"name: {name}")
        if extra:
            parts.append(extra)
        return ", ".join(parts) if parts else "general declaration"

    def _map_component_dependencies(
        self,
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

    def _build_dependency_context(
        self,
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
