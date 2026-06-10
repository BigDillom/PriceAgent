"""Volatility calibration: historical and implied (BSM)."""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from derivkit.core.conventions import parse_tenor
from derivkit.core.enums import CallPut
from derivkit.pricing.formulas.bsm import bs_call_put

logger = logging.getLogger(__name__)


def historical_volatility(
    prices: pd.Series,
    *,
    window: int | None = None,
    annualization: float = 243.0,
) -> tuple[float, dict[str, Any]]:
    """Close-to-close log-return historical volatility (annualized).

    Args:
        prices: Price series indexed by time (uses values only).
        window: Rolling window length in observations. Defaults to all returns.
        annualization: Trading days per year for scaling (243 for CN futures).

    Returns:
        (sigma, meta) with sigma as decimal (0.22 = 22%).
    """
    series = prices.dropna().astype(float)
    if len(series) < 2:
        raise ValueError("Need at least 2 prices for historical volatility")

    log_returns = np.log(series / series.shift(1)).dropna()
    n_returns = len(log_returns)
    requested = window
    win = window or n_returns
    if win < 1:
        raise ValueError("window must be >= 1")
    window_adjusted = False
    if n_returns < win:
        win = n_returns
        window_adjusted = True

    sample = log_returns.iloc[-win:]
    if len(sample) < 2:
        raise ValueError(
            f"Need at least 2 returns for historical vol, got {len(sample)} "
            f"(n_obs={len(series)}). Increase lookback_days or use a longer series."
        )
    daily_std = float(sample.std(ddof=1))
    sigma = daily_std * math.sqrt(annualization)

    meta = {
        "method": "historical",
        "window": win,
        "requested_window": requested,
        "window_adjusted": window_adjusted,
        "n_obs": int(len(series)),
        "n_returns": n_returns,
        "annualization": annualization,
        "daily_std": daily_std,
        "start": str(series.index[0]),
        "end": str(series.index[-1]),
    }
    return sigma, meta


def implied_volatility(
    market_price: float,
    spot: float,
    strike: float,
    maturity: float | str,
    rate: float,
    call_put: CallPut | str = CallPut.CALL,
    div_yield: float = 0.0,
    *,
    vol_bounds: tuple[float, float] = (1e-6, 5.0),
) -> tuple[float, dict[str, Any]]:
    """Invert BSM price to implied volatility via Brent root-finding."""
    t = parse_tenor(maturity) if isinstance(maturity, str) else float(maturity)
    if t <= 0:
        raise ValueError("Maturity must be positive for implied vol")
    if market_price <= 0:
        raise ValueError("market_price must be positive")

    cp = CallPut(call_put) if isinstance(call_put, str) else call_put
    sign = 1 if cp == CallPut.CALL else -1
    intrinsic = max(sign * (spot - strike), 0.0)
    if market_price < intrinsic - 1e-10:
        raise ValueError(
            f"market_price {market_price} below intrinsic {intrinsic} for {cp.value}"
        )

    def objective(sigma: float) -> float:
        return bs_call_put(spot, strike, t, rate, sigma, sign, div_yield) - market_price

    lo, hi = vol_bounds
    f_lo, f_hi = objective(lo), objective(hi)
    if f_lo * f_hi > 0:
        raise ValueError(
            f"Cannot bracket implied vol: price={market_price}, spot={spot}, "
            f"strike={strike}, T={t}"
        )

    sigma = float(brentq(objective, lo, hi))
    model_price = bs_call_put(spot, strike, t, rate, sigma, sign, div_yield)
    meta = {
        "method": "implied",
        "market_price": market_price,
        "model_price": model_price,
        "price_error": abs(model_price - market_price),
        "spot": spot,
        "strike": strike,
        "maturity_years": t,
        "rate": rate,
        "div_yield": div_yield,
        "call_put": cp.value,
    }
    return sigma, meta
