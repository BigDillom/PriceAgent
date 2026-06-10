"""Tests for LLM spec normalization."""

from __future__ import annotations

import derivkit as dk
from priceagent.spec_builder import build_vanilla_spec, normalize_spec


def test_build_vanilla_spec_validates():
    spec = build_vanilla_spec(
        valuation_date="2024-06-14",
        instrument_id="LH2409",
        spot=15520.0,
        strike=15500.0,
    )
    result = dk.price(spec)
    assert result.pv > 0


def test_normalize_flat_market():
    raw = {
        "market": {"valuation_date": "2024-06-14", "spot": 100.0, "rate": 0.03, "volatility": 0.2},
        "product": {"type": "european_call", "strike": 100, "maturity": "1y"},
        "engine": "analytic",
    }
    spec = normalize_spec(raw)
    assert spec["product"]["type"] == "vanilla.european"
    assert isinstance(spec["market"]["underlyings"], list)
    assert spec["market"]["underlyings"][0]["id"] == "UNDERLYING"
    result = dk.price(spec)
    assert result.pv > 0


def test_normalize_underlyings_dict_and_name():
    raw = {
        "market": {
            "valuation_date": "2024-06-14",
            "underlyings": {"LH2409": {"spot": 17880.0, "volatility": 0.2}},
            "rate": 0.03,
        },
        "product": {"type": "vanilla.european", "params": {"strike": 15500, "maturity": "3m"}},
    }
    spec = normalize_spec(raw)
    assert spec["market"]["underlyings"][0]["id"] == "LH2409"
    assert spec["market"]["vols"][0]["value"] == 0.2
