"""Output contract definitions and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OutputContract:
    """Explicit output field contract with tolerances."""

    fields: list[str] = field(default_factory=lambda: ["pv"])
    tolerance: dict[str, float] = field(default_factory=lambda: {"pv": 1e-2})
    deterministic: bool = True
    seed: int = 0


@dataclass
class PricingResult:
    """Structured pricing result."""

    pv: float
    greeks: dict[str, float] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"pv": self.pv}
        result.update(self.greeks)
        result["meta"] = self.meta
        return result

    def get(self, field_name: str, default: Any = None) -> Any:
        if field_name == "pv":
            return self.pv
        if field_name in self.greeks:
            return self.greeks[field_name]
        return self.meta.get(field_name, default)


def validate_result(
    result: PricingResult,
    expected: float | None,
    contract: OutputContract,
) -> bool:
    """Validate result against expected value within contract tolerance."""
    if expected is None:
        return True
    tol = contract.tolerance.get("pv", 1e-2)
    return abs(result.pv - expected) <= tol
