"""Asian average-price options."""

from __future__ import annotations

import numpy as np

from derivkit.core.conventions import parse_tenor
from derivkit.core.enums import (
    AsianAveSubstitution,
    AverageMethod,
    CallPut,
    EngineMethod,
)
from derivkit.core.interfaces import Product


class AsianOption(Product):
    """Asian option with geometric or arithmetic averaging."""

    def __init__(
        self,
        strike: float,
        call_put: CallPut,
        ave_method: AverageMethod = AverageMethod.GEOMETRIC,
        substitute: AsianAveSubstitution = AsianAveSubstitution.UNDERLYING,
        maturity: float | str = "1y",
        underlying_id: str = "default",
        participation: float = 1.0,
        obs_start_frac: float = 0.0,
        obs_end_frac: float = 1.0,
        s_average: float | None = None,
        enhanced: bool = False,
        limited_price: float | None = None,
        t_step_per_year: int = 243,
    ) -> None:
        self.strike = float(strike)
        self.call_put = CallPut(call_put) if isinstance(call_put, str) else call_put
        self.ave_method = AverageMethod(ave_method) if isinstance(ave_method, str) else ave_method
        self.substitute = (
            AsianAveSubstitution(substitute) if isinstance(substitute, str) else substitute
        )
        self._maturity = parse_tenor(maturity) if isinstance(maturity, str) else float(maturity)
        self.underlying_id = underlying_id
        self.participation = float(participation)
        self.obs_start_frac = float(obs_start_frac)
        self.obs_end_frac = float(obs_end_frac)
        self.s_average = s_average
        self.enhanced = enhanced
        self.limited_price = limited_price
        self.t_step_per_year = t_step_per_year
        if enhanced and limited_price is None:
            raise ValueError("enhanced Asian requires limited_price")

    @property
    def maturity(self) -> float:
        return self._maturity

    @property
    def supported_engines(self) -> set[EngineMethod]:
        if self.enhanced or self.substitute == AsianAveSubstitution.STRIKE:
            return {EngineMethod.MC}
        return {EngineMethod.ANALYTIC, EngineMethod.MC}

    @classmethod
    def from_params(cls, params: dict, underlying_id: str) -> AsianOption:
        return cls(
            strike=params.get("strike", 100.0),
            call_put=params.get("call_put", CallPut.CALL),
            ave_method=params.get("ave_method", AverageMethod.GEOMETRIC),
            substitute=params.get("substitute", AsianAveSubstitution.UNDERLYING),
            maturity=params.get("maturity", "1y"),
            underlying_id=underlying_id,
            participation=params.get("participation", params.get("parti", 1.0)),
            obs_start_frac=float(params.get("obs_start_frac", 0.0)),
            obs_end_frac=float(params.get("obs_end_frac", 1.0)),
            s_average=params.get("s_average"),
            enhanced=bool(params.get("enhanced", False)),
            limited_price=params.get("limited_price"),
            t_step_per_year=int(params.get("t_step_per_year", 243)),
        )

    def payoff(self, path_or_spot: np.ndarray | float) -> float | np.ndarray:
        s = np.asarray(path_or_spot, dtype=float)
        sign = 1 if self.call_put == CallPut.CALL else -1
        return np.maximum(sign * (s - self.strike), 0.0) * self.participation
