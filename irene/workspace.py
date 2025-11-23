from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple


class RustWorkspace:
    """Persistent scratch file that accumulates translated Rust code."""

    def __init__(self, path: Path, *, reset: bool = True, allow_patch: bool = True):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if reset or not self.path.exists():
            self.path.write_text("", encoding="utf-8")
        if allow_patch:
            self._ensure_patch_available()

    def reset(self) -> None:
        self.path.write_text("", encoding="utf-8")

    def current_text(self) -> str:
        try:
            return self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def write_text(self, data: str) -> None:
        self.path.write_text(data, encoding="utf-8")

    def snapshot(self) -> str:
        return self.current_text()

    def apply_patch(self, patch_text: str) -> Tuple[bool, str]:
        patch = patch_text.strip()
        if not patch:
            return False, "Empty patch"

        with tempfile.NamedTemporaryFile("w+", delete=False) as handle:
            handle.write(patch)
            handle.flush()
            patch_path = handle.name

        try:
            result = subprocess.run(
                ["patch", "-p0", "-i", patch_path],
                cwd=str(self.path.parent),
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return False, result.stderr or result.stdout or "patch command failed"
            return True, ""
        finally:
            Path(patch_path).unlink(missing_ok=True)

    @staticmethod
    def _ensure_patch_available() -> None:
        try:
            subprocess.run(["patch", "--version"], check=True, capture_output=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise RuntimeError("'patch' utility is required for workspace diff application") from exc

    def append_block(self, *, label: Optional[str], code: str) -> None:
        """Append a labeled Rust snippet to the workspace file."""
        snippet = code.strip()
        if not snippet:
            return
        # Skip writing identical snippet to prevent duplicate definitions.
        if snippet in self.current_text():
            return

        needs_padding = self.path.exists() and self.path.stat().st_size > 0
        parts = []
        if needs_padding:
            parts.append("\n\n")
        if label:
            parts.append(f"// {label}\n")
        parts.append(snippet)
        parts.append("\n")

        with self.path.open("a", encoding="utf-8") as handle:
            handle.write("".join(parts))

    def __repr__(self) -> str:  # pragma: no cover - convenience helper
        return f"RustWorkspace(path={self.path!s})"
