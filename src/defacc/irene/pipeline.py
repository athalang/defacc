import os
import dspy

from .rule_analyzer import StaticRuleAnalyzer, format_hints
from .retriever import ExampleRetriever, format_examples
from .compiler import RustCompiler, check_rustc_available
from .dspy_modules import IRENEModules

class IRENEPipeline:
    def __init__(
        self,
        lm: dspy.LM,
        corpus_path=os.path.join(os.path.dirname(__file__), "corpus/examples.json"),
        max_refinement_iterations: int = 3,
    ):
        self.max_iterations = max_refinement_iterations

        # Initialize components
        self.rule_analyzer = StaticRuleAnalyzer()
        self.retriever = ExampleRetriever(corpus_path)
        self.compiler = RustCompiler()
        
        # Configure DSPy with the LM
        self.lm = lm
        dspy.configure(lm=self.lm)
        
        # Initialize DSPy modules after configuration
        self.modules = IRENEModules()

        # Check if rustc is available
        if not check_rustc_available():
            print("Warning: rustc not found. Compilation checks will be skipped.")
            print("Install Rust from: https://rustup.rs/")

    def translate(self, c_code: str, verbose: bool = True) -> dict:
        """
        Translate C code to Rust using the IRENE framework.

        Args:
            c_code: The C source code to translate
            verbose: Print progress information

        Returns:
            Dictionary containing:
                - rust_code: The final Rust code
                - compiled: Whether the code compiled successfully
                - iterations: Number of refinement iterations used
                - errors: Final error messages (if any)
        """
        if verbose:
            print("\n" + "=" * 60)
            print("IRENE C-to-Rust Translation Pipeline")
            print("=" * 60 + "\n")

        # Step 1: Analyze rules
        if verbose:
            print("Step 1: Analyzing C code patterns...")
        rule_hints = self.rule_analyzer.analyze(c_code)
        categories = list(set(hint.category for hint in rule_hints))
        if verbose:
            print(f"  Detected categories: {categories}")
            print(f"  Found {len(rule_hints)} rule hints\n")

        # Step 2: Retrieve examples
        if verbose:
            print("Step 2: Retrieving similar examples...")
        examples = self.retriever.retrieve(c_code, categories, top_k=3)
        if verbose:
            print(f"  Retrieved {len(examples)} relevant examples\n")

        # Step 3: Summarize code
        if verbose:
            print("Step 3: Summarizing C code structure...")
        summary = self.modules.summarizer(c_code=c_code)
        if verbose:
            print(f"  Params: {summary.arguments}")
            print(f"  Returns: {summary.outputs}")
            print(f"  Function: {summary.function}\n")

        # Step 4: Initial translation
        if verbose:
            print("Step 4: Translating to Rust...")
        rust_result = self.modules.translator(
            c_code=c_code,
            rule_hints=format_hints(rule_hints),
            examples=format_examples(examples),
            summary=self._format_summary(summary),
        )

        rust_code = rust_result.rust_code
        if verbose:
            print("  Initial translation complete\n")

        # Step 5: Compile and refine
        if verbose:
            print("Step 5: Compiling and refining...")

        compiled = False
        errors = ""
        iteration = 0

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
                # Try to refine
                if verbose:
                    print("    Refining code...")
                refined = self.modules.refiner(rust_code=rust_code, errors=errors)
                rust_code = refined.fixed_code
            else:
                if verbose:
                    print("    Max iterations reached.\n")

        # Return results
        return {
            "rust_code": rust_code,
            "compiled": compiled,
            "iterations": iteration + 1,
            "errors": errors if not compiled else None,
            "rule_hints": rule_hints,
            "examples": examples,
            "summary": summary,
        }

    def _format_summary(self, summary) -> str:
        return f"""
Code Summary:
- Parameters: {summary.arguments}
- Returns: {summary.outputs}
- Functionality: {summary.function}
"""
