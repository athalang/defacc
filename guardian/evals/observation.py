"""Observation model and comparison for function-level fuzzing."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExecutionStatus(str, Enum):
    OK = "ok"
    CRASH = "crash"
    PANIC = "panic"
    TIMEOUT = "timeout"
    SANITIZER = "sanitizer"
    CONTRACT = "contract"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class Observation:
    """Normalized result of one function invocation."""

    status: ExecutionStatus
    return_value: Any = None
    outputs: dict[str, Any] = field(default_factory=dict)
    diagnostics: str = ""

    @property
    def succeeded(self) -> bool:
        return self.status == ExecutionStatus.OK


@dataclass(frozen=True)
class ObservationDiff:
    """Field-level differences between two successful observations."""

    equal: bool
    differences: tuple[str, ...] = ()


def compare_observations(left: Observation, right: Observation) -> ObservationDiff:
    """Compare two normalized observations."""
    differences: list[str] = []
    if left.status != right.status:
        differences.append(f"status: {left.status.value} != {right.status.value}")
    if left.return_value != right.return_value:
        differences.append(f"return_value: {left.return_value!r} != {right.return_value!r}")

    keys = sorted(set(left.outputs) | set(right.outputs))
    for key in keys:
        if left.outputs.get(key) != right.outputs.get(key):
            differences.append(f"output[{key}]: {left.outputs.get(key)!r} != {right.outputs.get(key)!r}")

    return ObservationDiff(equal=not differences, differences=tuple(differences))
