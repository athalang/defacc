"""Shared helpers for GUARDIAN evaluation tasks."""

from typing import Callable, Optional

from inspect_ai.dataset import Sample
from inspect_ai.solver import Generate, TaskState, solver

from guardian.evals.utils import count_unsafe
from guardian.llm import build_lm
from guardian.pipeline import GUARDIANPipeline
from guardian.examples.paper_cases import ALL_TEST_CASES


def create_samples(
    test_cases: dict,
    metadata_fn: Optional[Callable[[str], dict]] = None,
) -> list[Sample]:
    """Create Sample objects from test cases, optionally with per-sample metadata."""
    return [
        Sample(
            input=test_name,
            target="compiled",
            id=test_name,
            metadata=metadata_fn(test_name) if metadata_fn else None,
        )
        for test_name in test_cases.keys()
    ]


@solver
def guardian_translate():
    """
    GUARDIAN solver: full defensive pipeline.

    Uses:
    - Compiler-guided error-driven refinement
    """

    async def solve(state: TaskState, generate: Generate):
        test_name = state.input_text
        if test_name not in ALL_TEST_CASES:
            state.output.completion = f"Error: Unknown test case {test_name}"
            return state

        c_code = ALL_TEST_CASES[test_name]

        lm = build_lm()
        pipeline = GUARDIANPipeline(lm=lm)
        result = pipeline.translate(c_code, verbose=False)
        compilation = result.compilation

        state.output.completion = "compiled" if compilation.success else "failed"
        state.metadata["c_code"] = c_code
        state.metadata["rust_code"] = result.rust_code
        state.metadata["c_compiled"] = (
            result.c_compilation.success if result.c_compilation else False
        )
        state.metadata["c_errors"] = (
            result.c_compilation.errors if result.c_compilation else ""
        ) or ""
        state.metadata["compiled"] = compilation.success
        state.metadata["iterations"] = compilation.iterations
        state.metadata["errors"] = compilation.errors or ""
        state.metadata["approach"] = "guardian"

        return state

    return solve
