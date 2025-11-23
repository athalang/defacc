import sys
from pathlib import Path
from typing import Optional

from .project_runner import translate_compile_commands
from .reporting import format_project_translation, format_translation_result, summarize_result_line
from .tests.test_paper_examples import ALL_TEST_CASES

def run_demo(pipeline, test_name: str = "scanf_two_ints"):
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
    print()
    print(format_translation_result(result))
    print()
    return result


def run_project_demo(pipeline, compile_commands: str, verbose: bool = True, output_path: Optional[Path] = None):
    path = Path(compile_commands)
    results = translate_compile_commands(
        path,
        pipeline=pipeline,
        verbose=verbose,
        output_rust=output_path,
    )
    print(format_project_translation(results))
    return results


def run_all_tests(pipeline):
    results = {}
    for name in ALL_TEST_CASES.keys():
        print(f"\n{'=' * 80}")
        print(f"Test: {name}")
        print("=" * 80)

        c_code = ALL_TEST_CASES[name]
        result = pipeline.translate(c_code, verbose=False)

        results[name] = result
        print(summarize_result_line(name, result))

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    passed = sum(1 for r in results.values() if r.compilation.success)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print()

    for name, result in results.items():
        status = "✓" if result.compilation.success else "✗"
        print(f"  {status} {name}")

    print()
