#!/usr/bin/env python3
"""
Convenience wrapper for running IRENE from project root.
Delegates to main module.
"""

if __name__ == "__main__":
    import argparse
    from pathlib import Path
    from guardian.llm import build_pipeline
    from guardian.demo import run_demo, run_all_tests, run_project_demo
    from guardian.tests.test_paper_examples import ALL_TEST_CASES

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
    parser.add_argument(
        "--compile-commands",
        type=Path,
        help="Run translation on a compile_commands.json file",
    )
    parser.add_argument(
        "--output-rust",
        type=Path,
        default=Path("project_output.rs"),
        help="When translating a project, write the concatenated Rust to this file (default: project_output.rs)",
    )
    args = parser.parse_args()

    pipeline = build_pipeline()

    if args.compile_commands:
        run_project_demo(pipeline, args.compile_commands, output_path=args.output_rust)
    elif args.all:
        run_all_tests(pipeline)
    else:
        run_demo(pipeline, args.test)
