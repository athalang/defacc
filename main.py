#!/usr/bin/env python3
"""
Convenience wrapper for running GUARDIAN from project root.
Delegates to main module.
"""

if __name__ == "__main__":
    from pathlib import Path

    import typer

    from guardian.demo import run_demo, run_all_tests, run_file_demo
    from guardian.llm import build_pipeline
    from guardian.tests.test_paper_examples import ALL_TEST_CASES

    def main(
        test: str = typer.Option(
            "scanf_two_ints",
            "--test",
            help=f"Test case to run (choices: {', '.join(ALL_TEST_CASES.keys())})",
        ),
        all_: bool = typer.Option(
            False,
            "--all",
            help="Run all test cases",
        ),
        input_c: Path | None = typer.Option(
            None,
            "--input-c",
            help="Translate one C source file using single-file SCC ordering",
        ),
    ) -> None:
        # Configure LLM and create pipeline
        pipeline = build_pipeline()

        if input_c:
            run_file_demo(pipeline, input_c)
        elif all_:
            run_all_tests(pipeline)
        else:
            run_demo(pipeline, test)

    typer.run(main)
