import json
import importlib.resources as resources
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
from clang.cindex import Cursor, CursorKind, TypeKind

from irene.clang_utils import LibclangContext, cursor_kind_slug

@dataclass
class RuleHint:
    category: str  # "I/O", "Pointers", "Array", "Mixtype"
    code_snippet: str  # The problematic C code pattern
    suggested_rust: str  # How to translate it in Rust
    explanation: str  # Why this pattern needs special handling

@dataclass(frozen=True)
class HintDefinition:
    key: str
    bucket: str
    hint: Dict[str, str]
    kinds: Tuple[CursorKind, ...]
    call_name: Optional[str] = None
    predicate: Optional[str] = None
    required: bool = True

BUCKET_ORDER: Tuple[str, ...] = ("io", "pointer", "array", "mixtype")
def _load_hint_definitions() -> Tuple[HintDefinition, ...]:
    data_path = resources.files("irene.data").joinpath("rule_hints.json")
    with data_path.open("r", encoding="utf-8") as fh:
        raw_definitions = json.load(fh)

    definitions: List[HintDefinition] = []
    for item in raw_definitions:
        kinds = tuple(getattr(CursorKind, kind) for kind in item.get("kinds", []))
        definitions.append(
            HintDefinition(
                key=item["key"],
                bucket=item["bucket"],
                hint=item["hint"],
                kinds=kinds,
                call_name=item.get("call_name"),
                predicate=item.get("predicate"),
                required=item.get("required", True),
            )
        )
    return tuple(definitions)


HINT_DEFINITIONS: Tuple[HintDefinition, ...] = _load_hint_definitions()
HINTS_BY_KIND: Dict[CursorKind, List[HintDefinition]] = {}
for _definition in HINT_DEFINITIONS:
    for _kind in _definition.kinds:
        HINTS_BY_KIND.setdefault(_kind, []).append(_definition)
del _definition, _kind
REQUIRED_KEYS_BY_BUCKET = {
    bucket: {
        definition.key
        for definition in HINT_DEFINITIONS
        if definition.bucket == bucket and definition.required
    }
    for bucket in BUCKET_ORDER
}

class StaticRuleAnalyzer:
    BUCKET_ORDER = BUCKET_ORDER
    HINT_DEFINITIONS = HINT_DEFINITIONS
    HINTS_BY_KIND = HINTS_BY_KIND
    REQUIRED_KEYS = REQUIRED_KEYS_BY_BUCKET

    def __init__(
        self,
        clang_args: Optional[List[str]] = None,
        source_filename: str = "input.c",
        clang: Optional[LibclangContext] = None,
    ):
        """
        Rule analyzer with optional libclang AST generation support.

        Args:
            clang_args: Extra arguments passed to libclang when parsing code.
            source_filename: Filename used by libclang (use the real path for on-disk files).
            clang: Pre-configured LibclangContext to reuse (takes precedence over args).
        """
        self.clang = self._resolve_context(clang, clang_args, source_filename)

    def analyze(self, c_code: str) -> List[RuleHint]:
        """Analyze C code and return applicable rule hints using libclang."""
        translation_unit = self.clang.parse_translation_unit(c_code)
        return self.analyze_translation_unit(translation_unit)

    def analyze_translation_unit(self, translation_unit) -> List[RuleHint]:
        """Analyze an existing translation unit without reparsing."""
        root_cursor = translation_unit.cursor
        return self._collect_rule_hints(root_cursor)

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
            translation_unit = self.clang.parse_translation_unit(c_code)
        except Exception as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"Failed to parse C code with libclang: {exc}") from exc

        def cursor_to_dict(cursor: Cursor, depth: int = 0) -> Optional[Dict[str, Any]]:
            if depth > max_depth:
                return None

            # Only include nodes belonging to our in-memory file
            if cursor.location and cursor.location.file and not self.clang.is_in_source_file(cursor):
                return None

            children = []
            for child in cursor.get_children():
                child_dict = cursor_to_dict(child, depth + 1)
                if child_dict:
                    children.append(child_dict)

            node = {
                "kind": cursor_kind_slug(cursor.kind),
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

    def _resolve_context(
        self,
        clang: Optional[LibclangContext],
        clang_args: Optional[List[str]],
        source_filename: str,
    ) -> LibclangContext:
        """Return an existing LibclangContext or create one using shared defaults."""
        if clang is not None:
            return clang
        return LibclangContext(
            clang_args=clang_args or ["-xc", "-std=c11"],
            source_filename=source_filename,
        )

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

    def _is_integer_cast(self, cursor: Cursor) -> bool:
        """Return True when a cast targets a common signed integer type."""
        if cursor.kind != CursorKind.CSTYLE_CAST_EXPR or not cursor.type:
            return False
        return cursor.type.kind in {TypeKind.LONGLONG, TypeKind.LONG, TypeKind.INT}

    def _is_arithmetic_operator(self, cursor: Cursor) -> bool:
        """Check if a binary operator cursor represents arithmetic (+, -, *, /)."""
        if cursor.kind != CursorKind.BINARY_OPERATOR:
            return False
        ops = {token.spelling for token in cursor.get_tokens()}
        return bool({"+" , "-", "*", "/"}.intersection(ops))

    def _call_matches(self, cursor: Cursor, target: str) -> bool:
        """Return True when cursor is a call expression matching the given name."""
        return cursor.kind == CursorKind.CALL_EXPR and self.clang.get_called_function_name(cursor) == target

    def _rule_hint_from_template(self, template: Dict[str, str]) -> RuleHint:
        """Instantiate a RuleHint from a template dictionary."""
        return RuleHint(
            category=template["category"],
            code_snippet=template["code_snippet"],
            suggested_rust=template["suggested_rust"],
            explanation=template["explanation"],
        )

    def _is_mixed_numeric_arithmetic(self, cursor: Cursor) -> bool:
        """Detect binary arithmetic where operand numeric kinds differ."""
        if cursor.kind != CursorKind.BINARY_OPERATOR or not self._is_arithmetic_operator(cursor):
            return False
        children = list(cursor.get_children())
        if len(children) != 2:
            return False
        lhs, rhs = children
        return (
            lhs.type
            and rhs.type
            and self._is_numeric_type(lhs.type.kind)
            and self._is_numeric_type(rhs.type.kind)
            and lhs.type.kind != rhs.type.kind
        )

    def _requirements_satisfied(self, detected: Dict[str, Set[str]]) -> bool:
        """Return True when all buckets have met their minimum keys."""
        for bucket, required in self.REQUIRED_KEYS.items():
            if not required.issubset(detected.get(bucket, set())):
                return False
        return True

    def _collect_rule_hints(self, root: Cursor) -> List[RuleHint]:
        """Traverse the AST once and collect all rule hints."""
        buckets: Dict[str, List[RuleHint]] = {bucket: [] for bucket in self.BUCKET_ORDER}
        detected: Dict[str, Set[str]] = {bucket: set() for bucket in self.BUCKET_ORDER}

        for node in self.clang.walk_relevant_nodes(root):
            for definition in self.HINTS_BY_KIND.get(node.kind, ()):
                bucket = definition.bucket
                if definition.key in detected[bucket]:
                    continue
                if definition.call_name and not self._call_matches(node, definition.call_name):
                    continue
                if definition.predicate:
                    predicate_fn = getattr(self, definition.predicate)
                    if not predicate_fn(node):
                        continue
                buckets[bucket].append(self._rule_hint_from_template(definition.hint))
                detected[bucket].add(definition.key)

            if self._requirements_satisfied(detected):
                break

        ordered_hints: List[RuleHint] = []
        for bucket in self.BUCKET_ORDER:
            ordered_hints.extend(buckets[bucket])
        return ordered_hints

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
