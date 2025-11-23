"""
Libclang helpers shared across analysis utilities.
"""

import os
from pathlib import Path
from typing import Generator, List, Optional, Set

from clang.cindex import Cursor, CursorKind, TokenKind, TranslationUnit, Index


class LibclangContext:
    """
    Thin wrapper around libclang parsing and common cursor helpers.
    """

    def __init__(self, clang_args: Optional[List[str]] = None, source_filename: str = "input.c"):
        self.clang_args = clang_args or ["-xc", "-std=c11"]
        self.source_filename = source_filename
        self.index = Index.create()

    def parse_translation_unit(self, c_code: str) -> TranslationUnit:
        try:
            return self.index.parse(
                self.source_filename,
                args=self.clang_args,
                unsaved_files=[(self.source_filename, c_code)],
                options=TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD,
            )
        except Exception as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"Failed to parse C code with libclang: {exc}") from exc

    def is_in_source_file(self, cursor: Cursor) -> bool:
        loc = cursor.location
        return bool(
            loc
            and loc.file
            and os.path.abspath(loc.file.name) == os.path.abspath(self.source_filename)
        )

    def walk_relevant_nodes(self, cursor: Cursor) -> Generator[Cursor, None, None]:
        """Yield AST nodes that belong to the configured source file."""
        stack = [cursor]
        while stack:
            node = stack.pop()
            if node.location and node.location.file and not self.is_in_source_file(node):
                continue
            yield node
            stack.extend(reversed(list(node.get_children())))

    def get_called_function_name(self, cursor: Cursor) -> str:
        """Best-effort extraction of a function name from a call expression."""
        if cursor.spelling:
            return cursor.spelling

        for child in cursor.get_children():
            if child.kind == CursorKind.DECL_REF_EXPR and child.spelling:
                return child.spelling

        for token in cursor.get_tokens():
            if token.kind == TokenKind.IDENTIFIER:
                return token.spelling

        return ""


def normalize_path(name: str) -> str:
    """Return a normalized absolute path; fallback to raw name on failure."""
    try:
        return str(Path(name).resolve())
    except Exception:
        return name


def normalize_identifier(name: str) -> str:
    """Strip common C prefixes like 'struct ', 'enum ' for stable matching."""
    for prefix in ("struct ", "enum ", "union ", "class ", "typedef "):
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def cursor_in_files(cursor: Cursor, target_files: Set[str]) -> bool:
    """Return True when a cursor belongs to one of the allowed files."""
    loc = cursor.location
    return bool(
        loc
        and loc.file
        and normalize_path(loc.file.name) in target_files
    )


def extract_source(cursor: Cursor, c_code: str, target_files: Set[str]) -> str:
    """Return the source text for a cursor extent within allowed files."""
    if not cursor or not cursor.extent:
        return ""

    start = cursor.extent.start
    end = cursor.extent.end

    if not (
        start.file
        and end.file
        and normalize_path(start.file.name) in target_files
        and normalize_path(end.file.name) in target_files
    ):
        return ""

    lines = c_code.splitlines()
    if start.line < 1 or end.line > len(lines):
        return ""

    slice_lines = lines[start.line - 1 : end.line]
    if not slice_lines:
        return ""

    slice_lines[0] = slice_lines[0][start.column - 1 :]
    slice_lines[-1] = slice_lines[-1][: end.column - 1]

    return "\n".join(slice_lines).strip("\n")


def stable_cursor_id(cursor: Cursor, name: str, path: str) -> str:
    """
    Build a stable identifier for a cursor using USR when available, otherwise fallback to file:line:col.
    """
    usr = cursor.get_usr() or ""
    if usr:
        return usr
    loc = cursor.location
    line = loc.line if loc else "?"
    col = loc.column if loc else "?"
    return f"{path}::{name}@{line}:{col}"


def cursor_kind_slug(kind) -> str:
    """
    Return a lowercase descriptive name for a CursorKind that is stable across libclang versions.
    """
    name = getattr(kind, "name", None) or getattr(kind, "spelling", None)
    if not name:
        name = str(kind)
    return name.lower().replace("_decl", "")
