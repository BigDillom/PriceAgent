"""Black-Scholes-Merton stochastic process."""

from __future__ import annotations

import numpy as np

from derivkit.core.interfaces import StochProcess
from derivkit.data.market_env import MarketEnv


class BSMProcess(StochProcess):
    """Generalized BSM with continuous dividend yield."""

    def __init__(self, env: MarketEnv, underlying_id: str) -> None:
        self.env = env
        self.underlying_id = underlying_id

    def _params(self, t: float) -> tuple[float, float, float]:
        r = self.env.rate(t)
        q = self.env.div_yield(self.underlying_id)
        sigma = self.env.vol(self.underlying_id, t)
        return r, q, sigma

    def drift(self, t: float) -> float:
        r, q, _ = self._params(t)
        return r - q

    def diffusion(self, t: float, x: float) -> float:
        _, _, sigma = self._params(t)
        return sigma * x

    def evolve(self, t: float, x: np.ndarray, dt: float, dw: np.ndarray) -> np.ndarray:
        r, q, sigma = self._params(t)
        mu = (r - q - 0.5 * sigma**2) * dt
        vol_term = sigma * np.sqrt(dt) * dw
        return x * np.exp(mu + vol_term)

    def pde_coef(self, t: float, x: float) -> tuple[float, float, float]:
        """Coefficients for Black-Scholes PDE."""
        r, q, sigma = self._params(t)
        a = 0.5 * sigma**2 * x**2
        b = (r - q) * x
        c = -r
        return a, b, c
