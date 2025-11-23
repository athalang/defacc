"""
Baseline Comparison: GUARDIAN vs Vanilla LLM

This eval demonstrates GUARDIAN's defensive improvements by comparing:
1. Vanilla LLM - Direct prompting without defensive framework
2. GUARDIAN - Full pipeline with rules, examples, and refinement

Metrics:
- Compilation success rate
- Safety properties (unsafe block count)
- Refinement iterations needed
"""

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import Score, Target, accuracy, scorer
from inspect_ai.solver import TaskState, solver, Generate

from guardian.pipeline import GUARDIANPipeline
from guardian.compiler import RustCompiler
from guardian.tests.test_paper_examples import BASIC_TEST_CASES, ADVERSARIAL_TEST_CASES


@solver
def vanilla_llm_translate():
    """
    Baseline solver: Direct LLM translation without GUARDIAN framework.

    This uses simple prompting without:
    - Static rule analysis
    - Example retrieval
    - Structured summarization
    - Error-driven refinement
    """
    async def solve(state: TaskState, generate: Generate):
        test_name = state.input_text

        all_cases = {**BASIC_TEST_CASES, **ADVERSARIAL_TEST_CASES}
        if test_name not in all_cases:
            state.output.completion = f"Error: Unknown test case {test_name}"
            return state

        c_code = all_cases[test_name]

        # Simple vanilla prompt
        vanilla_prompt = f"""Translate the following C code to safe Rust code.

Requirements:
- Use only Rust standard library (no external crates)
- Ensure memory safety
- Return ONLY valid Rust source code (no markdown, no explanations)

C code:
```c
{c_code}
```

Rust code:"""

        from guardian.settings import settings
        import dspy

        lm = dspy.LM(
            model=settings.model,
            api_base=settings.api_base,
            temperature=settings.temperature,
            api_key=settings.api_key,
        )

        with dspy.context(lm=lm):
            # Direct LLM call without GUARDIAN pipeline
            response = lm(vanilla_prompt)

            # Handle response - dspy.LM() may return string or list
            if isinstance(response, list):
                rust_code = response[0] if response else ""
            else:
                rust_code = str(response)

            # Try to clean up common LLM formatting issues
            rust_code = rust_code.strip()
            if rust_code.startswith("```rust"):
                rust_code = rust_code[7:]
            if rust_code.startswith("```"):
                rust_code = rust_code[3:]
            if rust_code.endswith("```"):
                rust_code = rust_code[:-3]
            rust_code = rust_code.strip()

            # Try to compile
            compiler = RustCompiler()
            compiled, errors = compiler.compile(rust_code)

            # Store results
            state.output.completion = "compiled" if compiled else "failed"
            state.metadata["c_code"] = c_code
            state.metadata["rust_code"] = rust_code
            state.metadata["compiled"] = compiled
            state.metadata["iterations"] = 1  # No refinement
            state.metadata["errors"] = errors if not compiled else ""
            state.metadata["approach"] = "vanilla_llm"

        return state

    return solve


@solver
def guardian_translate():
    """
    GUARDIAN solver: Full defensive pipeline.

    Uses:
    - Static rule analysis
    - BM25 example retrieval
    - Structured summarization
    - Error-driven refinement (up to 3 iterations)
    """
    async def solve(state: TaskState, generate: Generate):
        test_name = state.input_text

        all_cases = {**BASIC_TEST_CASES, **ADVERSARIAL_TEST_CASES}
        if test_name not in all_cases:
            state.output.completion = f"Error: Unknown test case {test_name}"
            return state

        c_code = all_cases[test_name]

        from guardian.settings import settings
        import dspy

        lm = dspy.LM(
            model=settings.model,
            api_base=settings.api_base,
            temperature=settings.temperature,
            api_key=settings.api_key,
        )

        with dspy.context(lm=lm):
            pipeline = GUARDIANPipeline(lm=lm)
            result = pipeline.translate(c_code, verbose=False)
            compilation = result.compilation

            state.output.completion = "compiled" if compilation.success else "failed"
            state.metadata["c_code"] = c_code
            state.metadata["rust_code"] = result.rust_code
            state.metadata["compiled"] = compilation.success
            state.metadata["iterations"] = compilation.iterations
            state.metadata["errors"] = compilation.errors or ""
            state.metadata["approach"] = "guardian"

        return state

    return solve


@scorer(metrics=[accuracy()])
def comparison_scorer():
    """
    Enhanced scorer for baseline comparison.

    Scoring:
    - C (Correct): Compiles successfully with 0 unsafe blocks
    - P (Partial): Compiles but contains unsafe blocks
    - I (Incorrect): Failed to compile

    Also tracks:
    - Unsafe block count
    - Refinement iterations
    - Approach used (vanilla vs guardian)
    """
    async def score(state: TaskState, target: Target):
        rust_code = state.metadata.get("rust_code", "")
        compiled = state.metadata.get("compiled", False)
        iterations = state.metadata.get("iterations", 0)
        approach = state.metadata.get("approach", "unknown")

        # Count unsafe patterns
        unsafe_blocks = rust_code.count("unsafe {") + rust_code.count("unsafe{")
        unsafe_fn = rust_code.count("unsafe fn")
        unsafe_impl = rust_code.count("unsafe impl")
        total_unsafe = unsafe_blocks + unsafe_fn + unsafe_impl

        # Determine score
        if not compiled:
            score_val = "I"
            explanation = f"[{approach}] ✗ Failed: {state.metadata.get('errors', '')[:80]}"
        elif total_unsafe > 0:
            score_val = "P"
            explanation = f"[{approach}] ⚠ Compiles with {total_unsafe} unsafe construct(s)"
        else:
            score_val = "C"
            explanation = f"[{approach}] ✓ Safe ({iterations} iteration{'s' if iterations != 1 else ''})"

        return Score(
            value=score_val,
            answer=state.output.completion,
            explanation=explanation,
            metadata={
                "unsafe_blocks": unsafe_blocks,
                "unsafe_fn": unsafe_fn,
                "unsafe_impl": unsafe_impl,
                "total_unsafe": total_unsafe,
                "iterations": iterations,
                "approach": approach,
            }
        )

    return score


def _create_samples(test_cases: dict) -> list[Sample]:
    """Helper to create Sample objects from test cases."""
    return [
        Sample(
            input=test_name,
            target="compiled",
            id=test_name,
        )
        for test_name in test_cases.keys()
    ]


@task
def vanilla_basic():
    """
    Baseline: Vanilla LLM on basic test cases.

    Usage:
        inspect eval guardian/evals/baseline_comparison.py@vanilla_basic
    """
    return Task(
        dataset=_create_samples(BASIC_TEST_CASES),
        solver=vanilla_llm_translate(),
        scorer=comparison_scorer()
    )


@task
def guardian_basic():
    """
    GUARDIAN on basic test cases.

    Usage:
        inspect eval guardian/evals/baseline_comparison.py@guardian_basic
    """
    return Task(
        dataset=_create_samples(BASIC_TEST_CASES),
        solver=guardian_translate(),
        scorer=comparison_scorer()
    )


@task
def vanilla_adversarial():
    """
    Baseline: Vanilla LLM on adversarial test cases.

    Usage:
        inspect eval guardian/evals/baseline_comparison.py@vanilla_adversarial
    """
    return Task(
        dataset=_create_samples(ADVERSARIAL_TEST_CASES),
        solver=vanilla_llm_translate(),
        scorer=comparison_scorer()
    )


@task
def guardian_adversarial():
    """
    GUARDIAN on adversarial test cases.

    Usage:
        inspect eval guardian/evals/baseline_comparison.py@guardian_adversarial
    """
    return Task(
        dataset=_create_samples(ADVERSARIAL_TEST_CASES),
        solver=guardian_translate(),
        scorer=comparison_scorer()
    )


# Convenience combined tasks
ALL_TEST_CASES = {**BASIC_TEST_CASES, **ADVERSARIAL_TEST_CASES}


@task
def vanilla_all():
    """
    Baseline: Vanilla LLM on all test cases.

    Usage:
        inspect eval guardian/evals/baseline_comparison.py@vanilla_all
    """
    return Task(
        dataset=_create_samples(ALL_TEST_CASES),
        solver=vanilla_llm_translate(),
        scorer=comparison_scorer()
    )


@task
def guardian_all():
    """
    GUARDIAN on all test cases.

    Usage:
        inspect eval guardian/evals/baseline_comparison.py@guardian_all
    """
    return Task(
        dataset=_create_samples(ALL_TEST_CASES),
        solver=guardian_translate(),
        scorer=comparison_scorer()
    )
