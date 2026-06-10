"""Analytic barrier option engine (Merton / Reiner-Rubinstein).

Adapted from PriceLib (Apache 2.0):
pricelib/pricing_engines/analytic_engines/analytic_barrier_engine.py
"""

from __future__ import annotations

import numpy as np
from scipy.stats import norm

from derivkit.core.enums import BarrierType, CallPut, EngineMethod, InOut, UpDown
from derivkit.core.interfaces import PricingEngine, Product
from derivkit.data.market_env import MarketEnv
from derivkit.pricing.formulas.bsm import bs_call_put
from derivkit.pricing.products.barrier import BarrierOption


class AnalyticBarrierEngine(PricingEngine):
    """Closed-form single-barrier option pricer."""

    method = EngineMethod.ANALYTIC

    def __init__(self, for_haug: bool = False) -> None:
        self.for_haug = for_haug

    def calc_present_value(
        self,
        product: Product,
        env: MarketEnv,
        t: float | None = None,
        spot: float | None = None,
    ) -> float:
        if not isinstance(product, BarrierOption):
            raise TypeError(f"AnalyticBarrierEngine supports BarrierOption, got {type(product)}")

        if product.inout == InOut.IN:
            assert product.payment_type.value == "expire"
        if product.inout == InOut.OUT:
            assert product.payment_type.value == "hit"

        spot = spot if spot is not None else env.spot(product.underlying_id)
        tau = product.maturity
        r = env.rate(tau)
        q = env.div_yield(product.underlying_id)
        vol = env.vol(product.underlying_id, tau)
        drift = r - q
        sign = 1 if product.call_put == CallPut.CALL else -1

        if tau <= 0:
            payoff = product.payoff(spot)
            return float(np.asarray(payoff).item())

        if not self.for_haug:
            touched = (
                product.updown == UpDown.UP and spot >= product.barrier
            ) or (product.updown == UpDown.DOWN and spot <= product.barrier)
            if touched:
                if product.inout == InOut.OUT:
                    return product.rebate
                return bs_call_put(spot, product.strike, tau, r, vol, sign, q)

        if product.discrete_obs_interval is not None:
            beta = 0.5826
            adj = beta * vol * np.sqrt(product.discrete_obs_interval)
            barrier = (
                product.barrier * np.exp(adj)
                if product.updown == UpDown.UP
                else product.barrier * np.exp(-adj)
            )
        else:
            barrier = product.barrier

        mu = drift / vol**2 - 0.5
        la = np.sqrt(mu**2 + 2 * r / vol**2)
        a = (barrier / spot) ** (2 * mu)
        b = (barrier / spot) ** (2 * mu + 2)
        c = (barrier / spot) ** (mu + la)
        d = (barrier / spot) ** (mu - la)
        a1 = np.log(spot / product.strike)
        a2 = np.log(spot / barrier)
        a3 = np.log(spot * product.strike / barrier**2)
        a4 = drift + 0.5 * vol**2
        a5 = drift - 0.5 * vol**2
        a6 = tau
        a7 = vol * np.sqrt(a6)
        d1 = (a1 + a4 * a6) / a7
        d2 = (a1 + a5 * a6) / a7
        d3 = (a2 + a4 * a6) / a7
        d4 = (a2 + a5 * a6) / a7
        d5 = (a2 - a5 * a6) / a7
        d6 = (a2 - a4 * a6) / a7
        d7 = (a3 - a5 * a6) / a7
        d8 = (a3 - a4 * a6) / a7
        d9 = -a2 / a7 + la * a7
        d10 = -a2 / a7 - la * a7

        def A(phi: int) -> float:
            return float(
                phi * spot * np.exp(-q * a6) * norm.cdf(phi * d1)
                - phi * product.strike * np.exp(-r * a6) * norm.cdf(phi * d2)
            )

        def B(phi: int) -> float:
            return float(
                phi * spot * np.exp(-q * a6) * norm.cdf(phi * d3)
                - phi * product.strike * np.exp(-r * a6) * norm.cdf(phi * d4)
            )

        def C(phi: int, eta: int) -> float:
            return float(
                phi * spot * np.exp(-q * a6) * b * norm.cdf(-eta * d8)
                - phi * product.strike * np.exp(-r * a6) * a * norm.cdf(-eta * d7)
            )

        def D(phi: int, eta: int) -> float:
            return float(
                phi * spot * np.exp(-q * a6) * b * norm.cdf(-eta * d6)
                - phi * product.strike * np.exp(-r * a6) * a * norm.cdf(-eta * d5)
            )

        def E(eta: int) -> float:
            return float(
                product.rebate * np.exp(-r * a6) * (norm.cdf(eta * d4) - a * norm.cdf(-eta * d5))
            )

        def F(eta: int) -> float:
            return float(product.rebate * (c * norm.cdf(eta * d9) + d * norm.cdf(eta * d10)))

        category = _barrier_category(product.barrier_type, product.call_put)
        price = _price_by_category(
            category, product.strike, barrier, A, B, C, D, E, F
        )
        return price * product.participation


def _barrier_category(barrier_type: BarrierType, call_put: CallPut) -> str:
    mapping = {
        (BarrierType.UP_AND_IN, CallPut.CALL): "UIC",
        (BarrierType.UP_AND_IN, CallPut.PUT): "UIP",
        (BarrierType.UP_AND_OUT, CallPut.CALL): "UOC",
        (BarrierType.UP_AND_OUT, CallPut.PUT): "UOP",
        (BarrierType.DOWN_AND_IN, CallPut.CALL): "DIC",
        (BarrierType.DOWN_AND_IN, CallPut.PUT): "DIP",
        (BarrierType.DOWN_AND_OUT, CallPut.CALL): "DOC",
        (BarrierType.DOWN_AND_OUT, CallPut.PUT): "DOP",
    }
    return mapping[(BarrierType(barrier_type), CallPut(call_put))]


def _price_by_category(category, strike, barrier, A, B, C, D, E, F) -> float:
    if category == "UIC":
        phi, eta = 1, -1
        return A(phi) + E(eta) if strike >= barrier else (B(phi) - C(phi, eta) + D(phi, eta)) + E(eta)
    if category == "UIP":
        phi, eta = -1, -1
        return (A(phi) - B(phi) + D(phi, eta)) + E(eta) if strike >= barrier else C(phi, eta) + E(eta)
    if category == "UOC":
        phi, eta = 1, -1
        return F(eta) if strike >= barrier else (A(phi) - B(phi) + C(phi, eta) - D(phi, eta)) + F(eta)
    if category == "UOP":
        phi, eta = -1, -1
        return (B(phi) - D(phi, eta)) + F(eta) if strike >= barrier else (A(phi) - C(phi, eta)) + F(eta)
    if category == "DIC":
        phi, eta = 1, 1
        return C(phi, eta) + E(eta) if strike >= barrier else (A(phi) - B(phi) + D(phi, eta)) + E(eta)
    if category == "DIP":
        phi, eta = -1, 1
        return (B(phi) - C(phi, eta) + D(phi, eta)) + E(eta) if strike >= barrier else A(phi) + E(eta)
    if category == "DOC":
        phi, eta = 1, 1
        return (A(phi) - C(phi, eta)) + F(eta) if strike >= barrier else (B(phi) - D(phi, eta)) + F(eta)
    if category == "DOP":
        phi, eta = -1, 1
        return (A(phi) - B(phi) + C(phi, eta) - D(phi, eta)) + F(eta) if strike >= barrier else F(eta)
    raise ValueError(f"Unknown barrier category: {category}")
