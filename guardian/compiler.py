import re
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class CompilerOutput:
    success: bool
    output_path: Optional[Path]
    stdout: str
    stderr: str
    command: List[str]

    @property
    def messages(self) -> str:
        return self.stderr if self.stderr else self.stdout


def _default_executable_name() -> str:
    return "a.exe" if os.name == "nt" else "a.out"


def _run_compile(
    args: List[str],
    output_path: Path,
    timeout: int,
    *,
    timeout_message: str,
    not_found_message: str,
) -> CompilerOutput:
    """Run a compiler subprocess, mapping failures to a CompilerOutput."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return CompilerOutput(
            success=False,
            output_path=None,
            stdout="",
            stderr=timeout_message,
            command=args,
        )
    except FileNotFoundError:
        return CompilerOutput(
            success=False,
            output_path=None,
            stdout="",
            stderr=not_found_message,
            command=args,
        )

    return CompilerOutput(
        success=result.returncode == 0,
        output_path=output_path if result.returncode == 0 else None,
        stdout=result.stdout,
        stderr=result.stderr,
        command=args,
    )


class CCompiler:
    def __init__(self, compiler: str = "clang"):
        self.compiler = compiler

    def compile(
        self,
        c_code: str,
        *,
        std: str = "c11",
        extra_args: Optional[List[str]] = None,
        timeout: int = 30,
    ) -> Tuple[bool, str]:
        """
        Compile C code and return (success, errors/output).
        """
        try:
            with tempfile.TemporaryDirectory(prefix="guardian-c-") as tmpdir:
                if self._detect_has_main(c_code):
                    output = self.compile_executable(
                        c_code,
                        Path(tmpdir) / _default_executable_name(),
                        std=std,
                        extra_args=extra_args,
                        timeout=timeout,
                    )
                else:
                    output = self.compile_object(
                        c_code,
                        Path(tmpdir) / "input.o",
                        std=std,
                        extra_args=extra_args,
                        timeout=timeout,
                    )
                return output.success, output.messages
        except Exception as e:
            return False, f"C compilation error: {str(e)}"

    def compile_object(
        self,
        c_code: str,
        output_path: Path,
        *,
        std: str = "c11",
        extra_args: Optional[List[str]] = None,
        timeout: int = 30,
    ) -> CompilerOutput:
        """
        Compile C code to a caller-owned object path.
        """
        return self._compile(
            c_code,
            output_path,
            std=std,
            extra_args=extra_args,
            timeout=timeout,
            object_mode=True,
        )

    def compile_executable(
        self,
        c_code: str,
        output_path: Path,
        *,
        std: str = "c11",
        extra_args: Optional[List[str]] = None,
        timeout: int = 30,
    ) -> CompilerOutput:
        """
        Compile C code to a caller-owned executable path.
        """
        return self._compile(
            c_code,
            output_path,
            std=std,
            extra_args=extra_args,
            timeout=timeout,
            object_mode=False,
        )

    def _compile(
        self,
        c_code: str,
        output_path: Path,
        *,
        std: str,
        extra_args: Optional[List[str]],
        timeout: int,
        object_mode: bool,
    ) -> CompilerOutput:
        """Shared C compilation used by both object and executable targets."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        source_path = output_path.with_suffix(".c")
        source_path.write_text(c_code)

        args = [self.compiler, f"-std={std}"]
        if object_mode:
            args.append("-c")
        args.extend([str(source_path), "-o", str(output_path)])
        if extra_args:
            args.extend(extra_args)

        return _run_compile(
            args,
            output_path,
            timeout,
            timeout_message=f"C compilation timed out after {timeout} seconds",
            not_found_message=f"{self.compiler} not found. Please install clang or configure a C compiler.",
        )

    @staticmethod
    def _detect_has_main(c_code: str) -> bool:
        return re.search(r"\bint\s+main\s*\(", c_code) is not None


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
            with tempfile.TemporaryDirectory(prefix="guardian-rs-") as tmpdir:
                output = self.compile_executable(
                    rust_code,
                    Path(tmpdir) / _default_executable_name(),
                    crate_type=crate_type,
                    extra_args=extra_args,
                    timeout=timeout,
                )

                errors = output.messages
                if errors and not output.success:
                    errors = self._filter_rustc_internal_errors(errors)

                return output.success, errors
        except Exception as e:
            return False, f"Compilation error: {str(e)}"

    def compile_executable(
        self,
        rust_code: str,
        output_path: Path,
        *,
        crate_type: Optional[str] = None,
        extra_args: Optional[List[str]] = None,
        timeout: int = 30,
    ) -> CompilerOutput:
        """
        Compile Rust code to a caller-owned executable path.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        source_path = output_path.with_suffix(".rs")
        source_path.write_text(rust_code)

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

        return _run_compile(
            args,
            output_path,
            timeout,
            timeout_message=f"Compilation timed out after {timeout} seconds",
            not_found_message="rustc not found. Please install Rust: https://rustup.rs/",
        )

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


def check_c_compiler_available(compiler: str = "clang") -> bool:
    try:
        subprocess.run(
            [compiler, "--version"], check=True, timeout=5, capture_output=True
        )
        return True
    except FileNotFoundError:
        return False
