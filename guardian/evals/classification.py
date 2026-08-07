"""Classification rules for differential fuzzing findings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .observation import ExecutionStatus, Observation, ObservationDiff, compare_observations


class FindingClass(str, Enum):
    EQUIVALENT = "equivalent"
    REGRESSION = "regression"
    RUST_CRASH = "rust_crash"
    C_UB_SAFE_RUST = "c_ub_safe_rust"
    BUG_COMPATIBLE = "bug_compatible"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class Finding:
    classification: FindingClass
    differences: tuple[str, ...] = ()
    reason: str = ""


def classify_observations(
    *,
    c_reference: Observation,
    c_sanitized: Observation,
    rust: Observation,
) -> Finding:
    """Classify one differential execution."""
    if ExecutionStatus.UNSUPPORTED in {c_reference.status, c_sanitized.status, rust.status}:
        return Finding(FindingClass.UNSUPPORTED, reason="at least one side is unsupported")

    c_has_ub = c_sanitized.status in {
        ExecutionStatus.CRASH,
        ExecutionStatus.SANITIZER,
        ExecutionStatus.TIMEOUT,
        ExecutionStatus.CONTRACT,
    }
    rust_failed = rust.status in {
        ExecutionStatus.CRASH,
        ExecutionStatus.PANIC,
        ExecutionStatus.TIMEOUT,
        ExecutionStatus.CONTRACT,
        ExecutionStatus.SANITIZER,
    }

    if c_has_ub:
        if rust_failed:
            return Finding(FindingClass.BUG_COMPATIBLE, reason="C sanitizer failed and Rust also failed")
        return Finding(FindingClass.C_UB_SAFE_RUST, reason="C sanitizer failed and Rust returned safely")

    if rust_failed:
        return Finding(FindingClass.RUST_CRASH, reason=f"Rust status was {rust.status.value}")

    diff: ObservationDiff = compare_observations(c_reference, rust)
    if diff.equal:
        return Finding(FindingClass.EQUIVALENT)
    return Finding(FindingClass.REGRESSION, differences=diff.differences)
