"""Monte Carlo pricing engine with variance reduction."""

from __future__ import annotations

import logging

import numpy as np

from derivkit.core.enums import EngineMethod, RandsMethod
from derivkit.core.interfaces import PricingEngine, Product
from derivkit.core.rng import get_seed, normal_random
from derivkit.data.market_env import MarketEnv
from derivkit.pricing.perf.mc_kernels import simulate_gbm_terminal
from derivkit.pricing.products.vanilla import EuropeanVanilla

logger = logging.getLogger(__name__)


class McEngine(PricingEngine):
    """Monte Carlo with antithetic variates."""

    method = EngineMethod.MC

    def __init__(
        self,
        n_paths: int = 100_000,
        seed: int | None = None,
        rands_method: RandsMethod = RandsMethod.PSEUDO,
    ) -> None:
        self.n_paths = n_paths
        self.seed = seed
        self.rands_method = rands_method

    def calc_present_value(
        self,
        product: Product,
        env: MarketEnv,
        t: float | None = None,
        spot: float | None = None,
    ) -> float:
        if not isinstance(product, EuropeanVanilla):
            raise TypeError(f"McEngine supports EuropeanVanilla, got {type(product)}")

        s0 = spot if spot is not None else env.spot(product.underlying_id)
        tau = product.maturity
        if tau <= 0:
            return float(product.payoff(s0))

        r = env.rate(tau)
        q = env.div_yield(product.underlying_id)
        sigma = env.vol(product.underlying_id, tau)

        n_half = self.n_paths // 2
        effective_seed = self.seed if self.seed is not None else get_seed()
        z = normal_random(n_half, effective_seed, self.rands_method)
        z_anti = -z

        drift_tau = (r - q - 0.5 * sigma**2) * tau
        vol_sqrt_tau = sigma * np.sqrt(tau)
        s_t = np.concatenate([
            simulate_gbm_terminal(s0, drift_tau, vol_sqrt_tau, z),
            simulate_gbm_terminal(s0, drift_tau, vol_sqrt_tau, z_anti),
        ])
        payoffs = product.payoff(s_t)
        if isinstance(payoffs, float):
            payoffs = np.full(len(s_t), payoffs)
        return float(np.exp(-r * tau) * np.mean(payoffs))
