"""European and American vanilla options."""

from __future__ import annotations

import numpy as np

from derivkit.core.conventions import parse_tenor
from derivkit.core.enums import CallPut, EngineMethod, ExerciseType
from derivkit.core.interfaces import Product


class EuropeanVanilla(Product):
    """European call/put option under BSM."""

    def __init__(
        self,
        strike: float,
        maturity: float | str,
        call_put: CallPut = CallPut.CALL,
        underlying_id: str = "default",
        exercise: ExerciseType = ExerciseType.EUROPEAN,
    ) -> None:
        self.strike = float(strike)
        self._maturity = parse_tenor(maturity) if isinstance(maturity, str) else float(maturity)
        self.call_put = CallPut(call_put) if isinstance(call_put, str) else call_put
        self.underlying_id = underlying_id
        self.exercise = exercise

    @property
    def maturity(self) -> float:
        return self._maturity

    @property
    def supported_engines(self) -> set[EngineMethod]:
        if self.exercise == ExerciseType.EUROPEAN:
            return {
                EngineMethod.ANALYTIC,
                EngineMethod.TREE,
                EngineMethod.FDM,
                EngineMethod.MC,
                EngineMethod.QUAD,
            }
        return {EngineMethod.TREE, EngineMethod.FDM, EngineMethod.MC}

    def payoff(self, path_or_spot: np.ndarray | float) -> float | np.ndarray:
        s = np.asarray(path_or_spot, dtype=float)
        if self.call_put == CallPut.CALL:
            return np.maximum(s - self.strike, 0.0)
        return np.maximum(self.strike - s, 0.0)
