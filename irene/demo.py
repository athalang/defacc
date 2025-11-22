import sys
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

def run_all_tests(pipeline):
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