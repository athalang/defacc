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
    eval_manifest: Path | None = typer.Option(
        None,
        "--eval-manifest",
        help="Prepare or run function-level differential fuzzing evals from a manifest",
    ),
    eval_out: Path = typer.Option(
        Path("artifacts/evals"),
        "--eval-out",
        help="Directory for generated eval artifacts",
    ),
    eval_dry_run: bool = typer.Option(
        False,
        "--eval-dry-run",
        help="Print AFL++ commands without translating or reading corpus files",
    ),
) -> None:
    if not isinstance(eval_manifest, (Path, str)):
        eval_manifest = None
    if not isinstance(eval_out, (Path, str)):
        eval_out = Path("artifacts/evals")
    eval_out = Path(eval_out)
    eval_dry_run = eval_dry_run if isinstance(eval_dry_run, bool) else False

    if eval_manifest and eval_dry_run:
        from guardian.evals.manifest import load_manifest
        from guardian.evals.runner import afl_commands

        for command in afl_commands(load_manifest(Path(eval_manifest)), eval_out):
            print(" ".join(command))
        return

    pipeline = build_pipeline()

    if eval_manifest:
        commands = pipeline.prepare_differential_eval(Path(eval_manifest), eval_out)
        for command in commands:
            print(" ".join(command))
    elif input_c:
        run_file_demo(pipeline, input_c)
    elif all_:
        run_all_tests(pipeline)
    else:
        run_demo(pipeline, test)


def main() -> None:
    typer.run(run)


if __name__ == "__main__":
    main()
