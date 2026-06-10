"""High-level public API: price(), risk(), calibrate()."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from derivkit.contract.output_contract import PricingResult
from derivkit.dsl.loader import load_spec
from derivkit.dsl.schema import PricingSpec
from derivkit.engine_orchestrator import run_calibrate, run_pricing, run_risk

logger = logging.getLogger(__name__)


def price(spec: str | Path | dict[str, Any] | PricingSpec) -> PricingResult:
    """Price a derivative from DSL spec, file path, or dict.

    Args:
        spec: YAML/JSON file path, dict, or validated PricingSpec.

    Returns:
        PricingResult with pv, greeks, and meta.

    Example:
        >>> result = price({"task": "price", "market": {...}, "product": {...}})
        >>> print(result.pv)
    """
    parsed = spec if isinstance(spec, PricingSpec) else load_spec(spec)
    if parsed.task == "risk":
        return run_risk(parsed)
    return run_pricing(parsed)


def risk(spec: str | Path | dict[str, Any] | PricingSpec) -> PricingResult:
    """Calculate risk sensitivities (greeks) for a derivative."""
    parsed = spec if isinstance(spec, PricingSpec) else load_spec(spec)
    return run_risk(parsed)


def calibrate(spec: str | Path | dict[str, Any] | PricingSpec) -> PricingResult:
    """Calibrate volatility from historical returns or implied market price.

    Returns PricingResult where ``pv`` is the calibrated annualized volatility (decimal).
    Details are in ``meta`` (method, window, data source, etc.).

    Example:
        >>> result = calibrate({"task": "calibrate", "market": {...}, "calibration": {...}})
        >>> print(result.pv)  # e.g. 0.22 for 22%
    """
    if isinstance(spec, PricingSpec):
        parsed = spec
        base_dir = None
    else:
        path = Path(spec) if isinstance(spec, (str, Path)) and Path(spec).suffix in (
            ".yaml",
            ".yml",
            ".json",
        ) else None
        parsed = load_spec(spec)
        base_dir = path.parent if path else None
    return run_calibrate(parsed, base_dir=base_dir)
