"""Data quality validation rules."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

_MAX_REASONABLE_VOL = 5.0
_MIN_TENOR_SPACING = 1e-6


@dataclass
class ValidationIssue:
    """Single validation issue."""

    level: str  # error | warning
    field: str
    message: str


@dataclass
class ValidationReport:
    """Structured validation report."""

    passed: bool = True
    issues: list[ValidationIssue] = field(default_factory=list)

    def add_error(self, field: str, message: str) -> None:
        self.passed = False
        self.issues.append(ValidationIssue("error", field, message))

    def add_warning(self, field: str, message: str) -> None:
        self.issues.append(ValidationIssue("warning", field, message))

    def merge(self, other: ValidationReport) -> None:
        if not other.passed:
            self.passed = False
        self.issues.extend(other.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "issues": [
                {"level": i.level, "field": i.field, "message": i.message} for i in self.issues
            ],
        }


def validate_rate_curve(
    tenors: np.ndarray,
    rates: np.ndarray,
    *,
    min_tenor: float = 0.0,
    max_tenor: float | None = None,
) -> ValidationReport:
    """Validate rate curve monotonicity, coverage, and finiteness."""
    report = ValidationReport()
    tenors = np.asarray(tenors, dtype=float)
    rates = np.asarray(rates, dtype=float)

    if len(tenors) == 0:
        report.add_error("tenors", "Empty tenor array")
        return report
    if len(tenors) != len(rates):
        report.add_error("rates", f"Tenor/rate length mismatch: {len(tenors)} vs {len(rates)}")
        return report
    if not np.all(np.diff(tenors) > _MIN_TENOR_SPACING):
        report.add_error("tenors", "Tenors must be strictly increasing")
    if np.any(tenors < 0):
        report.add_error("tenors", "Tenors must be non-negative")
    if np.any(np.isnan(rates)) or np.any(np.isinf(rates)):
        report.add_error("rates", "Rates contain NaN or Inf")
    if np.any(rates < -0.05):
        report.add_warning("rates", "Rates below -5% may indicate data error")
    if max_tenor is not None and float(np.max(tenors)) < max_tenor:
        report.add_warning(
            "tenors",
            f"Curve max tenor {float(np.max(tenors)):.4f} < required {max_tenor:.4f}",
        )
    if min_tenor > 0 and float(np.min(tenors)) > min_tenor:
        report.add_warning("tenors", f"Curve does not cover near term from t={min_tenor}")
    return report


def validate_vol_surface(
    vols: np.ndarray,
    *,
    spots: np.ndarray | None = None,
    times: np.ndarray | None = None,
) -> ValidationReport:
    """Validate volatility surface: non-negative, finite, reasonable magnitude."""
    report = ValidationReport()
    vols = np.asarray(vols, dtype=float)
    if np.any(vols < 0):
        report.add_error("vols", "Volatility must be non-negative")
    if np.any(np.isnan(vols)) or np.any(np.isinf(vols)):
        report.add_error("vols", "Volatility contains NaN or Inf")
    if np.any(vols > _MAX_REASONABLE_VOL):
        report.add_warning("vols", f"Volatility exceeds {_MAX_REASONABLE_VOL:.0%} — check units")
    if spots is not None and times is not None:
        spots_a = np.asarray(spots, dtype=float)
        times_a = np.asarray(times, dtype=float)
        if vols.ndim == 2:
            if vols.shape != (len(times_a), len(spots_a)):
                report.add_error(
                    "vols",
                    f"Grid shape {vols.shape} != ({len(times_a)}, {len(spots_a)})",
                )
        if not np.all(np.diff(times_a) > 0):
            report.add_error("times", "Expiry grid must be strictly increasing")
        if not np.all(np.diff(spots_a) > 0):
            report.add_error("spots", "Spot grid must be strictly increasing")
    return report


def validate_spot(spot: float) -> ValidationReport:
    """Validate spot price."""
    report = ValidationReport()
    if spot <= 0:
        report.add_error("spot", f"Spot must be positive, got {spot}")
    if np.isnan(spot) or np.isinf(spot):
        report.add_error("spot", "Spot is NaN or Inf")
    return report


def validate_market_inputs(
    spots: dict[str, float],
    vols: dict[str, float] | None = None,
    *,
    required_maturity: float | None = None,
    rate_tenors: np.ndarray | None = None,
    rate_values: np.ndarray | None = None,
) -> ValidationReport:
    """Aggregate validation for MarketEnv construction."""
    report = ValidationReport()
    for uid, spot in spots.items():
        sub = validate_spot(spot)
        if not sub.passed:
            for issue in sub.issues:
                report.add_error(f"underlyings.{uid}.{issue.field}", issue.message)
    if vols:
        for uid, sigma in vols.items():
            sub = validate_vol_surface(np.array([sigma]))
            if not sub.passed:
                for issue in sub.issues:
                    report.add_error(f"vols.{uid}.{issue.field}", issue.message)
    if rate_tenors is not None and rate_values is not None:
        report.merge(validate_rate_curve(rate_tenors, rate_values, max_tenor=required_maturity))
    return report
