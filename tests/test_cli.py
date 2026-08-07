import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from guardian.translation import CompilationResult, TranslationResult


class FakePipeline:
    def translate(self, c_code: str, verbose: bool = True) -> TranslationResult:
        return TranslationResult(
            rust_code="fn main() {}",
            compilation=CompilationResult(success=True, iterations=1, errors=None),
            c_compilation=CompilationResult(success=True, iterations=1, errors=None),
        )

    def translate_file(self, source_path, verbose: bool = True) -> list[dict]:
        return []


class CliTests(unittest.TestCase):
    def test_run_uses_demo_pipeline_for_named_case(self) -> None:
        from guardian.cli import run

        with patch("guardian.cli.build_pipeline", return_value=FakePipeline()):
            with redirect_stdout(StringIO()):
                run(test="scanf_two_ints", all_=False, input_c=None)

    def test_run_prints_eval_dry_run_without_building_pipeline(self) -> None:
        from pathlib import Path
        import tempfile
        import json

        from guardian.cli import run

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "cases.json"
            manifest.write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "id": "external-add",
                                "source": "csmith",
                                "source_case_id": "seed-1",
                                "c_file": "missing.c",
                                "function": "target",
                                "args": [],
                                "return_type": "int",
                            }
                        ]
                    }
                )
            )

            with patch("guardian.cli.build_pipeline") as build_pipeline:
                output = StringIO()
                with redirect_stdout(output):
                    run(eval_manifest=manifest, eval_out=Path(tmp) / "out", eval_dry_run=True)

        build_pipeline.assert_not_called()
        self.assertIn("/opt/guardian-evals/build_and_fuzz_case.sh", output.getvalue())


if __name__ == "__main__":
    unittest.main()
