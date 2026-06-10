"""Analytic Asian option engine (Kemna-Vorst / Turnbull-Wakeman).

Adapted from PriceLib (Apache 2.0):
pricelib/pricing_engines/analytic_engines/analytic_asian_engine.py
"""

from __future__ import annotations

import math

from scipy.stats import norm

from derivkit.core.enums import (
    AsianAveSubstitution,
    AverageMethod,
    CallPut,
    EngineMethod,
)
from derivkit.core.interfaces import PricingEngine, Product
from derivkit.data.market_env import MarketEnv
from derivkit.pricing.products.asian import AsianOption


class AnalyticAsianEngine(PricingEngine):
    """Closed-form Asian option pricer for average-settlement cases."""

    method = EngineMethod.ANALYTIC

    def calc_present_value(
        self,
        product: Product,
        env: MarketEnv,
        t: float | None = None,
        spot: float | None = None,
    ) -> float:
        if not isinstance(product, AsianOption):
            raise TypeError(f"AnalyticAsianEngine supports AsianOption, got {type(product)}")

        if product.enhanced:
            raise ValueError("AnalyticAsianEngine does not support enhanced Asian options")
        if product.substitute != AsianAveSubstitution.UNDERLYING:
            raise ValueError("AnalyticAsianEngine only supports average-settlement Asian options")

        spot = spot if spot is not None else env.spot(product.underlying_id)
        tau = product.maturity
        r = env.rate(tau)
        q = env.div_yield(product.underlying_id)
        vol = env.vol(product.underlying_id, tau)
        b = r - q
        sign = 1 if product.call_put == CallPut.CALL else -1

        obs_start = product.obs_start_frac * tau
        obs_end = product.obs_end_frac * tau
        t_step = product.t_step_per_year

        if product.ave_method == AverageMethod.GEOMETRIC:
            if obs_start > 1e-12 or abs(obs_end - tau) > 1e-12:
                raise ValueError("Geometric Asian analytic requires full-life averaging window")
            b_a = 0.5 * (b - vol**2 / 6)
            vol_a = vol / math.sqrt(3)
            d1 = (math.log(spot / product.strike) + (b_a + 0.5 * vol_a**2) * tau) / (vol_a * math.sqrt(tau))
            d2 = d1 - vol_a * math.sqrt(tau)
            price = sign * (
                spot * math.exp((b_a - r) * tau) * norm.cdf(sign * d1)
                - product.strike * math.exp(-r * tau) * norm.cdf(sign * d2)
            )
            return price * product.participation

        if product.ave_method == AverageMethod.ARITHMETIC:
            if abs(obs_end - tau) > 1e-12:
                raise ValueError("Arithmetic Asian analytic requires obs_end at maturity")

            t1 = max(obs_start, 0.0)
            t2 = obs_end - obs_start
            tau_adj = t2 - tau
            if b == 0:
                m1 = 1.0
            else:
                m1 = (math.exp(b * tau) - math.exp(b * t1)) / (b * tau - b * t1) if tau != t1 else 1.0

            if tau_adj > 0:
                if product.s_average is None:
                    raise ValueError("s_average required when already inside averaging window")
                strike_hat = t2 / tau * product.strike - tau_adj / tau * product.s_average
                if strike_hat < 0:
                    if product.call_put == CallPut.CALL:
                        s_a = product.s_average * (t2 - tau) / t2 + spot * m1 * tau / t2
                        return max(s_a - product.strike, 0.0) * math.exp(-r * tau) * product.participation
                    return 0.0
            else:
                strike_hat = product.strike

            if b == 0:
                m2 = (
                    2 * math.exp(vol**2 * tau)
                    - 2 * math.exp(vol**2 * t1) * (1 + vol**2 * (tau - t1))
                ) / (vol**4 * (tau - t1) ** 2)
            else:
                m2 = (
                    2 * math.exp((2 * b + vol**2) * tau)
                ) / ((b + vol**2) * (2 * b + vol**2) * (tau - t1) ** 2) + (
                    2 * math.exp((2 * b + vol**2) * t1)
                ) / (b * (tau - t1) ** 2) * (
                    1 / (2 * b + vol**2) - math.exp(b * (tau - t1)) / (b + vol**2)
                )

            b_a = math.log(m1) / tau if tau > 0 else 0.0
            vol_a = math.sqrt(max(math.log(m2) / tau - 2 * b_a, 0.0)) if tau > 0 else 0.0
            d1 = (math.log(spot / strike_hat) + (b_a + 0.5 * vol_a**2) * tau) / (vol_a * math.sqrt(tau))
            d2 = d1 - vol_a * math.sqrt(tau)
            price = sign * (
                spot * math.exp((b_a - r) * tau) * norm.cdf(sign * d1)
                - strike_hat * math.exp(-r * tau) * norm.cdf(sign * d2)
            )
            if tau_adj > 0:
                price = price * tau / t2
            return price * product.participation

        raise ValueError(f"Unknown average method: {product.ave_method}")
