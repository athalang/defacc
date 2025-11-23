#!/usr/bin/env python3
"""
Convenience wrapper for running GUARDIAN from project root.
Delegates to main module.
"""

if __name__ == "__main__":
    import argparse
    import dspy
    from guardian.settings import settings
    from guardian.pipeline import GUARDIANPipeline
    from guardian.demo import run_demo, run_all_tests
    from guardian.tests.test_paper_examples import ALL_TEST_CASES

    parser = argparse.ArgumentParser(description="GUARDIAN C-to-Rust Translation Demo")
    parser.add_argument(
        "--test",
        type=str,
        default="scanf_two_ints",
        help=f"Test case to run (choices: {', '.join(ALL_TEST_CASES.keys())})",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all test cases",
    )
    args = parser.parse_args()

    # Configure LLM and create pipeline
    lm = dspy.LM(
        model=settings.model,
        api_base=settings.api_base,
        temperature=settings.temperature,
        api_key=settings.api_key,
    )
    dspy.configure(lm=lm)
    pipeline = GUARDIANPipeline(lm=lm)

    # Run demo or all tests
    if args.all:
        run_all_tests(pipeline)
    else:
        run_demo(pipeline, args.test)