"""libprotobuf-mutator schema generation for eval cases."""

from __future__ import annotations

from .manifest import EvalCase


PROTO_HEADER = 'syntax = "proto3";\n\npackage guardian.evals;\n\n'


def render_case_proto(case: EvalCase) -> str:
    """Render a protobuf schema for one case's structured fuzz input."""
    lines = [PROTO_HEADER, f"message {message_name(case.id)} {{\n"]
    field_number = 1
    for arg in case.args:
        if arg.kind == "scalar":
            proto_type = _scalar_proto_type(arg.value_type)
            lines.append(f"  {proto_type} {arg.source_field} = {field_number};\n")
        elif arg.kind in {"bytes", "array"}:
            lines.append(f"  bytes {arg.source_field} = {field_number};\n")
        elif arg.kind == "string":
            lines.append(f"  string {arg.source_field} = {field_number};\n")
        else:
            raise ValueError(f"unsupported arg kind: {arg.kind}")
        field_number += 1
    lines.append("}\n")
    return "".join(lines)


def message_name(case_id: str) -> str:
    parts = [part for part in case_id.replace("-", "_").split("_") if part]
    return "".join(part[:1].upper() + part[1:] for part in parts) + "Input"


def _scalar_proto_type(value_type: str | None) -> str:
    mapping = {
        "i8": "int32",
        "u8": "uint32",
        "i16": "int32",
        "u16": "uint32",
        "i32": "int32",
        "u32": "uint32",
        "i64": "int64",
        "u64": "uint64",
        "usize": "uint64",
        "bool": "bool",
    }
    if value_type not in mapping:
        raise ValueError(f"scalar argument requires a supported value_type, got {value_type!r}")
    return mapping[value_type]
