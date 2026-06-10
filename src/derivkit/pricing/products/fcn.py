"""FCN (Fixed Coupon Note) autocallable product."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np

from derivkit.core.conventions import parse_tenor
from derivkit.core.enums import EngineMethod, ExerciseType
from derivkit.core.interfaces import Product
from derivkit.pricing.products.snowball import _monthly_obs_dates


@dataclass
class FCN(Product):
    """Fixed coupon note: monthly knock-out, fixed coupon, European knock-in at maturity."""

    s0: float
    barrier_out: float
    barrier_in: float
    coupon: float
    underlying_id: str = "default"
    _maturity: float = 1.0
    lock_term_months: int = 1
    margin_lvl: float = 1.0
    parti_in: float = 1.0
    strike_upper: float | None = None
    strike_lower: float = 0.0
    valuation_date: date | None = None
    obs_dates: list[date] = field(default_factory=list)
    annual_days: int = 365
    t_step_per_year: int = 243
    in_obs_type: ExerciseType = ExerciseType.EUROPEAN

    def __post_init__(self) -> None:
        if self.strike_upper is None:
            self.strike_upper = self.barrier_in
        if not self.obs_dates:
            start = self.valuation_date or date.today()
            self.obs_dates = _monthly_obs_dates(start, self._maturity, self.lock_term_months)
        n = len(self.obs_dates)
        bo = np.full(n, float(self.barrier_out))
        bo[: max(self.lock_term_months - 1, 0)] = np.inf
        self._barrier_out = bo
        bi = np.zeros(n)
        bi[-1] = float(self.barrier_in)
        self._barrier_in = bi
        self._barrier_yield = np.zeros(n)
        self._coupon = np.full(n, float(self.coupon))

    @classmethod
    def from_params(
        cls,
        params: dict,
        underlying_id: str,
        valuation_date: date | None = None,
    ) -> FCN:
        maturity = parse_tenor(params.get("maturity", "1y"))
        lock_term = params.get("lock_term", "1m")
        lock_months = int(parse_tenor(lock_term) * 12) if isinstance(lock_term, str) else int(lock_term)
        s0 = float(params.get("s0", 100))
        barrier_in = float(params.get("barrier_in", 80))
        return cls(
            s0=s0,
            barrier_out=float(params.get("barrier_out", 103)),
            barrier_in=barrier_in,
            coupon=float(params.get("coupon", params.get("coupon_out", 0.02))),
            underlying_id=underlying_id,
            _maturity=maturity,
            lock_term_months=lock_months,
            margin_lvl=float(params.get("margin_lvl", 1.0)),
            parti_in=float(params.get("parti_in", 1.0)),
            strike_upper=float(params["strike_upper"]) if params.get("strike_upper") is not None else None,
            valuation_date=valuation_date,
        )

    @property
    def maturity(self) -> float:
        return self._maturity

    @property
    def supported_engines(self) -> set[EngineMethod]:
        return {EngineMethod.MC, EngineMethod.QUAD}

    def payoff(self, path_or_spot: np.ndarray | float) -> float | np.ndarray:
        raise NotImplementedError("FCN payoff is path-dependent; use MC/Quad engine")
