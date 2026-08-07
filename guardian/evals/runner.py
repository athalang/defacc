"""CLI runner for function-level differential fuzzing evals."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from guardian.llm import build_lm
from guardian.pipeline import GUARDIANPipeline

from .classification import FindingClass
from .harness import write_harness
from .manifest import EvalCase, load_manifest

if TYPE_CHECKING:
    from guardian.pipeline import GUARDIANPipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m guardian.evals")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="translate cases and generate harness artifacts")
    prepare.add_argument("--manifest", type=Path, required=True)
    prepare.add_argument("--out", type=Path, required=True)

    run = subparsers.add_parser("run", help="prepare artifacts and execute AFL++ commands")
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--budget-seconds", type=int, default=60)
    run.add_argument("--dry-run", action="store_true")

    report = subparsers.add_parser("report", help="summarize classified finding JSON files")
    report.add_argument("--findings", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "prepare":
        pipeline = GUARDIANPipeline(lm=build_lm())
        prepare_cases(load_manifest(args.manifest), args.out, pipeline=pipeline)
        return 0
    if args.command == "run":
        cases = load_manifest(args.manifest)
        if args.dry_run:
            for command in afl_commands(cases, args.out):
                print(" ".join(command))
            return 0
        pipeline = GUARDIANPipeline(lm=build_lm())
        commands = prepare_cases(cases, args.out, pipeline=pipeline)
        for command in commands:
            subprocess.run(command, check=True, timeout=args.budget_seconds + 30)
        return 0
    if args.command == "report":
        print(json.dumps(summarize_findings(args.findings), indent=2))
        return 0
    raise AssertionError(f"unhandled command {args.command}")


def prepare_cases(
    cases: list[EvalCase],
    output_root: Path,
    *,
    pipeline: "GUARDIANPipeline",
    verbose: bool = False,
) -> list[list[str]]:
    """Translate and generate harness artifacts for each case."""
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    commands: list[list[str]] = []

    for case in cases:
        case_dir = output_root / case.id
        case_dir.mkdir(parents=True, exist_ok=True)
        write_harness(case, case_dir)

        c_source = case.c_file.read_text(errors="ignore")
        (case_dir / "source.c").write_text(c_source)
        translation = pipeline.translate(c_source, verbose=verbose)
        (case_dir / "translation.rs").write_text(translation.rust_code)
        (case_dir / "translation_meta.json").write_text(
            json.dumps(
                {
                    "c_compiled": translation.c_compilation.success
                    if translation.c_compilation
                    else False,
                    "rust_compiled": translation.compilation.success,
                    "iterations": translation.compilation.iterations,
                    "errors": translation.compilation.errors,
                },
                indent=2,
            )
            + "\n"
        )

        commands.append(_afl_command(case, case_dir, output_root))
    return commands


def afl_commands(cases: list[EvalCase], output_root: Path) -> list[list[str]]:
    """Return AFL++ commands without translating or touching corpus files."""
    output_root = Path(output_root)
    return [
        _afl_command(case, output_root / case.id, output_root)
        for case in cases
    ]


def summarize_findings(findings_dir: Path) -> dict[str, int]:
    """Summarize persisted classified finding JSON files."""
    counts = {classification.value: 0 for classification in FindingClass}
    for path in Path(findings_dir).glob("**/*.json"):
        data = json.loads(path.read_text())
        classification = data.get("classification")
        if classification in counts:
            counts[classification] += 1
    return counts


def _afl_command(case: EvalCase, case_dir: Path, output_root: Path) -> list[str]:
    # The Docker image provides build_case.sh; keeping command construction here makes dry-runs testable.
    return [
        "bash",
        "/opt/guardian-evals/build_and_fuzz_case.sh",
        str(case_dir),
        str(output_root / "afl-out" / case.id),
        str(case.timeout_ms),
    ]


if __name__ == "__main__":
    raise SystemExit(main())
