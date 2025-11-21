"""Demo script for IRENE C-to-Rust translation framework.

This script demonstrates how to use IRENE with a configured language model.
You need to set up your LLM credentials before running this.
"""

import sys
import os
import dspy
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from main import IRENEPipeline
from tests.test_paper_examples import ALL_TEST_CASES


def setup_llm():
    """
    Set up the language model for DSPy.

    You need to configure this based on your chosen LLM provider.

    Examples:
        # OpenAI (requires OPENAI_API_KEY environment variable)
        lm = dspy.LM('openai/gpt-4', cache=False)

        # Anthropic Claude (requires ANTHROPIC_API_KEY environment variable)
        lm = dspy.LM('anthropic/claude-3-5-sonnet-20241022', cache=False)

        # Local model via Ollama
        lm = dspy.LM('ollama/mistral', api_base='http://localhost:11434', cache=False)
    """
    print("Configuring language model...")
    print()

    # Try to detect available API keys
    if os.getenv("ANTHROPIC_API_KEY"):
        print("✓ Found ANTHROPIC_API_KEY - using Claude 3.5 Sonnet")
        lm = dspy.LM('anthropic/claude-3-5-sonnet-20241022', cache=False)
    elif os.getenv("OPENAI_API_KEY"):
        print("✓ Found OPENAI_API_KEY - using GPT-4")
        lm = dspy.LM('openai/gpt-4', cache=False)
    elif model_name := os.getenv("IRENE_MODEL"):
        print(f"✓ Found IRENE_MODEL - using {model_name}")
        lm = dspy.LM(model_name, api_base='http://localhost:11434')
    else:
        print("✗ No API keys found, and no local model set!")
        print()
        print("Please set one of the following environment variables:")
        print("  export ANTHROPIC_API_KEY='your-key-here'")
        print("  export OPENAI_API_KEY='your-key-here'")
        print("  export IRENE_MODEL='ollama/mistral' # or another local model")
        print()
        sys.exit(1)

    return lm


def run_demo(test_name: str = "scanf_two_ints"):
    """Run IRENE demo on a specific test case."""
    print("=" * 80)
    print("IRENE C-to-Rust Translation Demo")
    print("=" * 80)
    print()

    # Setup LLM
    lm = setup_llm()

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

    # Run translation
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
