from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import dspy
import networkx as nx

from .compiler import RustCompiler, check_rustc_available
from .dspy_modules import GUARDIANModules
from .dependency_graph import DeclarationRecord, SCCComponent
from .project_scanner import build_project_graph

@dataclass
class CompilationResult:
    success: bool
    iterations: int
    errors: Optional[str]


@dataclass
class TranslationArtifacts:
    summary_text: str
    raw_summary: Optional[object] = None


@dataclass
class TranslationResult:
    rust_code: str
    compilation: CompilationResult
    artifacts: TranslationArtifacts


class GUARDIANPipeline:
    def __init__(
        self,
        lm: dspy.LM,
        max_refinement_iterations: int = 5,
    ):
        self.max_iterations = max_refinement_iterations

        self.compiler = RustCompiler()

        # Store LM instance (caller should configure DSPy before creating pipeline)
        self.lm = lm

        # Initialize DSPy modules
        self.modules = GUARDIANModules()

        # Check if rustc is available
        if not check_rustc_available():
            print("Warning: rustc not found. Compilation checks will be skipped.")
            print("Install Rust from: https://rustup.rs/")

    def translate(
        self,
        c_code: str,
        verbose: bool = True,
        summary_override: Optional[str] = None,
        declaration_context: Optional[str] = None,
        dependency_context: Optional[str] = None,
    ) -> TranslationResult:
        """
        Translate C code to Rust using the GUARDIAN framework.

        Args:
            c_code: The C source code to translate
            verbose: Print progress information
            summary_override: Optional plain-text summary to feed directly to the translator
            dependency_context: Optional summaries of upstream declarations that already exist

        Returns:
            Dictionary containing:
                - rust_code: The final Rust code
                - compiled: Whether the code compiled successfully
                - iterations: Number of refinement iterations used
                - errors: Final error messages (if any)
                - summary: Either the summarizer output or the provided summary text
        """
        root_context = declaration_context or self._build_context(kind="translation_unit", name="input")
        summary_obj, summary_payload = self._summarize_code(
            c_code,
            summary_override=summary_override,
            verbose=verbose,
            declaration_context=root_context,
        )
        rust_code = self._initial_translation(
            c_code,
            summary_payload,
            verbose,
            declaration_context=root_context,
            dependency_context=dependency_context,
        )
        final_code, compilation = self._compile_with_refinement(rust_code, verbose)

        artifacts = TranslationArtifacts(
            summary_text=summary_payload or "",
            raw_summary=summary_obj,
        )

        return TranslationResult(rust_code=final_code, compilation=compilation, artifacts=artifacts)

    def translate_project(self, compile_commands: Path, verbose: bool = True) -> List[dict]:
        """Translate an entire project by iterating over SCCs from the project scanner."""
        db_path = Path(compile_commands)
        project_graph = build_project_graph(db_path)
        components = project_graph.components()
        if not components:
            if verbose:
                print("No strongly connected components found for translation.")
            return []

        component_dependencies = self._map_component_dependencies(project_graph.graph, components)
        component_summaries: Dict[int, List[dict]] = {}
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

            declaration_summaries = self._summaries_for_declarations(component.declarations, verbose=verbose)
            summary_text = self._format_declaration_summaries(declaration_summaries)
            component_context = self._build_context(
                kind="scc",
                name=f"SCC {component.index}: {decl_names}",
            )
            dependency_context = self._build_dependency_context(
                component_index=component.index,
                component_dependencies=component_dependencies,
                component_summaries=component_summaries,
            )

            translation = self.translate(
                c_code=c_source,
                verbose=verbose,
                summary_override=summary_text or None,
                declaration_context=component_context,
                dependency_context=dependency_context or None,
            )

            results.append(
                {
                    "scc_index": component.index,
                    "declarations": [decl.name for decl in component.declarations],
                    "summaries": declaration_summaries,
                    "result": translation,
                }
            )
            component_summaries[component.index] = declaration_summaries

        return results

    def _format_summary(self, summary) -> str:
        return f"""
Code Summary:
- Parameters: {summary.arguments}
- Returns: {summary.outputs}
- Functionality: {summary.function}
"""

    def _summarize_code(
        self,
        c_code: str,
        *,
        declaration_context: Optional[str] = None,
        summary_override: Optional[str],
        verbose: bool,
    ) -> Tuple[Optional[object], str]:
        summary_payload = summary_override
        summary_obj = None
        if summary_override is None:
            if verbose:
                print("Step 1: Summarizing C code structure...")
            summary_obj = self.modules.summarizer(
                c_code=c_code,
                declaration_context=declaration_context or "",
            )
            summary_payload = self._format_summary(summary_obj)
            if verbose and summary_obj:
                print(f"  Params: {summary_obj.arguments}")
                print(f"  Returns: {summary_obj.outputs}")
                print(f"  Function: {summary_obj.function}\n")
        else:
            if verbose:
                print("Step 1: Using provided summary.\n")
        return summary_obj, summary_payload or ""

    def _initial_translation(
        self,
        c_code: str,
        summary_payload: str,
        verbose: bool,
        declaration_context: Optional[str] = None,
        dependency_context: Optional[str] = None,
    ) -> str:
        if verbose:
            print("Step 2: Translating to Rust...")
        rust_result = self.modules.translator(
            c_code=c_code,
            summary=summary_payload,
            declaration_context=declaration_context or "",
            dependency_context=dependency_context or "",
        )
        if verbose:
            print("  Initial translation complete\n")
        return rust_result.rust_code

    def _compile_with_refinement(self, rust_code: str, verbose: bool) -> Tuple[str, CompilationResult]:
        if verbose:
            print("Step 3: Compiling and refining...")

        errors = ""
        compiled = False
        for iteration in range(self.max_iterations):
            success, errors = self.compiler.compile(rust_code)
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
                refined = self.modules.refiner(rust_code=rust_code, errors=errors)
                rust_code = refined.fixed_code
            else:
                if verbose:
                    print("    Max iterations reached.\n")

        result = CompilationResult(
            success=compiled,
            iterations=iteration + 1,
            errors=None if compiled else errors,
        )
        return rust_code, result

    def _summaries_for_declarations(
        self, declarations: Iterable[DeclarationRecord], verbose: bool = True
    ) -> List[dict]:
        entries: List[dict] = []
        for decl in declarations:
            code = (decl.code or "").strip()
            if not code:
                continue
            summary = self.modules.summarizer(
                c_code=code,
                declaration_context=self._build_context(kind=decl.kind, name=decl.name),
            )
            if verbose:
                print(
                    f"  Summary for {decl.name} ({decl.kind}): params={summary.arguments}, returns={summary.outputs}"
                )
            entries.append(
                {
                    "name": decl.name,
                    "kind": decl.kind,
                    "arguments": summary.arguments,
                    "outputs": summary.outputs,
                    "function": summary.function,
                }
            )
        return entries

    def _format_declaration_summaries(self, summaries: Iterable[dict]) -> str:
        summaries = list(summaries)
        if not summaries:
            return ""
        lines = ["Code Summary by Declaration:"]
        for entry in summaries:
            lines.append(f"- {entry['name']} ({entry['kind']}):")
            lines.append(f"  Parameters: {entry['arguments']}")
            lines.append(f"  Returns: {entry['outputs']}")
            lines.append(f"  Functionality: {entry['function']}")
        return "\n".join(lines)

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
            dependencies[dst_comp].add(src_comp)
        return dependencies

    def _build_dependency_context(
        self,
        *,
        component_index: int,
        component_dependencies: Dict[int, Set[int]],
        component_summaries: Dict[int, List[dict]],
        max_hops: int = 2,
        max_entries: int = 12,
    ) -> str:
        upstream = component_dependencies.get(component_index)
        if not upstream:
            return ""

        seen_components: Set[int] = set()
        seen_decls: Set[str] = set()
        lines: List[str] = ["Known dependencies:"]
        queue = deque([(idx, 1) for idx in sorted(upstream)])

        while queue and len(seen_decls) < max_entries:
            idx, depth = queue.popleft()
            if idx in seen_components or depth > max_hops:
                continue
            seen_components.add(idx)
            entries = component_summaries.get(idx, [])
            if entries:
                lines.append(f"SCC {idx}:")
                for entry in entries:
                    name = entry.get("name")
                    if not name or name in seen_decls:
                        continue
                    kind = entry.get("kind", "")
                    args = entry.get("arguments", "?")
                    outputs = entry.get("outputs", "?")
                    function = entry.get("function", "")
                    lines.append(
                        f"- {name} ({kind}) | params: {args} | returns: {outputs} | function: {function}"
                    )
                    seen_decls.add(name)
                    if len(seen_decls) >= max_entries:
                        break
            if depth < max_hops:
                for parent in sorted(component_dependencies.get(idx, set())):
                    if parent not in seen_components:
                        queue.append((parent, depth + 1))

        if len(lines) == 1:
            return ""
        return "\n".join(lines)
