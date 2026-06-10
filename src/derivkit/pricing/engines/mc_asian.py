"""Monte Carlo engine for Asian options.

Adapted from PriceLib (Apache 2.0):
pricelib/pricing_engines/mc_engines/mc_asian_engine.py
"""

from __future__ import annotations

import numpy as np

from derivkit.core.enums import (
    AsianAveSubstitution,
    AverageMethod,
    CallPut,
    EngineMethod,
    RandsMethod,
)
from derivkit.core.interfaces import PricingEngine, Product
from derivkit.core.rng import get_seed
from derivkit.data.market_env import MarketEnv
from derivkit.pricing.engines.mc_paths import simulate_gbm_paths
from derivkit.pricing.products.asian import AsianOption


class McAsianEngine(PricingEngine):
    """MC pricer for Asian average-price options."""

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
        if not isinstance(product, AsianOption):
            raise TypeError(f"McAsianEngine supports AsianOption, got {type(product)}")

        spot = spot if spot is not None else env.spot(product.underlying_id)
        tau = product.maturity
        if tau <= 0:
            return float(np.asarray(product.payoff(spot)).item())

        r = env.rate(tau)
        q = env.div_yield(product.underlying_id)
        sigma = env.vol(product.underlying_id, tau)
        n_steps = max(int(tau * product.t_step_per_year), 1)
        effective_seed = self.seed if self.seed is not None else get_seed()
        paths = simulate_gbm_paths(
            spot, r, q, sigma, tau, n_steps, self.n_paths, effective_seed, self.rands_method
        )

        obs_start = int(round(product.obs_start_frac * n_steps))
        obs_end = int(round(product.obs_end_frac * n_steps))
        obs_steps = np.arange(obs_start, max(obs_end, obs_start + 1), 1, dtype=int)
        obs_steps = np.minimum(obs_steps, n_steps)
        sign = 1 if product.call_put == CallPut.CALL else -1
        terminal = paths[:, -1]

        if product.substitute == AsianAveSubstitution.UNDERLYING:
            obs_paths = paths[:, obs_steps]
            if product.enhanced:
                assert product.limited_price is not None
                obs_paths = obs_paths + sign * np.maximum(
                    sign * (product.limited_price - obs_paths), 0.0
                )
            if product.ave_method == AverageMethod.ARITHMETIC:
                ave_s = np.mean(obs_paths, axis=1)
            elif product.ave_method == AverageMethod.GEOMETRIC:
                ave_s = np.exp(np.mean(np.log(obs_paths), axis=1))
            else:
                raise ValueError("ave_method must be geometric or arithmetic")
            payoff = np.maximum(sign * (ave_s - product.strike), 0.0) * product.participation
            return float(np.mean(payoff) * np.exp(-r * tau))

        if product.substitute == AsianAveSubstitution.STRIKE:
            obs_paths = paths[:, obs_steps]
            if product.ave_method == AverageMethod.ARITHMETIC:
                ave_s = np.mean(obs_paths, axis=1)
            elif product.ave_method == AverageMethod.GEOMETRIC:
                ave_s = np.exp(np.mean(np.log(obs_paths), axis=1))
            else:
                raise ValueError("ave_method must be geometric or arithmetic")
            payoff = np.maximum(sign * (terminal - ave_s), 0.0) * product.participation
            return float(np.mean(payoff) * np.exp(-r * tau))

        raise ValueError("substitute must be underlying or strike")
