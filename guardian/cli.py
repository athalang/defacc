from pathlib import Path

import typer

from guardian.demo import run_all_tests, run_demo, run_file_demo
from guardian.examples.paper_cases import ALL_TEST_CASES
from guardian.llm import build_pipeline


def run(
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
    pipeline = build_pipeline()

    if input_c:
        run_file_demo(pipeline, input_c)
    elif all_:
        run_all_tests(pipeline)
    else:
        run_demo(pipeline, test)


def main() -> None:
    typer.run(run)
