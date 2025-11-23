import os
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import dspy
import networkx as nx

from .rule_analyzer import RuleHint, StaticRuleAnalyzer, format_hints
from .retriever import ExampleRetriever, TranslationExample, format_examples
from .compiler import RustCompiler, check_rustc_available
from .dspy_modules import IRENEModules
from .dependency_graph import DeclarationRecord, SCCComponent
from .project_scanner import build_project_graph
from .workspace import RustWorkspace

@dataclass
class CompilationResult:
    success: bool
    iterations: int
    errors: Optional[str]


@dataclass
class TranslationArtifacts:
    rule_hints: List[RuleHint]
    examples: List[TranslationExample]
    summary_text: str
    raw_summary: Optional[object] = None


@dataclass
class TranslationResult:
    rust_code: str
    compilation: CompilationResult
    artifacts: TranslationArtifacts


class IRENEPipeline:
    def __init__(
        self,
        lm: dspy.LM,
        corpus_path=os.path.join(os.path.dirname(__file__), "corpus/examples.json"),
        max_refinement_iterations: int = 5,
    ):
        self.max_iterations = max_refinement_iterations

        # Initialize components
        self.rule_analyzer = StaticRuleAnalyzer()
        self.retriever = ExampleRetriever(corpus_path)
        self.compiler = RustCompiler()

        # Store LM instance (caller should configure DSPy before creating pipeline)
        self.lm = lm

        # Initialize DSPy modules
        self.modules = IRENEModules()

        # Check if rustc is available
        if not check_rustc_available():
            print("Warning: rustc not found. Compilation checks will be skipped.")
            print("Install Rust from: https://rustup.rs/")

    def translate(
        self,
        c_code: str,
        verbose: bool = True,
        rule_hints: Optional[List[RuleHint]] = None,
        summary_override: Optional[str] = None,
        declaration_context: Optional[str] = None,
        dependency_context: Optional[str] = None,
        workspace_context: Optional[str] = None,
        workspace_highlight: Optional[str] = None,
        workspace_path: Optional[Path] = None,
        expected_declarations: Optional[int] = None,
        c_declaration_names: Optional[List[str]] = None,
        workspace_handle: Optional[RustWorkspace] = None,
    ) -> TranslationResult:
        """
        Translate C code to Rust using the IRENE framework.

        Args:
            c_code: The C source code to translate
            verbose: Print progress information
            rule_hints: Optional pre-computed rule hints to reuse instead of re-running
                libclang analysis
            summary_override: Optional plain-text summary to feed directly to the translator
            dependency_context: Optional summaries of upstream declarations that already exist
            workspace_context: Optional Rust source code that should be prepended
                before compiling the generated snippet. Used when compiling projects
                so upstream definitions are available to rustc.
            workspace_highlight: Optional curated snippet from the workspace
                (e.g., immediate SCC dependencies) that should be surfaced
                prominently to the LM even if trimmed from the main workspace view.
            workspace_path: Optional filesystem path to the persistent workspace file.
                When provided, the compiler will read the latest contents directly
                from disk before invoking rustc.
            expected_declarations: Optional count of top-level declarations represented
                in the C input. When provided, the translator is instructed to emit
                exactly this many Rust declarations (no more, no less).
            c_declaration_names: Optional ordered list of declaration names from the
                original C snippet. Used to provide naming guidance (e.g. CamelCase)
                when generating Rust identifiers.
            workspace_handle: Optional RustWorkspace object. When provided, the
                translator/refiner must emit unified diffs that mutate this file
                instead of returning standalone code snippets.

        Returns:
            Dictionary containing:
                - rust_code: The final Rust code
                - compiled: Whether the code compiled successfully
                - iterations: Number of refinement iterations used
                - errors: Final error messages (if any)
                - summary: Either the summarizer output or the provided summary text
        """
        if verbose:
            print("\n" + "=" * 60)
            print("IRENE C-to-Rust Translation Pipeline")
            print("=" * 60 + "\n")

        computed_hints, categories = self._analyze_rules(c_code, rule_hints, verbose)
        examples = self._retrieve_examples(c_code, categories, verbose)
        root_context = declaration_context or self._build_context(kind="translation_unit", name="input")
        summary_obj, summary_payload = self._summarize_code(
            c_code,
            summary_override=summary_override,
            verbose=verbose,
            declaration_context=root_context,
        )
        workspace_obj = workspace_handle
        if not workspace_obj and workspace_path:
            # Avoid resetting existing files unintentionally.
            workspace_obj = RustWorkspace(Path(workspace_path), reset=False)
        if not workspace_obj:
            raise RuntimeError("Patch-based translation requires a workspace path.")

        workspace_file_path = workspace_obj.path
        translator_inputs = {
            "c_code": c_code,
            "rule_hints": format_hints(computed_hints),
            "examples": format_examples(examples),
            "summary": summary_payload,
            "declaration_context": root_context or "",
            "dependency_context": dependency_context or "",
            "translation_constraints": self._translation_constraints(
                expected_declarations,
                c_declaration_names,
                workspace_file=workspace_file_path,
            ),
            "workspace_file": str(workspace_file_path),
        }

        workspace_view = workspace_context or workspace_obj.current_text()
        initial_patch = self._generate_patch(
            translator_inputs=translator_inputs,
            workspace_view=workspace_view,
            workspace_highlight=workspace_highlight,
            compiler_errors="",
            verbose=verbose,
        )

        final_code, compilation = self._compile_with_refinement(
            verbose,
            workspace_context=workspace_context,
            workspace_highlight=workspace_highlight,
            initial_patch=initial_patch,
            workspace_handle=workspace_obj,
            translator_inputs=translator_inputs,
        )

        artifacts = TranslationArtifacts(
            rule_hints=computed_hints,
            examples=examples,
            summary_text=summary_payload or "",
            raw_summary=summary_obj,
        )

        final_rust = workspace_obj.current_text() if workspace_obj else final_code
        return TranslationResult(rust_code=final_rust, compilation=compilation, artifacts=artifacts)

    def translate_project(
        self,
        compile_commands: Path,
        verbose: bool = True,
        workspace_path: Optional[Path] = None,
    ) -> List[dict]:
        """Translate an entire project by iterating over SCCs from the project scanner."""
        db_path = Path(compile_commands)
        project_graph = build_project_graph(db_path)
        components = project_graph.components()
        if not components:
            if verbose:
                print("No strongly connected components found for translation.")
            return []

        workspace = RustWorkspace(Path(workspace_path)) if workspace_path else None
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
            merged_rule_hints = self._collect_rule_hints(component.declarations)
            component_context = self._build_context(
                kind="scc",
                name=f"SCC {component.index}: {decl_names}",
            )
            dependency_context = self._build_dependency_context(
                component_index=component.index,
                component_dependencies=component_dependencies,
                component_summaries=component_summaries,
            )
            workspace_context = workspace.current_text() if workspace else None
            workspace_highlight = self._workspace_dependency_snippet(
                workspace_context,
                component_dependencies.get(component.index),
            ) if workspace_context else None

            translation = self.translate(
                c_code=c_source,
                verbose=verbose,
                rule_hints=merged_rule_hints or None,
                summary_override=summary_text or None,
                declaration_context=component_context,
                dependency_context=dependency_context or None,
                workspace_context=workspace_context,
                workspace_highlight=workspace_highlight,
                workspace_path=workspace.path if workspace else None,
                expected_declarations=len(component.declarations),
                c_declaration_names=[decl.name for decl in component.declarations],
                workspace_handle=workspace,
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
            if workspace and translation.compilation.success:
                # Workspace already mutated by patches; no append needed.
                pass

        return results

    def _format_summary(self, summary) -> str:
        return f"""
Code Summary:
- Parameters: {summary.arguments}
- Returns: {summary.outputs}
- Functionality: {summary.function}
"""

    def _analyze_rules(
        self, c_code: str, cached_hints: Optional[List[RuleHint]], verbose: bool
    ) -> Tuple[List[RuleHint], List[str]]:
        if cached_hints is None:
            if verbose:
                print("Step 1: Analyzing C code patterns...")
            computed_hints = self.rule_analyzer.analyze(c_code)
        else:
            computed_hints = cached_hints
            if verbose:
                print("Step 1: Using provided rule hints...")
        categories = list({hint.category for hint in computed_hints if getattr(hint, "category", None)})
        if verbose:
            print(f"  Detected categories: {categories}")
            print(f"  Found {len(computed_hints)} rule hints\n")
        return computed_hints, categories

    def _retrieve_examples(
        self, c_code: str, categories: List[str], verbose: bool
    ) -> List[TranslationExample]:
        if verbose:
            print("Step 2: Retrieving similar examples...")
        examples = self.retriever.retrieve(c_code, categories, top_k=3)
        if verbose:
            print(f"  Retrieved {len(examples)} relevant examples\n")
        return examples

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
                print("Step 3: Summarizing C code structure...")
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
                print("Step 3: Using provided summary.\n")
        return summary_obj, summary_payload or ""

    def _generate_patch(
        self,
        *,
        translator_inputs: dict,
        workspace_view: Optional[str],
        workspace_highlight: Optional[str],
        compiler_errors: Optional[str],
        verbose: bool,
    ) -> str:
        workspace_prompt = self._workspace_prompt_fragment(
            workspace_view,
            workspace_highlight,
        )
        if verbose and workspace_prompt:
            print(
                "  Workspace prompt provided to translator "
                f"(length={len(workspace_prompt)} characters)."
            )
        payload = dict(translator_inputs)
        payload.update(
            {
                "workspace_context": workspace_prompt,
                "compiler_errors": compiler_errors or "",
            }
        )
        rust_result = self.modules.translator(**payload)
        patch = (rust_result.patch_diff or "").strip() if hasattr(rust_result, "patch_diff") else None
        workspace_file = payload.get("workspace_file")
        if workspace_file and not patch:
            raise RuntimeError(
                "Translator did not produce a unified diff. "
                "Ensure the LM outputs a valid 'patch_diff' with ---/+++ headers."
            )
        if verbose:
            print("  Patch generation complete\n")
        return patch or ""

    def _compile_with_refinement(
        self,
        verbose: bool,
        *,
        workspace_context: Optional[str] = None,
        workspace_highlight: Optional[str] = None,
        initial_patch: Optional[str] = None,
        workspace_handle: Optional[RustWorkspace] = None,
        translator_inputs: Optional[dict] = None,
    ) -> Tuple[str, CompilationResult]:
        if verbose:
            print("Step 5: Applying patches and compiling...")

        if not workspace_handle or not translator_inputs:
            raise RuntimeError("Workspace handle and translator inputs are required for patch compilation.")

        workspace_view = workspace_context or workspace_handle.current_text()
        pending_patch = initial_patch
        compiled = False
        errors = ""

        for iteration in range(self.max_iterations):
            if pending_patch:
                snapshot = workspace_handle.snapshot()
                applied, apply_error = workspace_handle.apply_patch(pending_patch)
                if not applied:
                    errors = f"Failed to apply patch: {apply_error}"
                    if verbose:
                        print(f"    Patch apply failed: {apply_error.strip()}")
                        print("    Patch preview:\n" + pending_patch[:400])
                    workspace_handle.write_text(snapshot)
                else:
                    workspace_view = workspace_handle.current_text()
                    success, errors = self.compiler.compile(workspace_view)
                    if success:
                        compiled = True
                        if verbose:
                            print(f"  ✓ Compilation successful after {iteration + 1} iteration(s)!\n")
                        break
                    if verbose:
                        print(f"  ✗ Compilation failed (iteration {iteration + 1}/{self.max_iterations})")
                        print(f"    Errors: {errors[:200]}...")
                    workspace_handle.write_text(snapshot)
                    workspace_view = snapshot
            else:
                errors = "Missing patch diff from model"
                if verbose:
                    print("    No patch diff provided; retrying translator...")

            if iteration >= self.max_iterations - 1:
                if verbose:
                    print("    Max iterations reached.\n")
                break

            if verbose:
                print("    Re-requesting patch from translator...")
            pending_patch = self._generate_patch(
                translator_inputs=translator_inputs,
                workspace_view=workspace_view,
                workspace_highlight=workspace_highlight,
                compiler_errors=errors,
                verbose=verbose,
            )

        result = CompilationResult(
            success=compiled,
            iterations=iteration + 1,
            errors=None if compiled else errors,
        )
        return workspace_handle.current_text(), result

    @staticmethod
    def _workspace_prompt_fragment(
        workspace_context: Optional[str],
        highlight: Optional[str] = None,
        limit: int = 6000,
    ) -> str:
        """Return workspace snippet with prioritized sections and symbol summary."""
        sections: List[str] = []
        focus = (highlight or "").strip()
        if focus:
            sections.append(focus)
        elif workspace_context:
            trimmed = workspace_context.strip()
            if trimmed:
                truncated = len(trimmed) > limit
                body = trimmed if not truncated else trimmed[-limit:]
                signature_body = IRENEPipeline._declaration_signature_block(body)
                if not signature_body:
                    return ""
                symbol_lines = IRENEPipeline._workspace_symbol_summary(trimmed)

                header_lines: List[str] = []
                if symbol_lines:
                    header_lines.append("// Existing workspace declarations available for reuse:")
                    header_lines.extend(f"// - {item}" for item in symbol_lines)
                if truncated:
                    header_lines.append(f"// [Workspace truncated to last {limit} characters]")

                if header_lines:
                    header = "\n".join(header_lines)
                    sections.append(f"{header}\n\n{signature_body}")
                else:
                    sections.append(signature_body)

        return "\n\n".join(part for part in sections if part).strip()

    @staticmethod
    def _translation_constraints(
        expected_declarations: Optional[int],
        c_declaration_names: Optional[List[str]] = None,
        workspace_file: Optional[Path] = None,
    ) -> str:
        rules: List[str] = [
            "Output pure Rust code only. No comments, markdown, or explanatory text.",
            "Never add placeholder headings like 'assuming X exists'; instead, reference existing items or omit them.",
            "Do not introduce new top-level declarations beyond what the C snippet defines.",
            "Follow Rust naming conventions: structs/enums/types/traits must be UpperCamelCase; update all uses when renaming.",
            "Use only fields or methods that exist in the provided structs/enums. Do NOT invent helper methods like `as_bytes`/`as_ref` unless already defined in the workspace context.",
            "Avoid redundant parentheses in control-flow conditions (e.g., use `if flag` not `if (flag)`).",
        ]
        if workspace_file:
            rules.append(
                f"Produce a unified diff that edits {workspace_file} in-place."
                " Include '---'/'+++' headers and @@ hunks referencing that file."
            )
        if expected_declarations and expected_declarations > 0:
            decl_word = "declaration" if expected_declarations == 1 else "declarations"
            rules.append(
                f"Emit exactly {expected_declarations} top-level Rust {decl_word}, mirroring the provided C declarations."
            )
        for name in c_declaration_names or []:
            target = IRENEPipeline._rust_camel_case(name)
            if not target or target == name:
                continue
            rules.append(
                f"Rename `{name}` to `{target}` in Rust and update all references to use `{target}`."
            )
        return "\n".join(f"- {rule}" for rule in rules)

    @staticmethod
    def _workspace_symbol_summary(workspace_context: str, max_symbols: int = 40) -> List[str]:
        pattern = re.compile(
            r"^\s*(?:pub\s+)?(struct|enum|trait|fn|type|const|static)\s+([A-Za-z_][A-Za-z0-9_]*)",
            re.MULTILINE,
        )
        symbols: List[str] = []
        seen: Set[str] = set()
        for match in pattern.finditer(workspace_context):
            name = match.group(2)
            if name in seen:
                continue
            seen.add(name)
            symbols.append(f"{match.group(1)} {name}")
            if len(symbols) >= max_symbols:
                break
        return symbols

    @staticmethod
    def _rust_camel_case(name: str) -> str:
        parts = re.split(r"[^A-Za-z0-9]+", name)
        filtered = [part for part in parts if part]
        if not filtered:
            return name
        camel = "".join(part[:1].upper() + part[1:] for part in filtered)
        return camel

    @staticmethod
    def _declaration_signature_block(snippet: Optional[str]) -> str:
        if not snippet:
            return ""
        patterns = [
            re.compile(r"^\s*(?:pub\s+)?(?:unsafe\s+)?fn\s+[A-Za-z_][A-Za-z0-9_]*"),
            re.compile(r"^\s*(?:pub\s+)?(struct|enum|trait)\s+[A-Za-z_][A-Za-z0-9_]*"),
            re.compile(r"^\s*(?:pub\s+)?type\s+[A-Za-z_][A-Za-z0-9_]*"),
            re.compile(r"^\s*(?:pub\s+)?const\s+[A-Za-z_][A-Za-z0-9_]*"),
            re.compile(r"^\s*(?:pub\s+)?static\s+[A-Za-z_][A-Za-z0-9_]*"),
            re.compile(r"^\s*(?:pub\s+)?impl\s+[^{]+"),
        ]
        signatures: List[str] = []
        seen: Set[str] = set()
        for raw in snippet.splitlines():
            line = raw.strip()
            if not line:
                continue
            if any(pat.search(line) for pat in patterns):
                normalized = line.rstrip("{").rstrip()
                if normalized not in seen:
                    signatures.append(normalized)
                    seen.add(normalized)
        return "\n".join(signatures)

    @staticmethod
    def _workspace_dependency_snippet(
        workspace_context: Optional[str],
        dependency_indices: Optional[Iterable[int]],
        char_limit: int = 4000,
    ) -> Optional[str]:
        if not workspace_context or not dependency_indices:
            return None

        sections = IRENEPipeline._workspace_sections(workspace_context)
        ordered = [idx for idx in sorted(set(dependency_indices or []))]
        if not ordered:
            return None

        snippets: List[str] = []
        total = 0
        for idx in ordered:
            block = sections.get(idx)
            if not block:
                continue
            block = block.strip()
            if not block:
                continue
            block_len = len(block)
            if total and total + block_len > char_limit:
                break
            if not total and block_len > char_limit:
                block = block[-char_limit:]
                block_len = len(block)
            snippets.append(block)
            total += block_len
            if total >= char_limit:
                break

        if not snippets:
            return None

        header = "// Immediate upstream SCC excerpts (reuse existing structs/types):"
        return f"{header}\n\n" + "\n\n".join(snippets)

    @staticmethod
    def _workspace_sections(workspace_context: str) -> Dict[int, str]:
        pattern = re.compile(r"^//\s*SCC\s+(\d+):.*$", re.MULTILINE)
        matches = list(pattern.finditer(workspace_context))
        if not matches:
            return {}

        sections: Dict[int, str] = {}
        for i, match in enumerate(matches):
            try:
                idx = int(match.group(1))
            except ValueError:
                continue
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(workspace_context)
            sections[idx] = workspace_context[start:end].strip()
        return sections

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

    def _collect_rule_hints(self, declarations: Iterable[DeclarationRecord]) -> List[RuleHint]:
        merged: List[RuleHint] = []
        seen = set()
        for decl in declarations:
            for hint in getattr(decl, "rule_hints", []) or []:
                key = (
                    getattr(hint, "category", ""),
                    getattr(hint, "code_snippet", ""),
                    getattr(hint, "suggested_rust", ""),
                    getattr(hint, "explanation", ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                merged.append(hint)
        return merged

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
