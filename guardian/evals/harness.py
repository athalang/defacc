"""Generate C ABI differential fuzzing harness artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .manifest import ArgumentSpec, EvalCase
from .proto_schema import message_name, render_case_proto


@dataclass(frozen=True)
class HarnessArtifacts:
    proto: str
    c_header: str
    c_adapter: str
    rust_adapter: str
    comparator: str


def generate_harness(case: EvalCase) -> HarnessArtifacts:
    """Generate source text for the case harness."""
    return HarnessArtifacts(
        proto=render_case_proto(case),
        c_header=_render_c_header(case),
        c_adapter=_render_c_adapter(case),
        rust_adapter=_render_rust_adapter(case),
        comparator=_render_comparator(case),
    )


def write_harness(case: EvalCase, output_dir: Path) -> HarnessArtifacts:
    """Write generated harness artifacts into a case output directory."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = generate_harness(case)
    (output_dir / "input.proto").write_text(artifacts.proto)
    (output_dir / "target_abi.h").write_text(artifacts.c_header)
    (output_dir / "c_adapter.c").write_text(artifacts.c_adapter)
    (output_dir / "rust_adapter.rs").write_text(artifacts.rust_adapter)
    (output_dir / "differential_harness.cc").write_text(artifacts.comparator)
    return artifacts


def _render_c_header(case: EvalCase) -> str:
    args = ", ".join(_c_arg(arg) for arg in case.args)
    return (
        "#pragma once\n"
        "#include <stddef.h>\n"
        "#include <stdint.h>\n\n"
        f"{case.return_type} guardian_c_target({args});\n"
        f"{case.return_type} guardian_rust_target({args});\n"
    )


def _render_c_adapter(case: EvalCase) -> str:
    args = ", ".join(_c_arg(arg) for arg in case.args)
    call_args = ", ".join(_c_call_arg(arg) for arg in case.args)
    return (
        '#include "target_abi.h"\n'
        '#include "source.c"\n\n'
        f"{case.return_type} guardian_c_target({args}) {{\n"
        f"    return {case.function}({call_args});\n"
        "}\n"
    )


def _render_rust_adapter(case: EvalCase) -> str:
    args = ", ".join(_rust_ffi_arg(arg) for arg in case.args)
    call_args = ", ".join(_rust_call_arg(arg) for arg in case.args)
    rust_return = _rust_ffi_type(case.return_type)
    return (
        "#![allow(non_camel_case_types)]\n"
        "use std::os::raw::{c_int, c_uint, c_ulonglong};\n\n"
        'include!("translation.rs");\n\n'
        "#[no_mangle]\n"
        f"pub unsafe extern \"C\" fn guardian_rust_target({args}) -> {rust_return} {{\n"
        f"    {case.function}({call_args})\n"
        "}\n"
    )


def _render_comparator(case: EvalCase) -> str:
    input_type = message_name(case.id)
    declarations = "\n".join(_cpp_arg_declaration(arg) for arg in case.args)
    call_args = ", ".join(arg.name for arg in case.args)
    output_checks = "\n".join(
        f'  if (before_{output.name} != after_{output.name}) return 1;'
        for output in case.mutated_outputs
    )
    return f"""#include <stdint.h>
#include <stddef.h>
#include <string>

#include "src/libfuzzer/libfuzzer_macro.h"
#include "target_abi.h"
#include "input.pb.h"

static int compare_one(const guardian::evals::{input_type}& input) {{
{declarations}
  auto c_result = guardian_c_target({call_args});
  auto rust_result = guardian_rust_target({call_args});
  if (c_result != rust_result) return 1;
{output_checks}
  return 0;
}}

DEFINE_PROTO_FUZZER(const guardian::evals::{input_type}& input) {{
  if (compare_one(input) != 0) {{
    __builtin_trap();
  }}
}}
"""


def _c_arg(arg: ArgumentSpec) -> str:
    if arg.kind == "scalar":
        return f"{arg.c_type} {arg.name}"
    return f"{arg.c_type} {arg.name}, size_t {arg.name}_len"


def _c_call_arg(arg: ArgumentSpec) -> str:
    if arg.kind == "scalar":
        return arg.name
    return arg.name


def _rust_ffi_arg(arg: ArgumentSpec) -> str:
    if arg.kind == "scalar":
        return f"{arg.name}: {_rust_ffi_type(arg.c_type)}"
    return f"{arg.name}: *mut u8, {arg.name}_len: usize"


def _rust_call_arg(arg: ArgumentSpec) -> str:
    if arg.kind == "scalar":
        return arg.name
    return f"std::slice::from_raw_parts_mut({arg.name}, {arg.name}_len)"


def _rust_ffi_type(c_type: str) -> str:
    normalized = c_type.replace("const", "").replace("*", "").strip()
    mapping = {
        "int": "c_int",
        "unsigned int": "c_uint",
        "uint32_t": "u32",
        "int32_t": "i32",
        "uint64_t": "u64",
        "int64_t": "i64",
        "size_t": "usize",
        "void": "()",
    }
    return mapping.get(normalized, "c_ulonglong")


def _cpp_arg_declaration(arg: ArgumentSpec) -> str:
    accessor = f"input.{arg.source_field}()"
    if arg.kind == "scalar":
        return f"  {arg.c_type} {arg.name} = static_cast<{arg.c_type}>({accessor});"
    if arg.kind == "string":
        return (
            f"  std::string storage_{arg.name} = {accessor};\n"
            f"  uint8_t* {arg.name} = reinterpret_cast<uint8_t*>(storage_{arg.name}.data());\n"
            f"  size_t {arg.name}_len = storage_{arg.name}.size();"
        )
    return (
        f"  std::string storage_{arg.name} = {accessor};\n"
        f"  uint8_t* {arg.name} = reinterpret_cast<uint8_t*>(storage_{arg.name}.data());\n"
        f"  size_t {arg.name}_len = storage_{arg.name}.size();"
    )
