from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Set
from clang.cindex import Cursor, CursorKind, TokenKind, TranslationUnit, TypeKind, Index

@dataclass
class RuleHint:
    category: str  # "I/O", "Pointers", "Array", "Mixtype"
    code_snippet: str  # The problematic C code pattern
    suggested_rust: str  # How to translate it in Rust
    explanation: str  # Why this pattern needs special handling

class StaticRuleAnalyzer:
    def __init__(self, clang_args: Optional[List[str]] = None):
        """
        Rule analyzer with optional libclang AST generation support.

        Args:
            clang_args: Extra arguments passed to libclang when parsing code.
        """
        self.clang_args = clang_args or ["-xc", "-std=c11"]

    def analyze(self, c_code: str) -> List[RuleHint]:
        """Analyze C code and return applicable rule hints using libclang."""
        translation_unit = self._parse_translation_unit(c_code)
        root_cursor = translation_unit.cursor

        hints = []
        hints.extend(self._check_io_patterns(root_cursor))
        hints.extend(self._check_pointer_patterns(root_cursor))
        hints.extend(self._check_array_patterns(root_cursor))
        hints.extend(self._check_mixtype_patterns(root_cursor))

        return hints

    def generate_libclang_ast(
        self,
        c_code: str,
        max_depth: int = 8,
        include_attributes: bool = False,
    ) -> Dict[str, Any]:
        """
        Produce a libclang AST for a C code snippet without writing to disk.

        Args:
            c_code: C source code to parse.
            max_depth: Maximum recursion depth when walking the AST.
            include_attributes: Include cursor attributes (e.g., is_const) when True.

        Returns:
            Dict representation of the AST rooted at the translation unit cursor.
        """

        try:
            index = Index.create()
            translation_unit = index.parse(
                "input.c",
                args=self.clang_args,
                unsaved_files=[("input.c", c_code)],
                options=TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD,
            )
        except Exception as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"Failed to parse C code with libclang: {exc}") from exc

        def cursor_to_dict(cursor: Cursor, depth: int = 0) -> Optional[Dict[str, Any]]:
            if depth > max_depth:
                return None

            # Only include nodes belonging to our in-memory file
            if cursor.location and cursor.location.file and cursor.location.file.name != "input.c":
                return None

            children = []
            for child in cursor.get_children():
                child_dict = cursor_to_dict(child, depth + 1)
                if child_dict:
                    children.append(child_dict)

            node = {
                "kind": cursor.kind.spelling,
                "spelling": cursor.spelling or "",
                "type": cursor.type.spelling if cursor.type else "",
                "location": {
                    "line": cursor.location.line,
                    "column": cursor.location.column,
                }
                if cursor.location
                else None,
                "children": children,
            }

            if include_attributes:
                node["is_const"] = cursor.is_const_qualified_type()
                node["is_definition"] = cursor.is_definition()

            return node

        return cursor_to_dict(translation_unit.cursor) or {}

    def _parse_translation_unit(self, c_code: str) -> TranslationUnit:
        """Parse C code into a libclang TranslationUnit."""
        try:
            index = Index.create()
            return index.parse(
                "input.c",
                args=self.clang_args,
                unsaved_files=[("input.c", c_code)],
                options=TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD,
            )
        except Exception as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"Failed to parse C code with libclang: {exc}") from exc

    def _walk_relevant_nodes(self, cursor: Cursor) -> Generator[Cursor, None, None]:
        """Yield AST nodes that belong to the in-memory file."""
        stack = [cursor]
        while stack:
            node = stack.pop()
            if (
                node.location
                and node.location.file
                and node.location.file.name != "input.c"
            ):
                continue
            yield node
            stack.extend(reversed(list(node.get_children())))

    def _get_called_function_name(self, cursor: Cursor) -> str:
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

    def _is_numeric_type(self, type_kind: TypeKind) -> bool:
        """Return True when type_kind represents a numeric scalar."""
        numeric_kinds = {
            TypeKind.BOOL,
            TypeKind.CHAR_U,
            TypeKind.UCHAR,
            TypeKind.USHORT,
            TypeKind.UINT,
            TypeKind.ULONG,
            TypeKind.ULONGLONG,
            TypeKind.CHAR_S,
            TypeKind.SCHAR,
            TypeKind.WCHAR,
            TypeKind.SHORT,
            TypeKind.INT,
            TypeKind.LONG,
            TypeKind.LONGLONG,
            TypeKind.FLOAT,
            TypeKind.DOUBLE,
            TypeKind.LONGDOUBLE,
        }
        return type_kind in numeric_kinds

    def _is_pointer_arithmetic(self, cursor: Cursor) -> bool:
        """Detect simple pointer arithmetic (increment/decrement or +/- with integers)."""
        if cursor.kind == CursorKind.UNARY_OPERATOR:
            tokens = {token.spelling for token in cursor.get_tokens()}
            if "++" in tokens or "--" in tokens:
                children = list(cursor.get_children())
                target = children[0] if children else None
                return bool(target and target.type and target.type.kind == TypeKind.POINTER)

        if cursor.kind == CursorKind.BINARY_OPERATOR:
            tokens = [token.spelling for token in cursor.get_tokens()]
            if "+" in tokens or "-" in tokens:
                children = list(cursor.get_children())
                if len(children) == 2:
                    lhs, rhs = children
                    lhs_is_ptr = lhs.type and lhs.type.kind == TypeKind.POINTER
                    rhs_is_ptr = rhs.type and rhs.type.kind == TypeKind.POINTER
                    return lhs_is_ptr or rhs_is_ptr

        return False

    def _is_arithmetic_operator(self, cursor: Cursor) -> bool:
        """Check if a binary operator cursor represents arithmetic (+, -, *, /)."""
        if cursor.kind != CursorKind.BINARY_OPERATOR:
            return False
        ops = {token.spelling for token in cursor.get_tokens()}
        return bool({"+" , "-", "*", "/"}.intersection(ops))

    def _check_io_patterns(self, root: Cursor) -> List[RuleHint]:
        hints: List[RuleHint] = []
        detected: Set[str] = set()

        for node in self._walk_relevant_nodes(root):
            if node.kind != CursorKind.CALL_EXPR:
                continue

            func_name = self._get_called_function_name(node)
            if func_name == "scanf" and "scanf" not in detected:
                hints.append(
                    RuleHint(
                        category="I/O",
                        code_snippet='scanf("%d%d", &a, &b)',
                        suggested_rust="use read_to_string() + split_whitespace() + parse()",
                        explanation="scanf in C reads formatted input; Rust uses string parsing",
                    )
                )
                detected.add("scanf")

            if func_name == "printf" and "printf" not in detected:
                hints.append(
                    RuleHint(
                        category="I/O",
                        code_snippet='printf("...", ...)',
                        suggested_rust='println!("...", ...)',
                        explanation="Use println! macro for formatted output in Rust",
                    )
                )
                detected.add("printf")

        return hints

    def _check_pointer_patterns(self, root: Cursor) -> List[RuleHint]:
        """Check for malloc/pointer patterns using the AST."""
        hints: List[RuleHint] = []
        detected: Set[str] = set()

        for node in self._walk_relevant_nodes(root):
            if node.kind == CursorKind.CALL_EXPR:
                if self._get_called_function_name(node) == "malloc" and "malloc" not in detected:
                    hints.append(
                        RuleHint(
                            category="Pointers",
                            code_snippet="malloc(n * sizeof(int))",
                            suggested_rust="Vec::with_capacity(n) or Box::new()",
                            explanation="Rust uses Vec<T> for dynamic arrays instead of malloc",
                        )
                    )
                    detected.add("malloc")

            if self._is_pointer_arithmetic(node) and "pointer_arith" not in detected:
                hints.append(
                    RuleHint(
                        category="Pointers",
                        code_snippet="ptr++, *ptr",
                        suggested_rust="Use iterators or indexed access with Vec",
                        explanation="Rust prefers safe iteration over pointer arithmetic",
                    )
                )
                detected.add("pointer_arith")

        return hints

    def _check_array_patterns(self, root: Cursor) -> List[RuleHint]:
        """Check for array indexing patterns using ArraySubscriptExpr nodes."""
        hints: List[RuleHint] = []
        for node in self._walk_relevant_nodes(root):
            if node.kind == CursorKind.ARRAY_SUBSCRIPT_EXPR:
                hints.append(
                    RuleHint(
                        category="Array",
                        code_snippet="arr[i]",
                        suggested_rust="arr[i as usize] or use .get(i)",
                        explanation="Rust array indices must be usize; explicit cast required",
                    )
                )
                break
        return hints

    def _check_mixtype_patterns(self, root: Cursor) -> List[RuleHint]:
        """Check for mixed integer type patterns using the AST."""
        hints: List[RuleHint] = []
        detected: Set[str] = set()

        for node in self._walk_relevant_nodes(root):
            if node.kind == CursorKind.CSTYLE_CAST_EXPR:
                target_kind = node.type.kind if node.type else None
                if target_kind in {TypeKind.LONGLONG, TypeKind.LONG, TypeKind.INT} and "casts" not in detected:
                    hints.append(
                        RuleHint(
                            category="Mixtype",
                            code_snippet="(long long)x * y",
                            suggested_rust="(x as i64) * (y as i64)",
                            explanation="Rust requires explicit type conversions with 'as'",
                        )
                    )
                    detected.add("casts")

            if node.kind == CursorKind.BINARY_OPERATOR and self._is_arithmetic_operator(node):
                children = list(node.get_children())
                if len(children) == 2:
                    lhs, rhs = children
                    if (
                        lhs.type
                        and rhs.type
                        and self._is_numeric_type(lhs.type.kind)
                        and self._is_numeric_type(rhs.type.kind)
                        and lhs.type.kind != rhs.type.kind
                        and "mixed_arith" not in detected
                    ):
                        hints.append(
                            RuleHint(
                                category="Mixtype",
                                code_snippet="mixed type arithmetic",
                                suggested_rust="Use explicit 'as i32', 'as i64', 'as f64' casts",
                                explanation="Rust doesn't perform implicit numeric conversions",
                            )
                        )
                        detected.add("mixed_arith")

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
