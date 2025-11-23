"""
IRENE C-to-Rust Translation Evaluation

Simple eval task to measure translation quality.
"""

from inspect_ai import Task, task, eval
from inspect_ai.dataset import Sample
from inspect_ai.scorer import Score, Target, accuracy, scorer
from inspect_ai.solver import TaskState, solver, Generate

from irene.llm import build_lm
from irene.pipeline import IRENEPipeline
from irene.project_runner import translate_compile_commands
from irene.tests.test_paper_examples import ALL_TEST_CASES


@solver
def translate_c_to_rust():
    """
    Solver that uses IRENE pipeline to translate C to Rust.
    """
    async def solve(state: TaskState, generate: Generate):
        # Get the C code from input
        test_name = state.input_text

        compile_commands = state.metadata.get("compile_commands")
        if not compile_commands and test_name not in ALL_TEST_CASES:
            state.output.completion = f"Error: Unknown test case {test_name}"
            return state

        c_code = ALL_TEST_CASES.get(test_name)

        # Initialize pipeline (using the LLM from state)
        lm = build_lm()

        # Use dspy.context() for async-safe configuration
        import dspy

        with dspy.context(lm=lm):
            pipeline = IRENEPipeline(lm=lm)

            if compile_commands:
                project_results = translate_compile_commands(
                    compile_commands, pipeline=pipeline, verbose=False
                )
                compiled = all(
                    entry["result"].compilation.success for entry in project_results
                )
                state.output.completion = "compiled" if compiled else "failed"
                state.metadata["compiled"] = compiled
                state.metadata["project_results"] = [
                    {
                        "scc_index": entry["scc_index"],
                        "declarations": entry["declarations"],
                        "compiled": entry["result"].compilation.success,
                        "iterations": entry["result"].compilation.iterations,
                        "errors": entry["result"].compilation.errors,
                    }
                    for entry in project_results
                ]
            else:
                result = pipeline.translate(c_code, verbose=False)

                # Store result in state
                state.output.completion = "compiled" if result.compilation.success else "failed"
                state.metadata["rust_code"] = result.rust_code
                state.metadata["compiled"] = result.compilation.success
                state.metadata["iterations"] = result.compilation.iterations
                state.metadata["errors"] = result.compilation.errors or ""

        return state

    return solve


@scorer(metrics=[accuracy()])
def compilation_success():
    """
    Scorer that checks if the Rust code compiled successfully.
    """
    async def score(state: TaskState, target: Target):
        # Check if compilation succeeded
        compiled = state.metadata.get("compiled", False)

        return Score(
            value="C" if compiled else "I",  # C = Correct, I = Incorrect
            answer=state.output.completion,
            explanation=f"Compiled in {state.metadata.get('iterations', 0)} iterations" if compiled else f"Failed: {state.metadata.get('errors', 'Unknown')[:100]}"
        )

    return score


@task
def scanf_two_ints_eval():
    """
    Simple eval task for the scanf_two_ints test case.

    Usage:
        inspect eval irene/evals/c_to_rust.py@scanf_two_ints_eval
    """
    return Task(
        dataset=[
            Sample(
                input="scanf_two_ints",
                target="compiled",
                id="scanf_two_ints",
                metadata={"category": "I/O"}
            )
        ],
        solver=translate_c_to_rust(),
        scorer=compilation_success()
    )


@task
def all_tests_eval():
    """
    Eval task for all test cases.

    Usage:
        inspect eval irene/evals/c_to_rust.py@all_tests_eval
    """
    samples = [
        Sample(
            input=test_name,
            target="compiled",
            id=test_name,
            metadata={"category": "unknown"}  # TODO: add category metadata
        )
        for test_name in ALL_TEST_CASES.keys()
    ]

    return Task(
        dataset=samples,
        solver=translate_c_to_rust(),
        scorer=compilation_success()
    )
