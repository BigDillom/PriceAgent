"""Volatility calibration tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import derivkit as dk
from derivkit.data.calibration import historical_volatility, implied_volatility
from derivkit.pricing.formulas.bsm import bs_call_put

COMMODITY_DIR = Path(__file__).resolve().parents[2] / "examples" / "commodity"


def test_historical_volatility_constant_series():
    # Zero vol if prices constant
    prices = pd.Series([100.0] * 10)
    sigma, meta = historical_volatility(prices, window=5, annualization=243)
    assert sigma == pytest.approx(0.0, abs=1e-12)
    assert meta["method"] == "historical"


def test_historical_volatility_known_series():
    rng = np.random.default_rng(42)
    daily_vol = 0.01
    shocks = rng.normal(0, daily_vol, 100)
    prices = pd.Series(100.0 * np.exp(np.cumsum(shocks)))
    sigma, _ = historical_volatility(prices, window=60, annualization=243)
    expected = daily_vol * np.sqrt(243)
    assert sigma == pytest.approx(expected, rel=0.30)


def test_implied_volatility_roundtrip():
    sigma_true = 0.25
    price = bs_call_put(100, 100, 1.0, 0.05, sigma_true, 1)
    sigma, meta = implied_volatility(price, 100, 100, 1.0, 0.05, "call")
    assert sigma == pytest.approx(sigma_true, rel=1e-6)
    assert meta["price_error"] < 1e-8


def test_calibrate_historical_yaml():
    path = COMMODITY_DIR / "lh_calibrate_historical.yaml"
    result = dk.calibrate(path)
    assert result.pv > 0
    assert result.meta["calibration_method"] == "historical"
    assert result.meta["data_source"]["source"] == "csv"


def test_calibrate_implied_yaml():
    path = COMMODITY_DIR / "lh_calibrate_implied.yaml"
    result = dk.calibrate(path)
    assert result.pv > 0.15
    assert result.pv < 0.35
    assert result.meta["calibration_method"] == "implied"
    assert result.greeks["market_price"] == 738.05


def test_calibrate_then_price_workflow():
    cal = dk.calibrate(COMMODITY_DIR / "lh_calibrate_historical.yaml")
    sigma = cal.pv
    spec = {
        "task": "price",
        "market": {
            "valuation_date": "2024-06-14",
            "underlyings": [{"id": "LH2409", "asset_class": "commodity", "spot": 15520.0}],
            "rates": [{"id": "CNY_RF", "kind": "constant", "value": 0.025}],
            "vols": [{"id": "LH_IV", "kind": "constant", "value": sigma, "underlying_id": "LH2409"}],
        },
        "product": {
            "type": "vanilla.european",
            "params": {"strike": 15500, "maturity": "3m", "call_put": "call"},
        },
        "engine": {"method": "analytic"},
    }
    priced = dk.price(spec)
    assert priced.pv > 0
