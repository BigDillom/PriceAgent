"""Snowball Quad engine + FCN/Phoenix integration tests."""

import pytest

from derivkit.core.rng import set_seed
from derivkit.data.market_env import MarketEnv
from derivkit.pricing.engines.fdm_snowball import FdmSnowballEngine
from derivkit.pricing.engines.mc_phoenix import McPhoenixEngine
from derivkit.pricing.engines.mc_snowball import McSnowballEngine
from derivkit.pricing.engines.quad_fcn import QuadFcnEngine
from derivkit.pricing.engines.quad_snowball import QuadSnowballEngine
from derivkit.pricing.products.fcn import FCN
from derivkit.pricing.products.phoenix import Phoenix
from derivkit.pricing.products.snowball import StandardSnowball
from derivkit.verify.oracle import cross_check, default_tolerances, tolerance_for
from derivkit.dsl.schema import PricingSpec


@pytest.fixture
def snowball_env_product():
    market = {
        "valuation_date": "2024-01-05",
        "underlyings": [{"id": "CSI1000", "asset_class": "index", "spot": 100.0}],
        "rates": [{"id": "CN_RF", "kind": "constant", "value": 0.05}],
        "vols": [{"id": "CSI1000", "kind": "constant", "value": 0.2, "underlying_id": "CSI1000"}],
    }
    params = {
        "s0": 100,
        "barrier_out": 103,
        "barrier_in": 80,
        "coupon_out": 0.113,
        "maturity": "1y",
        "lock_term": "3m",
    }
    env = MarketEnv.from_spec(market)
    product = StandardSnowball.from_params(params, "CSI1000", valuation_date=env.valuation_date)
    return env, product


def test_snowball_quad_price(snowball_env_product):
    env, product = snowball_env_product
    quad = QuadSnowballEngine(n_points=901)
    pv = quad.calc_present_value(product, env)
    assert 85.0 < pv < 105.0


def test_snowball_quad_mc_cross_check(snowball_env_product):
    env, product = snowball_env_product
    set_seed(42)
    mc = McSnowballEngine(n_paths=80_000, seed=42)
    quad = QuadSnowballEngine(n_points=901)
    pv_mc = mc.calc_present_value(product, env)
    pv_quad = quad.calc_present_value(product, env)
    tol = tolerance_for("snowball.standard", "quad", pv_mc)
    assert abs(pv_quad - pv_mc) <= tol


def test_snowball_quad_fdm_cross_check(snowball_env_product):
    env, product = snowball_env_product
    fdm = FdmSnowballEngine(s_step=250)
    quad = QuadSnowballEngine(n_points=901)
    pv_fdm = fdm.calc_present_value(product, env)
    pv_quad = quad.calc_present_value(product, env)
    tol = tolerance_for("snowball.standard", "quad", pv_fdm)
    assert abs(pv_quad - pv_fdm) <= tol


def test_fcn_mc_quad_cross_check():
    market = {
        "valuation_date": "2024-01-05",
        "underlyings": [{"id": "CSI1000", "asset_class": "index", "spot": 100.0}],
        "rates": [{"id": "CN_RF", "kind": "constant", "value": 0.05}],
        "vols": [{"id": "CSI1000", "kind": "constant", "value": 0.2, "underlying_id": "CSI1000"}],
    }
    params = {
        "s0": 100,
        "barrier_out": 103,
        "barrier_in": 80,
        "coupon": 0.02,
        "maturity": "1y",
        "lock_term": "1m",
    }
    env = MarketEnv.from_spec(market)
    product = FCN.from_params(params, "CSI1000", valuation_date=env.valuation_date)
    set_seed(7)
    mc = McPhoenixEngine(n_paths=80_000, seed=7)
    quad = QuadFcnEngine(n_points=901)
    pv_mc = mc.calc_present_value(product, env)
    pv_quad = quad.calc_present_value(product, env)
    tol = tolerance_for("fcn", "quad", pv_mc)
    assert abs(pv_quad - pv_mc) <= tol


def test_phoenix_mc_price():
    market = {
        "valuation_date": "2024-01-05",
        "underlyings": [{"id": "CSI1000", "asset_class": "index", "spot": 100.0}],
        "rates": [{"id": "CN_RF", "kind": "constant", "value": 0.05}],
        "vols": [{"id": "CSI1000", "kind": "constant", "value": 0.2, "underlying_id": "CSI1000"}],
    }
    params = {
        "s0": 100,
        "barrier_out": 103,
        "barrier_in": 80,
        "coupon": 0.02,
        "maturity": "1y",
        "lock_term": "1m",
    }
    env = MarketEnv.from_spec(market)
    product = Phoenix.from_params(params, "CSI1000", valuation_date=env.valuation_date)
    set_seed(11)
    mc = McPhoenixEngine(n_paths=60_000, seed=11)
    pv = mc.calc_present_value(product, env)
    assert 90.0 < pv < 115.0


def test_oracle_tolerance_matrix_by_product():
    assert default_tolerances("snowball.standard")["quad"] == 0.02
    assert default_tolerances("fcn")["mc"] == 0.15
    assert "quad" not in default_tolerances("phoenix")


def test_snowball_dsl_quad(snowball_env_product):
    spec_dict = {
        "task": "price",
        "market": {
            "valuation_date": "2024-01-05",
            "underlyings": [{"id": "CSI1000", "asset_class": "index", "spot": 100.0}],
            "rates": [{"id": "CN_RF", "kind": "constant", "value": 0.05}],
            "vols": [{"id": "CSI1000", "kind": "constant", "value": 0.2, "underlying_id": "CSI1000"}],
        },
        "product": {
            "type": "snowball.standard",
            "params": {
                "s0": 100,
                "barrier_out": 103,
                "barrier_in": 80,
                "coupon_out": 0.113,
                "maturity": "1y",
            },
        },
        "engine": {"method": "quad", "params": {"n_points": 701}},
        "output": {"deterministic": True, "seed": 0},
    }
    from derivkit.engine_orchestrator import run_pricing

    result = run_pricing(PricingSpec.model_validate(spec_dict))
    assert result.meta["engine"] == "quad"
    assert 85.0 < result.pv < 105.0
