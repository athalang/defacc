"""
IRENE C-to-Rust Translation Evaluation

Simple eval task to measure translation quality.
"""

from inspect_ai import Task, task, eval
from inspect_ai.dataset import Sample
from inspect_ai.scorer import Score, Target, accuracy, scorer
from inspect_ai.solver import TaskState, solver, Generate

from irene.pipeline import IRENEPipeline
from irene.tests.test_paper_examples import ALL_TEST_CASES, BASIC_TEST_CASES, ADVERSARIAL_TEST_CASES


@solver
def translate_c_to_rust():
    """
    Solver that uses IRENE pipeline to translate C to Rust.
    """
    async def solve(state: TaskState, generate: Generate):
        # Get the C code from input
        test_name = state.input_text

        if test_name not in ALL_TEST_CASES:
            state.output.completion = f"Error: Unknown test case {test_name}"
            return state

        c_code = ALL_TEST_CASES[test_name]

        # Initialize pipeline (using the LLM from state)
        from irene.settings import settings
        import dspy

        lm = dspy.LM(
            model=settings.model,
            api_base=settings.api_base,
            temperature=settings.temperature,
            api_key=settings.api_key,
        )

        # Use dspy.context() for async-safe configuration
        with dspy.context(lm=lm):
            pipeline = IRENEPipeline(lm=lm)

            # Translate
            result = pipeline.translate(c_code, verbose=False)

            # Store result in state
            state.output.completion = "compiled" if result['compiled'] else "failed"
            state.metadata["c_code"] = c_code,
            state.metadata["rust_code"] = result['rust_code']
            state.metadata["compiled"] = result['compiled']
            state.metadata["iterations"] = result['iterations']
            state.metadata["errors"] = result.get('errors', '')

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


@scorer(metrics=[accuracy()])
def safety_scorer():
    """
    Scorer that checks compilation success AND safety properties of generated Rust code.

    Scoring:
    - C (Correct): Compiles successfully with 0 unsafe blocks
    - P (Partial): Compiles but contains unsafe blocks
    - I (Incorrect): Failed to compile
    """
    async def score(state: TaskState, target: Target):
        rust_code = state.metadata.get("rust_code", "")
        compiled = state.metadata.get("compiled", False)
        iterations = state.metadata.get("iterations", 0)

        # Count unsafe patterns
        unsafe_blocks = rust_code.count("unsafe {") + rust_code.count("unsafe{")
        unsafe_fn = rust_code.count("unsafe fn")
        unsafe_impl = rust_code.count("unsafe impl")
        total_unsafe = unsafe_blocks + unsafe_fn + unsafe_impl

        # Check for other safety indicators
        has_unwrap = ".unwrap()" in rust_code
        has_expect = ".expect(" in rust_code
        panics = has_unwrap or has_expect

        # Determine score
        if not compiled:
            score_val = "I"
            explanation = f"✗ Failed to compile: {state.metadata.get('errors', 'Unknown')[:100]}"
        elif total_unsafe > 0:
            score_val = "P"
            explanation = f"⚠ Compiles but uses {total_unsafe} unsafe construct(s) ({unsafe_blocks} blocks, {unsafe_fn} fns, {unsafe_impl} impls)"
        else:
            score_val = "C"
            safety_notes = []
            if panics:
                safety_notes.append(f"uses {'unwrap' if has_unwrap else 'expect'}")
            explanation = f"✓ Safe compilation in {iterations} iteration(s)" + (f" ({', '.join(safety_notes)})" if safety_notes else " (no unsafe blocks)")

        return Score(
            value=score_val,
            answer=state.output.completion,
            explanation=explanation
        )

    return score


def single_test(test_name: str = "scanf_two_ints"):
    """
    Dynamic eval task for any individual test case.

    Usage:
        inspect eval irene/evals/c_to_rust.py@single_test -T test_name=buffer_overflow
        inspect eval irene/evals/c_to_rust.py@single_test -T test_name=use_after_free

    Or use the default:
        inspect eval irene/evals/c_to_rust.py@single_test
    """
    if test_name not in ALL_TEST_CASES:
        raise ValueError(f"Unknown test case: {test_name}. Available: {list(ALL_TEST_CASES.keys())}")

    # Determine category
    if test_name in BASIC_TEST_CASES:
        category = "basic"
    elif test_name in ADVERSARIAL_TEST_CASES:
        category = "adversarial"
    else:
        category = "unknown"

    return Task(
        dataset=[
            Sample(
                input=test_name,
                target="compiled",
                id=test_name,
                metadata={
                    "category": category,
                }
            )
        ],
        solver=translate_c_to_rust(),
        scorer=compilation_success()
    )

# Make it a task
single_test = task(single_test)


@task
def all_tests():
    """
    Eval task for all test cases (basic + adversarial) with safety scoring.

    This is the primary evaluation that checks:
    - Compilation success
    - Zero unsafe blocks
    - Zero unsafe functions
    - Zero unsafe impls

    Usage:
        inspect eval irene/evals/c_to_rust.py@all_tests
    """
    samples = []
    for test_name in ALL_TEST_CASES.keys():
        # Determine category
        if test_name in BASIC_TEST_CASES:
            category = "basic"
        elif test_name in ADVERSARIAL_TEST_CASES:
            category = "adversarial"
        else:
            category = "unknown"

        samples.append(Sample(
            input=test_name,
            target="compiled",
            id=test_name,
            metadata={
                "category": category,
            }
        ))

    return Task(
        dataset=samples,
        solver=translate_c_to_rust(),
        scorer=safety_scorer()
    )


@task
def basic_tests():
    """
    Eval task for basic test cases only (original 7 examples) with safety scoring.

    Usage:
        inspect eval irene/evals/c_to_rust.py@basic_tests
    """
    samples = [
        Sample(
            input=test_name,
            target="compiled",
            id=test_name,
            metadata={
                "category": "basic",
            }
        )
        for test_name in BASIC_TEST_CASES.keys()
    ]

    return Task(
        dataset=samples,
        solver=translate_c_to_rust(),
        scorer=safety_scorer()
    )


@task
def adversarial_tests():
    """
    Eval task for adversarial test cases (security vulnerabilities) with safety scoring.

    These test cases contain common C vulnerabilities:
    - Buffer overflows
    - Use-after-free
    - Integer overflows
    - NULL pointer dereferences
    - Uninitialized memory
    - Format string vulnerabilities

    IRENE's defensive mechanisms should prevent these from becoming unsafe Rust code.

    Usage:
        inspect eval irene/evals/c_to_rust.py@adversarial_tests
    """
    samples = [
        Sample(
            input=test_name,
            target="compiled",
            id=test_name,
            metadata={
                "category": "adversarial",
            }
        )
        for test_name in ADVERSARIAL_TEST_CASES.keys()
    ]

    return Task(
        dataset=samples,
        solver=translate_c_to_rust(),
        scorer=safety_scorer()
    )


@task
def all_tests_compilation():
    """
    Eval task for all test cases with compilation-only scoring (no safety checks).

    This is a more lenient scorer that only checks:
    - Compilation success (allows unsafe blocks)

    Usage:
        inspect eval irene/evals/c_to_rust.py@all_tests_compilation
    """
    samples = []
    for test_name in ALL_TEST_CASES.keys():
        # Determine category
        if test_name in BASIC_TEST_CASES:
            category = "basic"
        elif test_name in ADVERSARIAL_TEST_CASES:
            category = "adversarial"
        else:
            category = "unknown"

        samples.append(Sample(
            input=test_name,
            target="compiled",
            id=test_name,
            metadata={
                "category": category,
            }
        ))

    return Task(
        dataset=samples,
        solver=translate_c_to_rust(),
        scorer=compilation_success()
    )


@task
def adversarial_tests_compilation():
    """
    Eval task for adversarial test cases with compilation-only scoring (no safety checks).

    This is a more lenient scorer useful for debugging.

    Usage:
        inspect eval irene/evals/c_to_rust.py@adversarial_tests_compilation
    """
    samples = [
        Sample(
            input=test_name,
            target="compiled",
            id=test_name,
            metadata={
                "category": "adversarial",
            }
        )
        for test_name in ADVERSARIAL_TEST_CASES.keys()
    ]

    return Task(
        dataset=samples,
        solver=translate_c_to_rust(),
        scorer=compilation_success()
    )