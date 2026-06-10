"""Monte Carlo engine for standard snowball products.

Logic adapted from PriceLib (Apache 2.0):
pricelib/pricing_engines/mc_engines/mc_autocallable_engine.py
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
from derivkit.pricing.products.snowball import StandardSnowball

logger = logging.getLogger(__name__)


class McSnowballEngine(PricingEngine):
    """MC pricing for standard snowball with monthly knock-out observation."""

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
        if not isinstance(product, StandardSnowball):
            raise TypeError(f"McSnowballEngine supports StandardSnowball, got {type(product)}")

        s0 = spot if spot is not None else env.spot(product.underlying_id)
        tau = product.maturity
        r = env.rate(tau)
        q = env.div_yield(product.underlying_id)
        sigma = env.vol(product.underlying_id, tau)
        val_date = env.valuation_date

        n_steps = max(int(tau * product.t_step_per_year), 1)
        dt = tau / n_steps
        effective_seed = self.seed if self.seed is not None else get_seed()

        n_half = self.n_paths // 2
        z = normal_random((n_half, n_steps), effective_seed, self.rands_method)
        paths = simulate_gbm_paths_from_shocks(s0, r, q, sigma, dt, z)
        paths_anti = simulate_gbm_paths_from_shocks(s0, r, q, sigma, dt, -z)
        all_paths = np.vstack([paths, paths_anti])
        n_path = all_paths.shape[0]

        obs_indices = self._obs_indices(val_date, product, n_steps, dt)
        if not obs_indices:
            obs_indices = [n_steps]

        barrier_out = product._barrier_out
        barrier_in = product._barrier_in
        coupon_out = product._coupon_out

        knock_out_date = np.full(n_path, np.inf)
        for i, obs_idx in enumerate(obs_indices):
            bo = barrier_out[min(i, len(barrier_out) - 1)]
            hit = all_paths[:, obs_idx] >= bo
            knock_out_date = np.where(hit & (obs_indices[i] < knock_out_date), obs_idx, knock_out_date)

        not_knocked_out = knock_out_date == np.inf
        ki_level = barrier_in[0] if len(barrier_in) else product.barrier_in
        knocked_in = np.any(all_paths <= ki_level, axis=1)

        pv_total = 0.0
        disc = lambda t_ann: np.exp(-r * t_ann)

        for p in range(n_path):
            if knock_out_date[p] < np.inf:
                obs_i = int(knock_out_date[p])
                ci = min(
                    next((j for j, oi in enumerate(obs_indices) if oi == obs_i), 0),
                    len(coupon_out) - 1,
                )
                coupon = coupon_out[ci]
                t_pay = (obs_i / n_steps) * tau
                payoff = product.s0 * (coupon * t_pay + product.margin_lvl)
                pv_total += payoff * disc(t_pay)
            elif not knocked_in[p]:
                payoff = product.s0 * (product.coupon_div * tau + product.margin_lvl)
                pv_total += payoff * disc(tau)
            else:
                s_t = all_paths[p, -1]
                loss = max(min(s_t - product.strike_upper, 0), product.strike_lower - product.strike_upper)
                payoff = loss * product.parti_in + product.margin_lvl * product.s0
                pv_total += payoff * disc(tau)

        return float(pv_total / n_path)

    @staticmethod
    def _obs_indices(
        val_date: date, product: StandardSnowball, n_steps: int, dt: float
    ) -> list[int]:
        indices: list[int] = []
        start = val_date
        for obs in product.obs_dates:
            days = (obs - start).days
            if days < 0:
                continue
            t_years = days / product.annual_days
            idx = int(round(t_years / dt)) if dt > 0 else n_steps
            idx = min(max(idx, 1), n_steps)
            indices.append(idx)
        return sorted(set(indices))
