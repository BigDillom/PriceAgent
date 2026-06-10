"""Single-barrier option products."""

from __future__ import annotations

import numpy as np

from derivkit.core.conventions import parse_tenor
from derivkit.core.enums import (
    BarrierType,
    CallPut,
    EngineMethod,
    InOut,
    PaymentType,
    UpDown,
)
from derivkit.core.interfaces import Product


def barrier_components(barrier_type: BarrierType) -> tuple[UpDown, InOut]:
    mapping = {
        BarrierType.UP_AND_OUT: (UpDown.UP, InOut.OUT),
        BarrierType.UP_AND_IN: (UpDown.UP, InOut.IN),
        BarrierType.DOWN_AND_OUT: (UpDown.DOWN, InOut.OUT),
        BarrierType.DOWN_AND_IN: (UpDown.DOWN, InOut.IN),
    }
    return mapping[BarrierType(barrier_type)]


class BarrierOption(Product):
    """Single-barrier knock-in / knock-out option under BSM."""

    def __init__(
        self,
        strike: float,
        barrier: float,
        rebate: float,
        call_put: CallPut,
        barrier_type: BarrierType,
        maturity: float | str,
        underlying_id: str = "default",
        participation: float = 1.0,
        payment_type: PaymentType | None = None,
        discrete_obs_interval: float | None = None,
        t_step_per_year: int = 243,
    ) -> None:
        self.strike = float(strike)
        self.barrier = float(barrier)
        self.rebate = float(rebate)
        self.call_put = CallPut(call_put) if isinstance(call_put, str) else call_put
        self.barrier_type = BarrierType(barrier_type) if isinstance(barrier_type, str) else barrier_type
        self.updown, self.inout = barrier_components(self.barrier_type)
        self._maturity = parse_tenor(maturity) if isinstance(maturity, str) else float(maturity)
        self.underlying_id = underlying_id
        self.participation = float(participation)
        self.discrete_obs_interval = discrete_obs_interval
        self.t_step_per_year = t_step_per_year
        if payment_type is None:
            self.payment_type = PaymentType.EXPIRE if self.inout == InOut.IN else PaymentType.HIT
        else:
            self.payment_type = PaymentType(payment_type) if isinstance(payment_type, str) else payment_type

    @property
    def maturity(self) -> float:
        return self._maturity

    @property
    def supported_engines(self) -> set[EngineMethod]:
        return {EngineMethod.ANALYTIC, EngineMethod.MC}

    @classmethod
    def from_params(cls, params: dict, underlying_id: str) -> BarrierOption:
        barrier_type = params.get("barrier_type")
        if barrier_type is None:
            updown = UpDown(params.get("updown", "up"))
            inout = InOut(params.get("inout", "out"))
            key = (updown, inout)
            reverse = {
                (UpDown.UP, InOut.OUT): BarrierType.UP_AND_OUT,
                (UpDown.UP, InOut.IN): BarrierType.UP_AND_IN,
                (UpDown.DOWN, InOut.OUT): BarrierType.DOWN_AND_OUT,
                (UpDown.DOWN, InOut.IN): BarrierType.DOWN_AND_IN,
            }
            barrier_type = reverse[key]
        return cls(
            strike=params.get("strike", 100.0),
            barrier=params.get("barrier", params.get("barrier_out", 120.0)),
            rebate=params.get("rebate", 0.0),
            call_put=params.get("call_put", CallPut.CALL),
            barrier_type=barrier_type,
            maturity=params.get("maturity", "1y"),
            underlying_id=underlying_id,
            participation=params.get("participation", params.get("parti", 1.0)),
            payment_type=params.get("payment_type"),
            discrete_obs_interval=params.get("discrete_obs_interval"),
            t_step_per_year=int(params.get("t_step_per_year", 243)),
        )

    def payoff(self, path_or_spot: np.ndarray | float) -> float | np.ndarray:
        s = np.asarray(path_or_spot, dtype=float)
        sign = 1 if self.call_put == CallPut.CALL else -1
        vanilla = np.maximum(sign * (s - self.strike), 0.0) * self.participation
        if self.inout == InOut.OUT:
            if self.updown == UpDown.UP:
                return np.where(s >= self.barrier, self.rebate, vanilla)
            return np.where(s <= self.barrier, self.rebate, vanilla)
        if self.updown == UpDown.UP:
            return np.where(s >= self.barrier, vanilla, self.rebate)
        return np.where(s <= self.barrier, vanilla, self.rebate)
