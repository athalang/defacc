"""
IRENE: Integrating Rules and Semantics for LLM-Based C-to-Rust Translation

A DSPy-based framework for translating C code to idiomatic, safe Rust.
"""

from .main import IRENEPipeline
from .rule_analyzer import StaticRuleAnalyzer, RuleHint
from .retriever import ExampleRetriever, TranslationExample
from .compiler import RustCompiler
from .dspy_modules import IRENEModules

__version__ = "0.1.0"
__all__ = [
    "IRENEPipeline",
    "StaticRuleAnalyzer",
    "RuleHint",
    "ExampleRetriever",
    "TranslationExample",
    "RustCompiler",
    "IRENEModules",
]
