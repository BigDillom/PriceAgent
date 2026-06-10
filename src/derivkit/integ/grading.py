"""QFbench-style result grading with per-field tolerances."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import json

from derivkit.contract.output_contract import PricingResult, validate_result


@dataclass
class GradeReport:
    """Grading outcome for a single task."""

    passed: bool
    errors: list[str] = field(default_factory=list)
    checked_fields: list[str] = field(default_factory=list)

    def assert_passed(self) -> None:
        if not self.passed:
            raise AssertionError("; ".join(self.errors))


def load_expected(path: str | Path) -> dict[str, Any]:
    """Load expected values and tolerances from JSON."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "tolerance" not in data and "tolerances" in data:
        data["tolerance"] = data["tolerances"]
    return data


def grade_result(
    actual: PricingResult | dict[str, Any],
    expected: dict[str, Any],
) -> GradeReport:
    """Grade actual pricing output against expected reference values.

    ``expected`` JSON schema::

        {
          "pv": 10.45,
          "tolerance": {"pv": 0.01},
          "fields": ["pv"]
        }

    Optional greek fields may be listed in ``fields`` with matching keys in
    ``expected`` and ``tolerance``.
    """
    if isinstance(actual, PricingResult):
        actual_dict = actual.to_dict()
    else:
        actual_dict = actual

    fields = expected.get("fields", ["pv"])
    tolerance = expected.get("tolerance", {"pv": 1e-2})
    errors: list[str] = []

    for field_name in fields:
        if field_name not in actual_dict and field_name not in actual_dict.get("meta", {}):
            errors.append(f"missing field: {field_name}")
            continue
        exp_val = expected.get(field_name)
        if exp_val is None:
            continue
        act_val = actual_dict.get(field_name)
        if act_val is None:
            errors.append(f"missing actual value for {field_name}")
            continue
        tol = tolerance.get(field_name, tolerance.get("pv", 1e-2))
        if abs(float(act_val) - float(exp_val)) > tol:
            errors.append(
                f"{field_name}: actual={act_val}, expected={exp_val}, tolerance={tol}"
            )

    return GradeReport(passed=not errors, errors=errors, checked_fields=fields)


def grade_pv(
    result: PricingResult,
    expected_pv: float,
    tolerance: float = 1e-2,
) -> bool:
    """Backward-compatible PV-only grading."""
    from derivkit.contract.output_contract import OutputContract

    contract = OutputContract(tolerance={"pv": tolerance})
    return validate_result(result, expected_pv, contract)
