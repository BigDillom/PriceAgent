"""Monte Carlo engine for cash-or-nothing digital options.

Adapted from PriceLib (Apache 2.0):
pricelib/pricing_engines/mc_engines/mc_digital_engine.py
"""

from __future__ import annotations

import math

import numpy as np

from derivkit.core.enums import CallPut, EngineMethod, ExerciseType, PaymentType, RandsMethod
from derivkit.core.interfaces import PricingEngine, Product
from derivkit.core.rng import get_seed
from derivkit.data.market_env import MarketEnv
from derivkit.pricing.engines.mc_paths import simulate_gbm_paths
from derivkit.pricing.products.digital import DigitalOption


class McDigitalEngine(PricingEngine):
    """MC pricer for cash-or-nothing digitals."""

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
        if not isinstance(product, DigitalOption):
            raise TypeError(f"McDigitalEngine supports DigitalOption, got {type(product)}")

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

        if product.exercise == ExerciseType.AMERICAN:
            if product.discrete_obs_interval is None:
                obs_points = np.arange(0, n_steps + 1, 1)
            else:
                dt_step = product.discrete_obs_interval * product.t_step_per_year
                obs_points = np.flip(np.round(np.arange(n_steps, 0, -dt_step)).astype(int))
                obs_points = np.concatenate((np.array([0]), obs_points))
                obs_points = np.minimum(obs_points, n_steps)

            obs_spots = paths[:, obs_points]
            if product.call_put == CallPut.CALL:
                strike_bool = np.where(obs_spots >= product.strike, 1, 0)
            else:
                strike_bool = np.where(obs_spots <= product.strike, 1, 0)
            value = product.rebate * np.max(strike_bool, axis=0)
            if product.payment_type == PaymentType.HIT:
                strike_time = (np.argmax(strike_bool, axis=0) + 1) * (1.0 / product.t_step_per_year)
                return float(np.mean(value * np.exp(-r * strike_time)))
            return float(np.mean(value) * math.exp(-r * tau))

        terminal = paths[:, -1]
        if product.call_put == CallPut.CALL:
            payoff = (terminal >= product.strike) * product.rebate
        else:
            payoff = (terminal <= product.strike) * product.rebate
        return float(np.mean(payoff) * math.exp(-r * tau))
