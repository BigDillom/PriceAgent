"""Standard snowball (autocallable) product definition."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from derivkit.core.conventions import parse_tenor
from derivkit.core.enums import EngineMethod
from derivkit.core.interfaces import Product


def _monthly_obs_dates(start: date, maturity_years: float, lock_months: int = 3) -> list[date]:
    """Generate monthly observation dates with simple business-day skip."""
    end = start + timedelta(days=int(maturity_years * 365))
    dates: list[date] = []
    current = start
    month = 0
    while current <= end:
        if month >= lock_months:
            d = current
            while d.weekday() >= 5:
                d += timedelta(days=1)
            dates.append(d)
        current = current + timedelta(days=30)
        month += 1
    if not dates:
        dates.append(end)
    return dates


@dataclass
class StandardSnowball(Product):
    """Classic knock-in/knock-out snowball."""

    s0: float
    barrier_out: float
    barrier_in: float
    coupon_out: float
    underlying_id: str = "default"
    _maturity: float = 1.0
    lock_term_months: int = 3
    margin_lvl: float = 1.0
    parti_in: float = 1.0
    parti_out: float = 0.0
    strike_upper: float | None = None
    strike_lower: float = 0.0
    strike_call: float | None = None
    coupon_div: float | None = None
    valuation_date: date | None = None
    obs_dates: list[date] = field(default_factory=list)
    annual_days: int = 365
    t_step_per_year: int = 243

    def __post_init__(self) -> None:
        if self.strike_upper is None:
            self.strike_upper = self.s0
        if self.strike_call is None:
            self.strike_call = 4 * self.s0
        if self.coupon_div is None:
            self.coupon_div = self.coupon_out
        if not self.obs_dates:
            start = self.valuation_date or date.today()
            self.obs_dates = _monthly_obs_dates(start, self._maturity, self.lock_term_months)
        n = len(self.obs_dates)
        if np.isscalar(self.barrier_out):
            self._barrier_out = np.full(n, float(self.barrier_out))
        else:
            self._barrier_out = np.asarray(self.barrier_out, dtype=float)
        if np.isscalar(self.barrier_in):
            self._barrier_in = np.full(n, float(self.barrier_in))
        else:
            self._barrier_in = np.asarray(self.barrier_in, dtype=float)
        if np.isscalar(self.coupon_out):
            self._coupon_out = np.full(n, float(self.coupon_out))
        else:
            self._coupon_out = np.asarray(self.coupon_out, dtype=float)

    @classmethod
    def from_params(
        cls,
        params: dict,
        underlying_id: str,
        valuation_date: date | None = None,
    ) -> StandardSnowball:
        maturity = parse_tenor(params.get("maturity", "1y"))
        lock_term = params.get("lock_term", "3m")
        lock_months = (
            int(parse_tenor(lock_term) * 12) if isinstance(lock_term, str) else int(lock_term)
        )
        s0 = float(params.get("s0", 100))
        return cls(
            s0=s0,
            barrier_out=float(params.get("barrier_out", 103)),
            barrier_in=float(params.get("barrier_in", 80)),
            coupon_out=float(params.get("coupon_out", 0.113)),
            underlying_id=underlying_id,
            _maturity=maturity,
            lock_term_months=lock_months,
            valuation_date=valuation_date,
        )

    @property
    def maturity(self) -> float:
        return self._maturity

    @property
    def supported_engines(self) -> set[EngineMethod]:
        return {EngineMethod.MC, EngineMethod.FDM, EngineMethod.QUAD}

    def payoff(self, path_or_spot: np.ndarray | float) -> float | np.ndarray:
        raise NotImplementedError("Snowball payoff is path-dependent; use MC/FDM engine")
