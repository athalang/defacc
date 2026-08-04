"""Utilities for rendering pipeline results to human-readable text."""

from __future__ import annotations

from typing import List

from .pipeline import TranslationResult


def format_translation_result(result: TranslationResult) -> str:
    lines = []
    comp = result.compilation
    status = "Compiled" if comp.success else "Failed"
    c_comp = result.c_compilation
    c_status = "Compiled" if c_comp and c_comp.success else "Failed"
    lines.append("=" * 80)
    lines.append("TRANSLATION RESULTS")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"C Status: {c_status}")
    lines.append(f"Status: {status}")
    lines.append(f"Iterations: {comp.iterations}")
    if c_comp and c_comp.errors:
        lines.append("")
        lines.append("C Errors:")
        lines.append(c_comp.errors)
    if comp.errors:
        lines.append("")
        lines.append("Rust Errors:")
        lines.append(comp.errors)
    lines.append("")
    lines.append("Generated Rust code:")
    lines.append("-" * 80)
    lines.append(result.rust_code)
    lines.append("-" * 80)
    return "\n".join(lines)


def format_result_line(name: str, result: TranslationResult) -> str:
    status = "✓" if result.compilation.success else "✗"
    c_status = "✓" if result.c_compilation and result.c_compilation.success else "✗"
    return f"{status} {name} (c: {c_status}, rust iterations: {result.compilation.iterations})"


def format_project_translation(results: List[dict]) -> str:
    if not results:
        return "No SCCs translated."
    lines = ["Project Translation Results:", ""]
    for entry in results:
        translation: TranslationResult = entry["result"]
        header = f"SCC {entry['scc_index']}: {', '.join(entry['declarations'])}"
        lines.append(format_result_line(header, translation))
    return "\n".join(lines)

