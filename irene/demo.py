import sys
from .tests.test_paper_examples import ALL_TEST_CASES

def run_demo(pipeline, test_name: str = "scanf_two_ints"):
    if test_name not in ALL_TEST_CASES:
        print(f"Unknown test case: {test_name}")
        print(f"Available tests: {', '.join(ALL_TEST_CASES.keys())}")
        sys.exit(1)

    c_code = ALL_TEST_CASES[test_name]

    print(f"Running test case: {test_name}")
    print("Input C code:\n")
    print(c_code)

    result = pipeline.translate(c_code, verbose=True)

    if result['errors']:
        print("Translation encountered errors.")
        print(f"Compilation errors: {result['errors']}")
    else:
        print(f"Compiled successfully: {result['compiled']}")
    print(f"Iterations: {result['iterations']}\n")
    print("Generated Rust code:")
    print(result['rust_code'], "\n")

    return result

def run_all_tests(pipeline):
    results = {}
    for name in ALL_TEST_CASES.keys():
        result = run_demo(pipeline, name)
        results[name] = result

    passed = sum(1 for r in results.values() if r['compiled'])
    total = len(results)
    print(f"Passed: {passed}/{total}")

    for name, result in results.items():
        status = "+" if result['compiled'] else "-"
        print(f"{status} {name}")