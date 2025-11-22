import dspy

from defacc.settings import settings
from defacc.pipeline import IRENEPipeline
from defacc.demo import run_demo, run_all_tests
from defacc.tests.test_paper_examples import ALL_TEST_CASES

def main(args):
    lm = dspy.LM(
        model=settings.model,
        api_base=settings.api_base,
        temperature=settings.temperature,
        api_key=settings.api_key,
    )
    dspy.configure(lm=lm)
    pipeline = IRENEPipeline(lm=lm)

    if args.all:
        run_all_tests(pipeline)
    else:
        run_demo(pipeline, args.test)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="IRENE C-to-Rust Translation Demo")
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

    main(args=args)