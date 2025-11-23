"""Helpers for translating entire projects using compile_commands.json."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .llm import LMConfig, build_pipeline
from .pipeline import IRENEPipeline


def translate_compile_commands(
    compile_commands: Path,
    *,
    pipeline: Optional[IRENEPipeline] = None,
    lm_config: Optional[LMConfig] = None,
    verbose: bool = True,
    output_rust: Optional[Path] = None,
) -> List[dict]:
    """
    Run the SCC-aware translation pipeline for a compilation database.
    """
    path = Path(compile_commands)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Generate compile_commands.json first.")

    active_pipeline = pipeline or build_pipeline(lm_config)
    results = active_pipeline.translate_project(path, verbose=verbose)

    if output_rust:
        concatenated = "\n\n".join(entry["result"].rust_code for entry in results)
        output_rust = Path(output_rust)
        output_rust.write_text(concatenated)
        if verbose:
            print(f"\nWrote concatenated Rust output to {output_rust}")

    return results
