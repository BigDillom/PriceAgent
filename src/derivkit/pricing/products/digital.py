"""Cash-or-nothing digital (binary) options."""

from __future__ import annotations

import numpy as np

from derivkit.core.conventions import parse_tenor
from derivkit.core.enums import CallPut, EngineMethod, ExerciseType, PaymentType
from derivkit.core.interfaces import Product


class DigitalOption(Product):
    """Cash-or-nothing digital option."""

    def __init__(
        self,
        strike: float,
        rebate: float,
        call_put: CallPut,
        exercise: ExerciseType = ExerciseType.EUROPEAN,
        payment_type: PaymentType = PaymentType.EXPIRE,
        maturity: float | str = "1y",
        underlying_id: str = "default",
        discrete_obs_interval: float | None = None,
        t_step_per_year: int = 243,
    ) -> None:
        self.strike = float(strike)
        self.rebate = float(rebate)
        self.call_put = CallPut(call_put) if isinstance(call_put, str) else call_put
        self.exercise = ExerciseType(exercise) if isinstance(exercise, str) else exercise
        self.payment_type = PaymentType(payment_type) if isinstance(payment_type, str) else payment_type
        self._maturity = parse_tenor(maturity) if isinstance(maturity, str) else float(maturity)
        self.underlying_id = underlying_id
        self.discrete_obs_interval = discrete_obs_interval
        self.t_step_per_year = t_step_per_year

    @property
    def maturity(self) -> float:
        return self._maturity

    @property
    def supported_engines(self) -> set[EngineMethod]:
        return {EngineMethod.ANALYTIC, EngineMethod.MC}

    @classmethod
    def from_params(cls, params: dict, underlying_id: str) -> DigitalOption:
        exercise = params.get("exercise", ExerciseType.EUROPEAN)
        payment = params.get("payment_type", PaymentType.EXPIRE)
        if exercise == ExerciseType.AMERICAN and params.get("payment_type") is None:
            payment = PaymentType.HIT
        return cls(
            strike=params.get("strike", 100.0),
            rebate=params.get("rebate", 1.0),
            call_put=params.get("call_put", CallPut.CALL),
            exercise=exercise,
            payment_type=payment,
            maturity=params.get("maturity", "1y"),
            underlying_id=underlying_id,
            discrete_obs_interval=params.get("discrete_obs_interval"),
            t_step_per_year=int(params.get("t_step_per_year", 243)),
        )

    def payoff(self, path_or_spot: np.ndarray | float) -> float | np.ndarray:
        s = np.asarray(path_or_spot, dtype=float)
        if self.call_put == CallPut.CALL:
            return np.where(s >= self.strike, self.rebate, 0.0)
        return np.where(s <= self.strike, self.rebate, 0.0)
