"""Utilities for rendering pipeline results to human-readable text."""

from __future__ import annotations

from typing import Iterable, List

from .pipeline import TranslationResult


def format_translation_result(result: TranslationResult) -> str:
    lines = []
    comp = result.compilation
    status = "Compiled" if comp.success else "Failed"
    lines.append("=" * 80)
    lines.append("TRANSLATION RESULTS")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Status: {status}")
    lines.append(f"Iterations: {comp.iterations}")
    if comp.errors:
        lines.append("")
        lines.append("Errors:")
        lines.append(comp.errors)
    lines.append("")
    lines.append("Generated Rust code:")
    lines.append("-" * 80)
    lines.append(result.rust_code)
    lines.append("-" * 80)
    lines.append("")
    lines.append("Artifacts:")
    lines.append(f"  Rule hints: {len(result.artifacts.rule_hints)}")
    lines.append(f"  Examples: {len(result.artifacts.examples)}")
    lines.append("  Summary:")
    lines.extend(_indent_block(result.artifacts.summary_text.strip() or "(none)", indent="    "))
    return "\n".join(lines)


def summarize_result_line(name: str, result: TranslationResult) -> str:
    status = "✓" if result.compilation.success else "✗"
    return f"{status} {name} (iterations: {result.compilation.iterations})"


def format_project_translation(results: List[dict]) -> str:
    if not results:
        return "No SCCs translated."
    lines = ["Project Translation Summary:", ""]
    for entry in results:
        translation: TranslationResult = entry["result"]
        header = f"SCC {entry['scc_index']}: {', '.join(entry['declarations'])}"
        lines.append(header)
        lines.append(summarize_result_line(header, translation))
    return "\n".join(lines)


def _indent_block(text: str, indent: str = "  ") -> Iterable[str]:
    if not text:
        yield indent + "(empty)"
        return
    for line in text.splitlines():
        yield f"{indent}{line}"
