from dataclasses import dataclass
from typing import Optional


@dataclass
class CompilationResult:
    success: bool
    iterations: int
    errors: Optional[str]


@dataclass
class TranslationResult:
    rust_code: str
    compilation: CompilationResult
    c_compilation: Optional[CompilationResult] = None
