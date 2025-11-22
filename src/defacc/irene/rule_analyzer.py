from dataclasses import dataclass
from typing import List
import re

@dataclass
class RuleHint:
    """A hint about which translation rule to apply."""

    category: str  # "I/O", "Pointers", "Array", "Mixtype"
    code_snippet: str  # The problematic C code pattern
    suggested_rust: str  # How to translate it in Rust
    explanation: str  # Why this pattern needs special handling


class StaticRuleAnalyzer:
    """Analyzes C code to detect patterns requiring special translation rules."""

    def analyze(self, c_code: str) -> List[RuleHint]:
        """Analyze C code and return applicable rule hints."""
        hints = []

        # I/O rules
        hints.extend(self._check_io_patterns(c_code))

        # Pointer rules
        hints.extend(self._check_pointer_patterns(c_code))

        # Array rules
        hints.extend(self._check_array_patterns(c_code))

        # Mixed type rules
        hints.extend(self._check_mixtype_patterns(c_code))

        return hints

    def _check_io_patterns(self, code: str) -> List[RuleHint]:
        """Check for scanf/printf patterns."""
        hints = []

        # scanf with multiple integers
        if re.search(r'scanf\s*\([^)]*%d[^)]*%d', code):
            hints.append(
                RuleHint(
                    category="I/O",
                    code_snippet='scanf("%d%d", &a, &b)',
                    suggested_rust="use read_to_string() + split_whitespace() + parse()",
                    explanation="scanf in C reads formatted input; Rust uses string parsing",
                )
            )

        # printf patterns
        if re.search(r'printf\s*\(', code):
            hints.append(
                RuleHint(
                    category="I/O",
                    code_snippet='printf("...", ...)',
                    suggested_rust='println!("...", ...)',
                    explanation="Use println! macro for formatted output in Rust",
                )
            )

        return hints

    def _check_pointer_patterns(self, code: str) -> List[RuleHint]:
        """Check for malloc/pointer patterns."""
        hints = []

        # malloc calls
        if re.search(r'malloc\s*\(', code):
            hints.append(
                RuleHint(
                    category="Pointers",
                    code_snippet="malloc(n * sizeof(int))",
                    suggested_rust="Vec::with_capacity(n) or Box::new()",
                    explanation="Rust uses Vec<T> for dynamic arrays instead of malloc",
                )
            )

        # pointer arithmetic
        if re.search(r'\*\s*\w+\s*\+\+|\+\+\s*\*\s*\w+', code) or re.search(r'\w+\s*\[\s*\*', code):
            hints.append(
                RuleHint(
                    category="Pointers",
                    code_snippet="ptr++, *ptr",
                    suggested_rust="Use iterators or indexed access with Vec",
                    explanation="Rust prefers safe iteration over pointer arithmetic",
                )
            )

        return hints

    def _check_array_patterns(self, code: str) -> List[RuleHint]:
        """Check for array indexing patterns."""
        hints = []

        # Array indexing with int
        if re.search(r'\w+\s*\[\s*\w+\s*\]', code):
            hints.append(
                RuleHint(
                    category="Array",
                    code_snippet="arr[i]",
                    suggested_rust="arr[i as usize] or use .get(i)",
                    explanation="Rust array indices must be usize; explicit cast required",
                )
            )

        return hints

    def _check_mixtype_patterns(self, code: str) -> List[RuleHint]:
        """Check for mixed integer type patterns."""
        hints = []

        # long long casts
        if re.search(r'\(long\s+long\)', code) or re.search(r'\(int\)', code):
            hints.append(
                RuleHint(
                    category="Mixtype",
                    code_snippet="(long long)x * y",
                    suggested_rust="(x as i64) * (y as i64)",
                    explanation="Rust requires explicit type conversions with 'as'",
                )
            )

        # Mixed arithmetic (int/long/float)
        if re.search(r'(int|long|float|double)\s+\w+.*=.*\*.*[+\-*/]', code):
            hints.append(
                RuleHint(
                    category="Mixtype",
                    code_snippet="mixed type arithmetic",
                    suggested_rust="Use explicit 'as i32', 'as i64', 'as f64' casts",
                    explanation="Rust doesn't perform implicit numeric conversions",
                )
            )

        return hints

def format_hints(hints: List[RuleHint]) -> str:
    """Format rule hints into a string for the LLM."""
    if not hints:
        return "No special translation rules detected."

    formatted = "Translation rules to apply:\n\n"
    for i, hint in enumerate(hints, 1):
        formatted += f"{i}. **{hint.category}**: {hint.explanation}\n"
        formatted += f"   C pattern: `{hint.code_snippet}`\n"
        formatted += f"   Rust approach: {hint.suggested_rust}\n\n"

    return formatted