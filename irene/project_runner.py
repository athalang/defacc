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
    results = active_pipeline.translate_project(path, verbose=verbose, workspace_path=output_rust)

    if output_rust and verbose:
        print(f"\nAccumulated Rust output written to {Path(output_rust)}")

    return results
