"""GUARDIAN: Guarded Universal Architecture for Defensive Interpretation And traNslation."""

from .compiler import CCompiler, RustCompiler
from .pipeline import GUARDIANPipeline
from .translation import CompilationResult, TranslationResult


def build_lm(config=None):
    from .llm import build_lm as _build_lm

    return _build_lm(config)


def build_pipeline(config=None):
    from .llm import build_pipeline as _build_pipeline

    return _build_pipeline(config)


__all__ = [
    "CCompiler",
    "CompilationResult",
    "GUARDIANPipeline",
    "RustCompiler",
    "TranslationResult",
    "build_lm",
    "build_pipeline",
]
