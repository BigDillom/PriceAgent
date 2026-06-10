"""Unified conventions for day-count, annualization, and greeks definitions."""

from __future__ import annotations

import re
from datetime import date, datetime

from derivkit.core.enums import Compounding, DayCount

DAYS_PER_YEAR: dict[DayCount, float] = {
    DayCount.ACT365: 365.0,
    DayCount.ACT360: 360.0,
    DayCount.ACT_ACT: 365.25,
    DayCount.THIRTY360: 360.0,
}


def year_fraction(
    start: date | datetime | str,
    end: date | datetime | str,
    day_count: DayCount = DayCount.ACT365,
) -> float:
    """Compute year fraction between two dates."""
    d0 = _to_date(start)
    d1 = _to_date(end)
    days = (d1 - d0).days
    return days / DAYS_PER_YEAR[day_count]


def parse_tenor(tenor: str | float | int) -> float:
    """Parse tenor string like '1y', '3m', '6w' into years."""
    if isinstance(tenor, (int, float)):
        return float(tenor)
    tenor = tenor.strip().lower()
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([ymwd])", tenor)
    if not match:
        raise ValueError(f"Invalid tenor: {tenor}")
    value, unit = float(match.group(1)), match.group(2)
    if unit == "y":
        return value
    if unit == "m":
        return value / 12.0
    if unit == "w":
        return value / 52.0
    if unit == "d":
        return value / 365.0
    raise ValueError(f"Unknown tenor unit: {unit}")


def discount_factor(
    rate: float,
    t: float,
    compounding: Compounding = Compounding.CONTINUOUS,
) -> float:
    """Compute discount factor DF(t) from constant rate."""
    if compounding == Compounding.CONTINUOUS:
        return float(__import__("math").exp(-rate * t))
    if compounding == Compounding.SIMPLE:
        return 1.0 / (1.0 + rate * t)
    if compounding == Compounding.ANNUAL:
        return (1.0 + rate) ** (-t)
    raise ValueError(f"Unknown compounding: {compounding}")


def _to_date(d: date | datetime | str) -> date:
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
