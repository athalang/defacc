"""Rust compiler wrapper for validating generated code."""

import subprocess
import tempfile
import re
from pathlib import Path
from typing import Tuple


def strip_markdown_fences(code: str) -> str:
    """
    Strip markdown code fences from code if present.

    Args:
        code: Code that may be wrapped in ```rust ... ``` or ``` ... ```
              Can also handle text before/after the code block.

    Returns:
        Clean code without markdown fences
    """
    # Remove leading/trailing whitespace
    code = code.strip()

    # Pattern to match ```rust or ``` with code and closing ```
    # This searches anywhere in the text, not just at start/end
    pattern = r'```(?:rust)?\s*\n(.*?)\n```'
    match = re.search(pattern, code, re.DOTALL)

    if match:
        # Return the code inside the fences
        return match.group(1).strip()

    # If no fences found, return original code
    return code


def looks_like_rust_code(code: str) -> bool:
    """
    Basic heuristic to check if text looks like Rust code.

    Args:
        code: Text to validate

    Returns:
        True if the text appears to be Rust code, False otherwise
    """
    # Check if the code contains common Rust keywords or patterns
    rust_patterns = [
        r'\bfn\s+\w+',  # function definitions
        r'\buse\s+\w+',  # use statements
        r'\blet\s+\w+',  # variable declarations
        r'\bstruct\s+\w+',  # struct definitions
        r'\bimpl\s+',  # impl blocks
        r'\benum\s+\w+',  # enum definitions
        r'\bpub\s+fn',  # public functions
        r'\bmut\s+\w+',  # mutable variables
    ]

    # Check if at least one pattern matches
    for pattern in rust_patterns:
        if re.search(pattern, code):
            return True

    # Check if code doesn't look like prose (too many common English words)
    # Count lines that start with capital letters (typical of prose)
    lines = code.strip().split('\n')
    prose_lines = sum(1 for line in lines if line.strip() and line.strip()[0].isupper() and not line.strip().startswith('//'))

    # If more than 50% of lines look like prose, it's probably not code
    if lines and (prose_lines / len(lines)) > 0.5:
        return False

    # If code contains Cargo.toml patterns, it's config not code
    if '[package]' in code or '[[bin]]' in code:
        return False

    return True


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
        # Strip markdown code fences if present
        clean_code = strip_markdown_fences(rust_code)

        # Validate that the extracted code looks like Rust
        if not looks_like_rust_code(clean_code):
            return False, "Error: LLM output does not appear to be valid Rust code. The output contains prose, configuration files, or other non-code text."

        # Create a temporary file for the Rust code
        with tempfile.NamedTemporaryFile(mode="w", suffix=".rs", delete=False) as f:
            f.write(clean_code)
            temp_file = Path(f.name)

        try:
            # Detect if code has a main function to determine crate type
            has_main = re.search(r'\bfn\s+main\s*\(', clean_code) is not None
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
