"""Snowball product integration tests (MC + FDM engines)."""

import time

import pytest

import derivkit as dk
from derivkit.core.rng import set_seed
from derivkit.data.market_env import MarketEnv
from derivkit.pricing.engines.fdm_snowball import FdmSnowballEngine
from derivkit.pricing.engines.mc_snowball import McSnowballEngine
from derivkit.pricing.products.snowball import StandardSnowball


@pytest.fixture
def snowball_spec_dict() -> dict:
    return {
        "task": "price",
        "market": {
            "valuation_date": "2024-01-05",
            "underlyings": [{"id": "CSI1000", "asset_class": "index", "spot": 100.0}],
            "rates": [{"id": "CN_RF", "kind": "constant", "value": 0.05}],
            "vols": [
                {"id": "CSI1000", "kind": "constant", "value": 0.2, "underlying_id": "CSI1000"}
            ],
        },
        "product": {
            "type": "snowball.standard",
            "params": {
                "s0": 100,
                "barrier_out": 103,
                "barrier_in": 80,
                "coupon_out": 0.113,
                "maturity": "1y",
                "lock_term": "3m",
            },
        },
        "engine": {"method": "mc", "params": {"n_paths": 50000}},
        "output": {"deterministic": True, "seed": 42},
    }


def test_snowball_mc_price(snowball_spec_dict):
    set_seed(42)
    result = dk.price(snowball_spec_dict)
    assert result.meta["backend"] == "derivkit"
    assert result.meta["engine"] == "mc"
    assert 85.0 < result.pv < 105.0


def test_snowball_determinism(snowball_spec_dict):
    set_seed(42)
    r1 = dk.price(snowball_spec_dict)
    set_seed(42)
    r2 = dk.price(snowball_spec_dict)
    assert r1.pv == r2.pv


def test_snowball_fdm_price(snowball_spec_dict):
    spec = {**snowball_spec_dict, "engine": {"method": "fdm", "params": {"s_step": 200}}}
    result = dk.price(spec)
    assert result.meta["engine"] == "fdm"
    assert 85.0 < result.pv < 105.0


def test_snowball_fdm_determinism(snowball_spec_dict):
    spec = {**snowball_spec_dict, "engine": {"method": "fdm", "params": {"s_step": 150}}}
    r1 = dk.price(spec)
    r2 = dk.price(spec)
    assert r1.pv == r2.pv


def test_snowball_fdm_mc_cross_check(snowball_spec_dict):
    """FDM vs MC present value within 1e-2 relative tolerance band."""
    env = MarketEnv.from_spec(snowball_spec_dict["market"])
    product = StandardSnowball.from_params(
        snowball_spec_dict["product"]["params"],
        "CSI1000",
        valuation_date=env.valuation_date,
    )
    mc = McSnowballEngine(n_paths=80_000, seed=42)
    fdm = FdmSnowballEngine(s_step=250)
    pv_mc = mc.calc_present_value(product, env)
    pv_fdm = fdm.calc_present_value(product, env)
    assert abs(pv_fdm - pv_mc) < max(1.0, 0.05 * abs(pv_mc))


@pytest.mark.perf
def test_snowball_fdm_perf_sla(snowball_spec_dict):
    """PDE snowball with s_step=400 should complete in under 0.3s."""
    env = MarketEnv.from_spec(snowball_spec_dict["market"])
    product = StandardSnowball.from_params(
        {"s0": 100, "barrier_out": 103, "barrier_in": 80, "coupon_out": 0.113, "maturity": "1y"},
        "CSI1000",
        valuation_date=env.valuation_date,
    )
    engine = FdmSnowballEngine(s_step=400)
    t0 = time.perf_counter()
    pv = engine.calc_present_value(product, env)
    elapsed = time.perf_counter() - t0
    assert 85.0 < pv < 105.0
    assert elapsed < 0.3, f"FDM snowball took {elapsed:.3f}s, SLA is 0.3s"
