#!/usr/bin/env python3
"""
Convenience wrapper for running GUARDIAN from project root.
Delegates to main module.
"""

if __name__ == "__main__":
    from pathlib import Path
    from typing import Optional

    import dspy
    import typer

    from guardian.settings import settings
    from guardian.pipeline import GUARDIANPipeline
    from guardian.demo import run_demo, run_all_tests, run_project_demo
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
        compile_commands: Optional[Path] = typer.Option(
            None,
            "--compile-commands",
            help="Run translation on a compile_commands.json file",
        ),
        output_rust: Path = typer.Option(
            Path("project_output.rs"),
            "--output-rust",
            help="When translating a project, write the concatenated Rust to this file (default: project_output.rs)",
        ),
    ) -> None:
        # Configure LLM and create pipeline
        lm = dspy.LM(
            model=settings.model,
            api_base=settings.api_base,
            temperature=settings.temperature,
            api_key=settings.api_key,
        )
        dspy.configure(lm=lm)
        pipeline = GUARDIANPipeline(lm=lm)

        if compile_commands:
            run_project_demo(pipeline, compile_commands, output_path=output_rust)
        elif all_:
            run_all_tests(pipeline)
        else:
            run_demo(pipeline, test)

    typer.run(main)
