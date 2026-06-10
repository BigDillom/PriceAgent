"""Analytic cash-or-nothing digital option engine.

Adapted from PriceLib (Apache 2.0):
pricelib/pricing_engines/analytic_engines/analytic_cash_or_nothing_engine.py
"""

from __future__ import annotations

import math

from scipy.stats import norm

from derivkit.core.enums import CallPut, EngineMethod, ExerciseType, PaymentType
from derivkit.core.interfaces import PricingEngine, Product
from derivkit.data.market_env import MarketEnv
from derivkit.pricing.products.digital import DigitalOption


class AnalyticDigitalEngine(PricingEngine):
    """Closed-form cash-or-nothing digital pricer."""

    method = EngineMethod.ANALYTIC

    def calc_present_value(
        self,
        product: Product,
        env: MarketEnv,
        t: float | None = None,
        spot: float | None = None,
    ) -> float:
        if not isinstance(product, DigitalOption):
            raise TypeError(f"AnalyticDigitalEngine supports DigitalOption, got {type(product)}")

        spot = spot if spot is not None else env.spot(product.underlying_id)
        tau = product.maturity
        r = env.rate(tau)
        q = env.div_yield(product.underlying_id)
        vol = env.vol(product.underlying_id, tau)
        sign = 1 if product.call_put == CallPut.CALL else -1

        v = r - q - vol**2 / 2
        mu = (r - q) / vol**2 - 0.5
        denominator = vol * math.sqrt(tau) if tau > 0 else 1.0

        if product.exercise == ExerciseType.EUROPEAN:
            if tau <= 0:
                if (product.call_put == CallPut.CALL and spot >= product.strike) or (
                    product.call_put == CallPut.PUT and spot <= product.strike
                ):
                    return product.rebate
                return 0.0
            k_s = product.strike / spot
            return float(
                product.rebate
                * math.exp(-r * tau)
                * norm.cdf(sign * (v * tau - math.log(k_s)) / denominator)
            )

        touched = (product.call_put == CallPut.CALL and spot >= product.strike) or (
            product.call_put == CallPut.PUT and spot <= product.strike
        )
        if touched:
            if product.payment_type == PaymentType.HIT:
                return product.rebate
            return product.rebate * math.exp(-r * tau)

        if product.discrete_obs_interval is not None:
            beta = 0.5826
            adj = beta * vol * math.sqrt(product.discrete_obs_interval)
            strike = (
                product.strike * math.exp(adj)
                if product.call_put == CallPut.CALL
                else product.strike * math.exp(-adj)
            )
        else:
            strike = product.strike
        k_s = strike / spot

        if product.payment_type == PaymentType.HIT:
            lambda_ = math.sqrt(mu**2 + 2 * r / vol**2)
            return float(
                product.rebate
                * (
                    k_s ** (mu + lambda_)
                    * norm.cdf(-sign * (math.log(k_s) / denominator + lambda_ * denominator))
                    + k_s ** (mu - lambda_)
                    * norm.cdf(-sign * (math.log(k_s) / denominator - lambda_ * denominator))
                )
            )

        if product.payment_type == PaymentType.EXPIRE:
            return float(
                product.rebate
                * math.exp(-r * tau)
                * (
                    norm.cdf((v * tau - math.log(k_s)) / denominator * sign)
                    + k_s ** (2 * mu) * norm.cdf(-(v * tau + math.log(k_s)) / denominator * sign)
                )
            )

        raise ValueError(f"Unsupported payment type: {product.payment_type}")
