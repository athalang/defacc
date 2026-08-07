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


if __name__ == "__main__":
    unittest.main()
