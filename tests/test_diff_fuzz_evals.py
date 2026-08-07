import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from guardian.evals import (
    ExecutionStatus,
    FindingClass,
    Observation,
    classify_observations,
    compare_observations,
    load_manifest,
)
from guardian.evals.harness import generate_harness
from guardian.evals.proto_schema import render_case_proto
from guardian.evals.runner import afl_commands, main as eval_main


class DifferentialFuzzEvalTests(unittest.TestCase):
    def test_manifest_loads_function_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "cases.json"
            manifest.write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "id": "external-add",
                                "source": "csmith",
                                "source_case_id": "seed-1",
                                "c_file": "case.c",
                                "function": "target",
                                "args": [
                                    {
                                        "name": "x",
                                        "kind": "scalar",
                                        "c_type": "int32_t",
                                        "source_field": "x",
                                        "value_type": "i32",
                                    }
                                ],
                                "return_type": "int32_t",
                            }
                        ]
                    }
                )
            )

            cases = load_manifest(manifest)

        self.assertEqual("external-add", cases[0].id)
        self.assertEqual("target", cases[0].function)
        self.assertEqual("x", cases[0].args[0].source_field)

    def test_proto_schema_uses_manifest_fields(self) -> None:
        case = load_manifest(Path("guardian/evals/manifests/external.example.json"))[0]

        proto = render_case_proto(case)

        self.assertIn('syntax = "proto3";', proto)
        self.assertIn("message JulietCwe190AddI32Input", proto)
        self.assertIn("int32 a = 1;", proto)
        self.assertIn("int32 b = 2;", proto)

    def test_observation_compare_catches_return_and_output_differences(self) -> None:
        left = Observation(ExecutionStatus.OK, return_value=1, outputs={"buf": b"abc"})
        right = Observation(ExecutionStatus.OK, return_value=2, outputs={"buf": b"abd"})

        diff = compare_observations(left, right)

        self.assertFalse(diff.equal)
        self.assertEqual(2, len(diff.differences))

    def test_classifies_defined_behavior_mismatch_as_regression(self) -> None:
        c_reference = Observation(ExecutionStatus.OK, return_value=1)
        c_sanitized = Observation(ExecutionStatus.OK, return_value=1)
        rust = Observation(ExecutionStatus.OK, return_value=2)

        finding = classify_observations(
            c_reference=c_reference,
            c_sanitized=c_sanitized,
            rust=rust,
        )

        self.assertEqual(FindingClass.REGRESSION, finding.classification)

    def test_classifies_sanitizer_failure_with_safe_rust_separately(self) -> None:
        c_reference = Observation(ExecutionStatus.CRASH)
        c_sanitized = Observation(ExecutionStatus.SANITIZER, diagnostics="runtime error")
        rust = Observation(ExecutionStatus.OK, return_value=0)

        finding = classify_observations(
            c_reference=c_reference,
            c_sanitized=c_sanitized,
            rust=rust,
        )

        self.assertEqual(FindingClass.C_UB_SAFE_RUST, finding.classification)

    def test_harness_generation_declares_c_abi_targets(self) -> None:
        case = load_manifest(Path("guardian/evals/manifests/external.example.json"))[0]

        artifacts = generate_harness(case)

        self.assertIn("guardian_c_target", artifacts.c_header)
        self.assertIn("guardian_rust_target", artifacts.c_header)
        self.assertIn('#include "source.c"', artifacts.c_adapter)
        self.assertIn('extern "C" fn guardian_rust_target', artifacts.rust_adapter)
        self.assertIn('include!("translation.rs");', artifacts.rust_adapter)
        self.assertIn("DEFINE_PROTO_FUZZER", artifacts.comparator)

    def test_eval_runner_dry_run_does_not_require_corpus_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "cases.json"
            manifest.write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "id": "missing-external-case",
                                "source": "juliet",
                                "source_case_id": "missing",
                                "c_file": "does-not-exist.c",
                                "function": "target",
                                "args": [],
                                "return_type": "int",
                            }
                        ]
                    }
                )
            )

            with redirect_stdout(StringIO()):
                self.assertEqual(
                    0,
                    eval_main(["run", "--manifest", str(manifest), "--out", tmp, "--dry-run"]),
                )

    def test_afl_command_uses_case_artifact_directory(self) -> None:
        case = load_manifest(Path("guardian/evals/manifests/external.example.json"))[0]

        commands = afl_commands([case], Path("artifacts/evals"))

        self.assertEqual("bash", commands[0][0])
        self.assertIn("artifacts\\evals\\juliet-cwe190-add-i32", str(Path(commands[0][2])))


if __name__ == "__main__":
    unittest.main()
