"""Analytic (closed-form) pricing engine."""

from __future__ import annotations

import logging

from derivkit.core.enums import CallPut, EngineMethod
from derivkit.core.interfaces import PricingEngine, Product
from derivkit.data.market_env import MarketEnv
from derivkit.pricing.formulas.bsm import (
    bs_call_put,
    bs_delta,
    bs_gamma,
    bs_rho,
    bs_theta,
    bs_vega,
)
from derivkit.pricing.products.vanilla import EuropeanVanilla

logger = logging.getLogger(__name__)


class AnalyticEngine(PricingEngine):
    """Black-Scholes analytic engine for European vanillas."""

    method = EngineMethod.ANALYTIC

    def calc_present_value(
        self,
        product: Product,
        env: MarketEnv,
        t: float | None = None,
        spot: float | None = None,
    ) -> float:
        if not isinstance(product, EuropeanVanilla):
            raise TypeError(f"AnalyticEngine supports EuropeanVanilla, got {type(product)}")

        s = spot if spot is not None else env.spot(product.underlying_id)
        k = product.strike
        tau = product.maturity
        r = env.rate(tau)
        q = env.div_yield(product.underlying_id)
        sigma = env.vol(product.underlying_id, tau)
        sign = 1 if product.call_put == CallPut.CALL else -1
        return bs_call_put(s, k, tau, r, sigma, sign, q)

    def calc_greeks(
        self,
        product: Product,
        env: MarketEnv,
        which: list[str] | None = None,
    ) -> dict[str, float]:
        if not isinstance(product, EuropeanVanilla):
            return super().calc_greeks(product, env, which)

        which = which or ["delta", "gamma", "vega", "theta", "rho"]
        s = env.spot(product.underlying_id)
        k = product.strike
        tau = product.maturity
        r = env.rate(tau)
        q = env.div_yield(product.underlying_id)
        sigma = env.vol(product.underlying_id, tau)
        sign = 1 if product.call_put == CallPut.CALL else -1

        greeks: dict[str, float] = {}
        if "delta" in which:
            greeks["delta"] = bs_delta(s, k, tau, r, sigma, sign, q)
        if "gamma" in which:
            greeks["gamma"] = bs_gamma(s, k, tau, r, sigma, q)
        if "vega" in which:
            greeks["vega"] = bs_vega(s, k, tau, r, sigma, q)
        if "rho" in which:
            greeks["rho"] = bs_rho(s, k, tau, r, sigma, sign, q)
        if "theta" in which:
            greeks["theta"] = bs_theta(s, k, tau, r, sigma, sign, q)
        return greeks
