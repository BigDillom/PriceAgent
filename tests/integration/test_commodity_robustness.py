"""W8 extreme-event robustness tests (ASF-style hog price shock)."""

from __future__ import annotations

from pathlib import Path

import pytest

import derivkit as dk
from derivkit.dsl.loader import load_spec

COMMODITY_DIR = Path(__file__).resolve().parents[2] / "examples" / "commodity"


@pytest.mark.integration
def test_asf_shock_lowers_call_pv():
    baseline = dk.price(load_spec(COMMODITY_DIR / "lh_robustness_baseline.yaml"))
    shocked = dk.price(load_spec(COMMODITY_DIR / "lh_robustness_asf.yaml"))
    assert baseline.meta["alignment"]["aligned_spots"]["LH2409"] == 15520.0
    assert shocked.meta["alignment"]["aligned_spots"]["LH2409"] == 12500.0
    assert shocked.pv < baseline.pv


@pytest.mark.integration
def test_asf_shock_delta_sensitivity():
    baseline_spec = load_spec(COMMODITY_DIR / "lh_robustness_baseline.yaml").to_dict()
    shocked_spec = load_spec(COMMODITY_DIR / "lh_robustness_asf.yaml").to_dict()
    baseline_spec["output"]["fields"] = ["pv", "delta"]
    shocked_spec["output"]["fields"] = ["pv", "delta"]
    baseline = dk.price(baseline_spec)
    shocked = dk.price(shocked_spec)
    assert shocked.greeks["delta"] < baseline.greeks["delta"]


@pytest.mark.integration
def test_robustness_higher_vol_increases_option_value():
    spec = load_spec(COMMODITY_DIR / "lh_robustness_baseline.yaml")
    low_vol = spec.to_dict()
    high_vol = spec.to_dict()
    high_vol["market"]["vols"][0]["value"] = 0.45
    result_low = dk.price(low_vol)
    result_high = dk.price(high_vol)
    assert result_high.pv > result_low.pv
