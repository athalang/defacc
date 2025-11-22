import subprocess
import tempfile
import re
from pathlib import Path
from typing import Tuple

class RustCompiler:
    """Wrapper for rustc to compile and validate Rust code."""

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

    def compile(self, rust_code: str) -> Tuple[bool, str]:
        """
        Compile Rust code and return (success, errors/output).

        Args:
            rust_code: The Rust source code to compile

        Returns:
            Tuple of (compilation_success, error_messages)
        """
        # Create a temporary file for the Rust code
        with tempfile.NamedTemporaryFile(mode="w", suffix=".rs", delete=False) as f:
            f.write(rust_code)
            temp_file = Path(f.name)

        try:
            # Detect if code has a main function to determine crate type
            has_main = re.search(r'\bfn\s+main\s*\(', rust_code) is not None
            crate_type = "bin" if has_main else "lib"

            # Create temp output file for binary
            with tempfile.NamedTemporaryFile(delete=False) as out_file:
                output_path = out_file.name

            # Run rustc
            result = subprocess.run(
                ["rustc", str(temp_file), "--crate-type", crate_type, "-o", output_path],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Clean up output file
            try:
                Path(output_path).unlink()
            except Exception:
                pass

            success = result.returncode == 0
            errors = result.stderr if result.stderr else result.stdout

            # Filter out rustc internal errors that confuse the LLM
            if errors and not success:
                errors = self._filter_rustc_internal_errors(errors)

            return success, errors

        except subprocess.TimeoutExpired:
            return False, "Compilation timed out after 30 seconds"
        except FileNotFoundError:
            return False, "rustc not found. Please install Rust: https://rustup.rs/"
        except Exception as e:
            return False, f"Compilation error: {str(e)}"
        finally:
            # Clean up temp file
            try:
                temp_file.unlink()
            except Exception:
                pass


def check_rustc_available() -> bool:
    """Check if rustc is available in the system."""
    try:
        result = subprocess.run(
            ["rustc", "--version"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False
