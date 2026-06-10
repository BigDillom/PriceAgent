"""Monte Carlo engine for barrier options.

Adapted from PriceLib (Apache 2.0):
pricelib/pricing_engines/mc_engines/mc_barrier_engine.py
"""

from __future__ import annotations

import numpy as np

from derivkit.core.enums import CallPut, EngineMethod, InOut, PaymentType, RandsMethod, UpDown
from derivkit.core.interfaces import PricingEngine, Product
from derivkit.core.rng import get_seed
from derivkit.data.market_env import MarketEnv
from derivkit.pricing.engines.mc_paths import simulate_gbm_paths
from derivkit.pricing.products.barrier import BarrierOption


class McBarrierEngine(PricingEngine):
    """MC pricer for single-barrier options with daily discrete monitoring."""

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
        if not isinstance(product, BarrierOption):
            raise TypeError(f"McBarrierEngine supports BarrierOption, got {type(product)}")

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
        sign = 1 if product.call_put == CallPut.CALL else -1

        if product.discrete_obs_interval is None:
            obs_points = np.arange(0, n_steps + 1, 1)
        else:
            dt_step = product.discrete_obs_interval * product.t_step_per_year
            obs_points = np.flip(np.round(np.arange(n_steps, 0, -dt_step)).astype(int))
            obs_points = np.concatenate((np.array([0]), obs_points))
            obs_points = np.minimum(obs_points, n_steps)

        obs_spots = paths[:, obs_points]
        if product.updown == UpDown.UP:
            knock = np.any(obs_spots >= product.barrier, axis=1)
        else:
            knock = np.any(obs_spots <= product.barrier, axis=1)

        terminal = paths[:, -1]

        if product.inout == InOut.IN:
            payoff = np.full(paths.shape[0], product.rebate)
            payoff[knock] = np.maximum(sign * (terminal[knock] - product.strike), 0.0) * product.participation
            return float(np.mean(payoff) * np.exp(-r * tau))

        payoff = np.maximum(sign * (terminal - product.strike), 0.0) * product.participation * np.exp(-r * tau)
        if product.payment_type == PaymentType.EXPIRE:
            payoff[knock] = product.rebate * np.exp(-r * tau)
        else:
            if product.updown == UpDown.UP:
                hit_mask = obs_spots >= product.barrier
            else:
                hit_mask = obs_spots <= product.barrier
            hit_time = np.min(np.where(hit_mask, obs_points, np.inf), axis=1)
            valid = knock & (hit_time != np.inf)
            payoff[valid] = product.rebate * np.exp(-r * hit_time[valid] / product.t_step_per_year)
        return float(np.mean(payoff))
