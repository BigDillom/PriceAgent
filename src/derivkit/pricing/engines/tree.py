"""Binomial/trinomial tree pricing engine."""

from __future__ import annotations

import logging
import math

import numpy as np

from derivkit.core.enums import EngineMethod
from derivkit.core.interfaces import PricingEngine, Product
from derivkit.data.market_env import MarketEnv
from derivkit.pricing.products.vanilla import EuropeanVanilla

logger = logging.getLogger(__name__)


class TreeEngine(PricingEngine):
    """CRR binomial tree for European/American options."""

    method = EngineMethod.TREE

    def __init__(self, n_steps: int = 200) -> None:
        self.n_steps = n_steps

    def calc_present_value(
        self,
        product: Product,
        env: MarketEnv,
        t: float | None = None,
        spot: float | None = None,
    ) -> float:
        if not isinstance(product, EuropeanVanilla):
            raise TypeError(f"TreeEngine supports EuropeanVanilla, got {type(product)}")

        s0 = spot if spot is not None else env.spot(product.underlying_id)
        k = product.strike
        tau = product.maturity
        if tau <= 0:
            return float(product.payoff(s0))

        r = env.rate(tau)
        q = env.div_yield(product.underlying_id)
        sigma = env.vol(product.underlying_id, tau)
        n = self.n_steps
        dt = tau / n
        u = math.exp(sigma * math.sqrt(dt))
        d = 1.0 / u
        p = (math.exp((r - q) * dt) - d) / (u - d)
        disc = math.exp(-r * dt)

        # Terminal payoffs
        spots = s0 * u ** np.arange(n, -1, -1) * d ** np.arange(0, n + 1)
        values = (
            np.maximum(spots - k, 0.0)
            if product.call_put.value == "call"
            else np.maximum(k - spots, 0.0)
        )

        # Backward induction
        for _ in range(n):
            values = disc * (p * values[:-1] + (1 - p) * values[1:])
            if product.exercise.value == "american":
                spots_step = spots[: len(values)]
                intrinsic = (
                    np.maximum(spots_step - k, 0.0)
                    if product.call_put.value == "call"
                    else np.maximum(k - spots_step, 0.0)
                )
                values = np.maximum(values, intrinsic)
                spots = spots[1:-1] if len(spots) > 2 else spots

        return float(values[0])
