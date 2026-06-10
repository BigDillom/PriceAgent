"""Interest rate term structures."""

from __future__ import annotations

import logging
from collections.abc import Sequence

import numpy as np

from derivkit.core.conventions import discount_factor
from derivkit.core.enums import Compounding, DayCount
from derivkit.core.observable import Observable

logger = logging.getLogger(__name__)


class ConstantRate(Observable):
    """Constant risk-free rate snapshot."""

    def __init__(
        self,
        rate: float,
        day_count: DayCount = DayCount.ACT365,
        compounding: Compounding = Compounding.CONTINUOUS,
        rate_id: str = "default",
    ) -> None:
        super().__init__()
        self.rate_id = rate_id
        self._rate = float(rate)
        self.day_count = day_count
        self.compounding = compounding

    @property
    def rate(self) -> float:
        return self._rate

    @rate.setter
    def rate(self, value: float) -> None:
        self._rate = float(value)
        self.notify()

    def __call__(self, t: float) -> float:
        return self._rate

    def disc_factor(self, t2: float, t1: float = 0.0) -> float:
        """Discount factor from t1 to t2."""
        dt = max(t2 - t1, 0.0)
        return discount_factor(self._rate, dt, self.compounding)


class RateCurve(Observable):
    """Piecewise rate curve with linear discount interpolation."""

    def __init__(
        self,
        tenors: Sequence[float],
        rates: Sequence[float],
        day_count: DayCount = DayCount.ACT365,
        compounding: Compounding = Compounding.CONTINUOUS,
        rate_id: str = "default",
    ) -> None:
        super().__init__()
        self.rate_id = rate_id
        self.day_count = day_count
        self.compounding = compounding
        self._tenors = np.asarray(tenors, dtype=float)
        self._rates = np.asarray(rates, dtype=float)
        if len(self._tenors) != len(self._rates):
            raise ValueError("tenors and rates must have same length")
        if not np.all(np.diff(self._tenors) > 0):
            raise ValueError("tenors must be strictly increasing")

    def __call__(self, t: float) -> float:
        return float(np.interp(t, self._tenors, self._rates))

    def disc_factor(self, t2: float, t1: float = 0.0) -> float:
        """Discount factor using zero-rate interpolation."""
        dt = max(t2 - t1, 0.0)
        if dt == 0.0:
            return 1.0
        r = self(t2)
        return discount_factor(r, dt, self.compounding)

    def bump(self, amount: float) -> RateCurve:
        """Return a parallel-shifted copy."""
        return RateCurve(
            self._tenors.tolist(),
            (self._rates + amount).tolist(),
            self.day_count,
            self.compounding,
            self.rate_id,
        )
