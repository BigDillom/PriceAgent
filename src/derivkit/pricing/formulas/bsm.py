"""Black-Scholes-Merton formulas.

Adapted from PriceLib (Apache 2.0, Galaxy Technologies):
pricelib/pricing_engines/analytic_engines/analytic_vanilla_european_engine.py
"""

from __future__ import annotations

import math

from scipy.stats import norm


def bs_d1(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    return (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))


def bs_d2(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    return bs_d1(S, K, T, r, sigma, q) - sigma * math.sqrt(T)


def bs_call_put(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    sign: int = 1,
    q: float = 0.0,
) -> float:
    """European call (sign=1) or put (sign=-1) under BSM."""
    if T <= 0:
        return max(sign * (S - K), 0.0)
    d1 = bs_d1(S, K, T, r, sigma, q)
    d2 = d1 - sigma * math.sqrt(T)
    return float(
        sign * math.exp(-q * T) * S * norm.cdf(sign * d1)
        - sign * math.exp(-r * T) * K * norm.cdf(sign * d2)
    )


def bs_delta(
    S: float, K: float, T: float, r: float, sigma: float, sign: int, q: float = 0.0
) -> float:
    if T <= 0:
        return float(sign) if sign * (S - K) > 0 else 0.0
    return float(sign * math.exp(-q * T) * norm.cdf(sign * bs_d1(S, K, T, r, sigma, q)))


def bs_gamma(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    if T <= 0:
        return 0.0
    d1 = bs_d1(S, K, T, r, sigma, q)
    return float(math.exp(-q * T) * norm.pdf(d1) / (S * sigma * math.sqrt(T)))


def bs_vega(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Vega per 1% vol bump (industry convention)."""
    if T <= 0:
        return 0.0
    d1 = bs_d1(S, K, T, r, sigma, q)
    return float(math.exp(-q * T) * S * norm.pdf(d1) * math.sqrt(T) * 0.01)


def bs_rho(
    S: float, K: float, T: float, r: float, sigma: float, sign: int, q: float = 0.0
) -> float:
    """Rho per 1% rate bump."""
    if T <= 0:
        return 0.0
    d2 = bs_d2(S, K, T, r, sigma, q)
    return float(sign * K * T * math.exp(-r * T) * norm.cdf(sign * d2) * 0.01)


def bs_theta(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    sign: int,
    q: float = 0.0,
    annual_days: float = 365.0,
) -> float:
    """Theta per calendar day."""
    if T <= 0:
        return 0.0
    d1 = bs_d1(S, K, T, r, sigma, q)
    d2 = bs_d2(S, K, T, r, sigma, q)
    theta = (
        -S * math.exp(-q * T) * norm.pdf(d1) * sigma / (2 * math.sqrt(T))
        - sign * r * K * math.exp(-r * T) * norm.cdf(sign * d2)
        + sign * q * S * math.exp(-q * T) * norm.cdf(sign * d1)
    )
    return float(theta / annual_days)
