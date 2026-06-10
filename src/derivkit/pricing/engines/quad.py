"""Quadrature pricing engine via log-normal density integration."""

from __future__ import annotations

import logging

import numpy as np
from scipy.integrate import simpson

from derivkit.core.enums import EngineMethod
from derivkit.core.interfaces import PricingEngine, Product
from derivkit.data.market_env import MarketEnv
from derivkit.pricing.products.vanilla import EuropeanVanilla

logger = logging.getLogger(__name__)


class QuadEngine(PricingEngine):
    """Simpson quadrature on log-normal terminal density."""

    method = EngineMethod.QUAD

    def __init__(self, n: int = 4096, n_smax: float = 8.0) -> None:
        self.n = n
        self.n_smax = n_smax

    def calc_present_value(
        self,
        product: Product,
        env: MarketEnv,
        t: float | None = None,
        spot: float | None = None,
    ) -> float:
        if not isinstance(product, EuropeanVanilla):
            raise TypeError(f"QuadEngine supports EuropeanVanilla, got {type(product)}")

        s0 = spot if spot is not None else env.spot(product.underlying_id)
        tau = product.maturity
        if tau <= 0:
            return float(product.payoff(s0))

        r = env.rate(tau)
        q = env.div_yield(product.underlying_id)
        sigma = env.vol(product.underlying_id, tau)

        s_max = s0 * self.n_smax
        spots = np.linspace(1e-8, s_max, self.n)

        mu = np.log(s0) + (r - q - 0.5 * sigma**2) * tau
        sig = sigma * np.sqrt(tau)
        log_s = np.log(spots)
        pdf = np.exp(-0.5 * ((log_s - mu) / sig) ** 2) / (spots * sig * np.sqrt(2 * np.pi))

        payoffs = np.asarray(product.payoff(spots), dtype=float)
        integral = simpson(payoffs * pdf, spots)
        return float(np.exp(-r * tau) * integral)
