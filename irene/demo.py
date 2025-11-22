import sys
import dspy
from pathlib import Path

from settings import settings

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from main import IRENEPipeline
from tests.test_paper_examples import ALL_TEST_CASES

def run_demo(test_name: str = "scanf_two_ints"):
    lm = dspy.LM(
        model=settings.model,
        api_base=settings.api_base,
        temperature=settings.temperature,
        api_key=settings.api_key,
    )
    dspy.configure(lm=lm)

    # Create pipeline
    print("\nInitializing IRENE pipeline...")
    pipeline = IRENEPipeline(lm_model=lm)
    print("✓ Pipeline ready\n")

    # Get test case
    if test_name not in ALL_TEST_CASES:
        print(f"Unknown test case: {test_name}")
        print(f"Available tests: {', '.join(ALL_TEST_CASES.keys())}")
        sys.exit(1)

    c_code = ALL_TEST_CASES[test_name]

    print(f"Running test case: {test_name}")
    print()
    print("Input C code:")
    print("-" * 80)
    print(c_code)
    print("-" * 80)
    print()

    result = pipeline.translate(c_code, verbose=True)

    # Show results
    print("\n" + "=" * 80)
    print("TRANSLATION RESULTS")
    print("=" * 80)
    print()
    print(f"Compiled successfully: {result['compiled']}")
    print(f"Refinement iterations: {result['iterations']}")
    print()
    print("Generated Rust code:")
    print("-" * 80)
    print(result['rust_code'])
    print("-" * 80)
    print()

    if not result['compiled'] and result['errors']:
        print("Compilation errors:")
        print("-" * 80)
        print(result['errors'])
        print("-" * 80)
        print()

    return result


def run_all_tests():
    """Run IRENE on all test cases."""
    print("=" * 80)
    print("IRENE Full Test Suite")
    print("=" * 80)
    print()

    lm = setup_llm()
    pipeline = IRENEPipeline(lm_model=lm)

    results = {}
    for name in ALL_TEST_CASES.keys():
        print(f"\n{'=' * 80}")
        print(f"Test: {name}")
        print("=" * 80)

        c_code = ALL_TEST_CASES[name]
        result = pipeline.translate(c_code, verbose=False)

        results[name] = result
        status = "✓ PASS" if result['compiled'] else "✗ FAIL"
        print(f"{status} - {name} (iterations: {result['iterations']})")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    passed = sum(1 for r in results.values() if r['compiled'])
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print()

    for name, result in results.items():
        status = "✓" if result['compiled'] else "✗"
        print(f"  {status} {name}")

    print()


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

    if args.all:
        run_all_tests()
    else:
        run_demo(args.test)
