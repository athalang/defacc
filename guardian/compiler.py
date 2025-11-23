import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

class RustCompiler:
    def _filter_rustc_internal_errors(self, errors: str) -> str:
        """
        Filter out rustc internal errors that aren't related to user code.

        These errors confuse the LLM and cause it to try to fix rustc issues
        rather than actual code problems.

        Args:
            errors: Raw error output from rustc

        Returns:
            Filtered error output with only user-code-related errors
        """
        # Split into lines
        lines = errors.split('\n')
        filtered_lines = []

        # Patterns to skip
        skip_patterns = [
            r"couldn't create a temp dir",  # rustc internal temp dir issues
            r"Operation not permitted.*at path.*\/dev\/",  # /dev/ permission issues
            r"error: aborting due to \d+ previous error",  # Keep this but it's not harmful
        ]

        skip_next = False
        for i, line in enumerate(lines):
            # Check if this line matches a skip pattern
            should_skip = False
            for pattern in skip_patterns:
                if re.search(pattern, line):
                    # Skip this error and the next few lines that are part of it
                    should_skip = True
                    skip_next = True
                    break

            if should_skip:
                continue

            # Skip empty lines after a filtered error
            if skip_next and not line.strip():
                continue

            skip_next = False
            filtered_lines.append(line)

        return '\n'.join(filtered_lines)

    def compile(
        self,
        rust_code: str,
        *,
        crate_type: Optional[str] = None,
        extra_args: Optional[List[str]] = None,
        timeout: int = 30,
    ) -> Tuple[bool, str]:
        """
        Compile Rust code and return (success, errors/output).

        Args:
            rust_code: The Rust source code to compile

        Returns:
            Tuple of (compilation_success, error_messages)
        """
        try:
            with tempfile.TemporaryDirectory(prefix="irene-rs-") as tmpdir:
                tmp_path = Path(tmpdir)
                source_path = tmp_path / "input.rs"
                source_path.write_text(rust_code)
                output_path = tmp_path / "a.out"

                resolved_crate_type = crate_type or self._detect_crate_type(rust_code)
                args = [
                    "rustc",
                    str(source_path),
                    "--crate-type",
                    resolved_crate_type,
                    "-o",
                    str(output_path),
                ]
                if extra_args:
                    args.extend(extra_args)

                result = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                success = result.returncode == 0
                errors = result.stderr if result.stderr else result.stdout

                if errors and not success:
                    errors = self._filter_rustc_internal_errors(errors)

                return success, errors
        except subprocess.TimeoutExpired:
            return False, f"Compilation timed out after {timeout} seconds"
        except FileNotFoundError:
            return False, "rustc not found. Please install Rust: https://rustup.rs/"
        except Exception as e:
            return False, f"Compilation error: {str(e)}"

    @staticmethod
    def _detect_crate_type(rust_code: str) -> str:
        has_main = re.search(r"\bfn\s+main\s*\(", rust_code) is not None
        return "bin" if has_main else "lib"

def check_rustc_available() -> bool:
    try:
        subprocess.run(
            ["rustc", "--version"], check=True, timeout=5
        )
        return True
    except FileNotFoundError: # rustc not in PATH
        return False
