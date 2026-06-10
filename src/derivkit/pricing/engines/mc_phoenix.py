"""Monte Carlo engine for Phoenix / FCN autocallable products.

Adapted from PriceLib (Apache 2.0):
pricelib/pricing_engines/mc_engines/mc_phoenix_engine.py
"""

from __future__ import annotations

import logging
from datetime import date

import numpy as np

from derivkit.core.enums import EngineMethod, RandsMethod
from derivkit.core.interfaces import PricingEngine, Product
from derivkit.core.rng import get_seed, normal_random
from derivkit.data.market_env import MarketEnv
from derivkit.pricing.engines.mc_paths import simulate_gbm_paths_from_shocks
from derivkit.pricing.products.fcn import FCN
from derivkit.pricing.products.phoenix import Phoenix

logger = logging.getLogger(__name__)

PhoenixProduct = Phoenix | FCN


class McPhoenixEngine(PricingEngine):
    """MC pricing for Phoenix and FCN structures."""

    method = EngineMethod.MC

    def __init__(
        self,
        n_paths: int = 100_000,
        seed: int | None = None,
        rands_method: RandsMethod = RandsMethod.PSEUDO,
        t_step_per_year: int = 243,
    ) -> None:
        self.n_paths = n_paths
        self.seed = seed
        self.rands_method = rands_method
        self.t_step_per_year = t_step_per_year

    def calc_present_value(
        self,
        product: Product,
        env: MarketEnv,
        t: float | None = None,
        spot: float | None = None,
    ) -> float:
        if not isinstance(product, (Phoenix, FCN)):
            raise TypeError(f"McPhoenixEngine supports Phoenix/FCN, got {type(product)}")

        s0 = spot if spot is not None else env.spot(product.underlying_id)
        tau = product.maturity
        r = env.rate(tau)
        val_date = env.valuation_date

        n_steps = max(int(tau * product.t_step_per_year), 1)
        dt = tau / n_steps
        effective_seed = self.seed if self.seed is not None else get_seed()

        n_half = self.n_paths // 2
        z = normal_random((n_half, n_steps), effective_seed, self.rands_method)
        sigma = env.vol(product.underlying_id, tau)
        q = env.div_yield(product.underlying_id)
        paths = simulate_gbm_paths_from_shocks(s0, r, q, sigma, dt, z)
        paths_anti = simulate_gbm_paths_from_shocks(s0, r, q, sigma, dt, -z)
        all_paths = np.vstack([paths, paths_anti])  # shape (n_path, n_steps+1)
        n_path = all_paths.shape[0]

        obs_indices = self._obs_indices(val_date, product, n_steps, dt)
        if not obs_indices:
            obs_indices = [n_steps]

        n_obs = len(obs_indices)
        barrier_out = product._barrier_out[-n_obs:].copy()
        barrier_yield = product._barrier_yield[-n_obs:].copy()
        barrier_in = product._barrier_in[-n_obs:].copy()
        coupon = product._coupon[-n_obs:].copy()
        pay_times = np.array([idx / n_steps * tau for idx in obs_indices])

        knock_out_time = np.full(n_path, np.inf)
        for i, obs_idx in enumerate(obs_indices):
            bo = barrier_out[min(i, len(barrier_out) - 1)]
            if np.isinf(bo):
                continue
            hit = all_paths[:, obs_idx] >= bo
            knock_out_time = np.where(hit & (obs_idx < knock_out_time), obs_idx, knock_out_time)

        knock_out_scenario = knock_out_time < np.inf
        hold_idx = knock_out_time.copy()
        hold_idx[~knock_out_scenario] = obs_indices[-1]

        prices_at_obs = all_paths[:, obs_indices].T  # (n_obs, n_path)
        barrier_yield_tiled = barrier_yield[:, np.newaxis]
        obs_mat = np.array(obs_indices)[:, np.newaxis]
        coupon_bool = prices_at_obs > barrier_yield_tiled
        coupon_bool = np.where(obs_mat > knock_out_time, False, coupon_bool)

        if isinstance(product, FCN):
            knocked_in = all_paths[:, -1] <= barrier_in[-1]
        else:
            ki_levels = barrier_in[0]
            knocked_in = np.any(all_paths <= ki_levels, axis=1)
        knock_in_scenario = np.where(knock_out_scenario, False, knocked_in)

        discount = np.exp(-r * pay_times)
        discounted_coupon = coupon * product.s0 * discount

        payoff = 0.0
        hold_times_ann = hold_idx / n_steps * tau
        payoff += np.sum(np.exp(-r * hold_times_ann[~knock_in_scenario])) * product.margin_lvl * product.s0
        payoff += np.sum(np.sum(coupon_bool, axis=1) * discounted_coupon)

        s_end = all_paths[knock_in_scenario, -1].copy()
        s_end = np.maximum(s_end, product.strike_lower)
        n_ki = int(np.sum(knock_in_scenario))
        if n_ki:
            payoff += (
                (product.margin_lvl * product.s0 - product.strike_upper) * n_ki + np.sum(s_end)
            ) * np.exp(-r * tau)

        return float(payoff / n_path)

    @staticmethod
    def _obs_indices(
        val_date: date, product: PhoenixProduct, n_steps: int, dt: float
    ) -> list[int]:
        indices: list[int] = []
        for obs in product.obs_dates:
            days = (obs - val_date).days
            if days < 0:
                continue
            t_years = days / product.annual_days
            idx = int(round(t_years / dt)) if dt > 0 else n_steps
            idx = min(max(idx, 1), n_steps)
            indices.append(idx)
        return sorted(set(indices))
