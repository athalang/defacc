"""Manifest model for function-level differential fuzzing cases."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal


ScalarType = Literal["i8", "u8", "i16", "u16", "i32", "u32", "i64", "u64", "usize", "bool"]
ArgKind = Literal["scalar", "bytes", "string", "array"]
ExpectedClass = Literal["defined", "may_ub", "known_ub", "security"]


@dataclass(frozen=True)
class ArgumentSpec:
    """One target-function argument derived from structured fuzz input."""

    name: str
    kind: ArgKind
    c_type: str
    source_field: str
    value_type: ScalarType | None = None
    min_len: int = 0
    max_len: int | None = None
    nullable: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArgumentSpec":
        required = ["name", "kind", "c_type", "source_field"]
        _require_keys(data, required, "argument")
        return cls(
            name=str(data["name"]),
            kind=_literal(data["kind"], {"scalar", "bytes", "string", "array"}, "argument.kind"),
            c_type=str(data["c_type"]),
            source_field=str(data["source_field"]),
            value_type=data.get("value_type"),
            min_len=int(data.get("min_len", 0)),
            max_len=None if data.get("max_len") is None else int(data["max_len"]),
            nullable=bool(data.get("nullable", False)),
        )


@dataclass(frozen=True)
class MutatedOutputSpec:
    """Caller-owned output that must be snapshotted after each function call."""

    name: str
    arg: str
    kind: Literal["bytes", "array", "scalar", "struct"]
    length_field: str | None = None
    fields: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MutatedOutputSpec":
        _require_keys(data, ["name", "arg", "kind"], "mutated output")
        return cls(
            name=str(data["name"]),
            arg=str(data["arg"]),
            kind=_literal(data["kind"], {"bytes", "array", "scalar", "struct"}, "mutated_output.kind"),
            length_field=None if data.get("length_field") is None else str(data["length_field"]),
            fields=tuple(str(field) for field in data.get("fields", ())),
        )


@dataclass(frozen=True)
class EvalCase:
    """A function-level differential fuzzing case."""

    id: str
    source: str
    source_case_id: str
    c_file: Path
    function: str
    args: tuple[ArgumentSpec, ...]
    return_type: str
    mutated_outputs: tuple[MutatedOutputSpec, ...] = ()
    preconditions: tuple[str, ...] = ()
    timeout_ms: int = 1000
    sanitizers: tuple[str, ...] = ("address", "undefined")
    expected_class: ExpectedClass = "defined"

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, base_dir: Path | None = None) -> "EvalCase":
        required = [
            "id",
            "source",
            "source_case_id",
            "c_file",
            "function",
            "args",
            "return_type",
        ]
        _require_keys(data, required, "eval case")
        base_dir = base_dir or Path.cwd()
        c_file = Path(str(data["c_file"]))
        if not c_file.is_absolute():
            c_file = base_dir / c_file
        return cls(
            id=str(data["id"]),
            source=str(data["source"]),
            source_case_id=str(data["source_case_id"]),
            c_file=c_file,
            function=str(data["function"]),
            args=tuple(ArgumentSpec.from_dict(arg) for arg in data["args"]),
            return_type=str(data["return_type"]),
            mutated_outputs=tuple(
                MutatedOutputSpec.from_dict(output)
                for output in data.get("mutated_outputs", ())
            ),
            preconditions=tuple(str(item) for item in data.get("preconditions", ())),
            timeout_ms=int(data.get("timeout_ms", 1000)),
            sanitizers=tuple(str(item) for item in data.get("sanitizers", ("address", "undefined"))),
            expected_class=_literal(
                data.get("expected_class", "defined"),
                {"defined", "may_ub", "known_ub", "security"},
                "expected_class",
            ),
        )


def load_manifest(path: Path) -> list[EvalCase]:
    """Load eval cases from a JSON manifest."""
    path = Path(path)
    data = json.loads(path.read_text())
    cases = data.get("cases", data if isinstance(data, list) else None)
    if not isinstance(cases, list):
        raise ValueError("manifest must be a list or an object with a 'cases' list")
    return [EvalCase.from_dict(case, base_dir=path.parent) for case in cases]


def dump_manifest(cases: Iterable[EvalCase]) -> str:
    """Serialize cases to the committed JSON manifest shape."""
    return json.dumps({"cases": [_case_to_dict(case) for case in cases]}, indent=2) + "\n"


def _case_to_dict(case: EvalCase) -> dict[str, Any]:
    return {
        "id": case.id,
        "source": case.source,
        "source_case_id": case.source_case_id,
        "c_file": str(case.c_file),
        "function": case.function,
        "args": [arg.__dict__ for arg in case.args],
        "return_type": case.return_type,
        "mutated_outputs": [output.__dict__ for output in case.mutated_outputs],
        "preconditions": list(case.preconditions),
        "timeout_ms": case.timeout_ms,
        "sanitizers": list(case.sanitizers),
        "expected_class": case.expected_class,
    }


def _require_keys(data: dict[str, Any], keys: list[str], context: str) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise ValueError(f"{context} missing required key(s): {', '.join(missing)}")


def _literal(value: Any, allowed: set[str], field: str) -> Any:
    if value not in allowed:
        raise ValueError(f"{field} must be one of {sorted(allowed)}, got {value!r}")
    return value
