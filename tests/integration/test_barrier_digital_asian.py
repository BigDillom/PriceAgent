"""Integration tests for barrier, digital, and Asian products (W3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from derivkit.core.enums import (
    AsianAveSubstitution,
    AverageMethod,
    BarrierType,
    CallPut,
    EngineMethod,
    ExerciseType,
)
from derivkit.core.rng import set_seed
from derivkit.data.market_env import MarketEnv, UnderlyingSpec
from derivkit.core.enums import AssetClass
from derivkit.data.term_structures import ConstantRate
from derivkit.data.volmodels import ConstantVol
from derivkit.dsl.schema import PricingSpec
from derivkit.engine_orchestrator import build_product, run_pricing
from derivkit.pricing.engines.analytic_asian import AnalyticAsianEngine
from derivkit.pricing.engines.analytic_barrier import AnalyticBarrierEngine
from derivkit.pricing.engines.analytic_digital import AnalyticDigitalEngine
from derivkit.pricing.engines.mc_asian import McAsianEngine
from derivkit.pricing.engines.mc_barrier import McBarrierEngine
from derivkit.pricing.engines.mc_digital import McDigitalEngine
from derivkit.pricing.products.asian import AsianOption
from derivkit.pricing.products.barrier import BarrierOption
from derivkit.pricing.products.digital import DigitalOption
from datetime import date

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "src" / "derivkit" / "verify" / "golden"


@pytest.fixture
def env():
    return MarketEnv(
        valuation_date=date(2024, 1, 5),
        underlyings={"SPX": UnderlyingSpec("SPX", AssetClass.INDEX, 100.0)},
        rates=ConstantRate(0.05),
        vols={"SPX": ConstantVol(0.2)},
    )


@pytest.fixture
def mc_seed():
    set_seed(42)
    return 42


class TestBarrier:
    def test_analytic_up_and_out_call(self, env):
        opt = BarrierOption(
            strike=100,
            barrier=120,
            rebate=1.0,
            call_put=CallPut.CALL,
            barrier_type=BarrierType.UP_AND_OUT,
            maturity=1.0,
            underlying_id="SPX",
        )
        pv = AnalyticBarrierEngine().calc_present_value(opt, env)
        assert 1.0 < pv < 3.0

    def test_analytic_vs_mc(self, env, mc_seed):
        opt = BarrierOption(
            strike=100,
            barrier=80,
            rebate=1.0,
            call_put=CallPut.CALL,
            barrier_type=BarrierType.DOWN_AND_IN,
            maturity=1.0,
            underlying_id="SPX",
        )
        analytic = AnalyticBarrierEngine().calc_present_value(opt, env)
        mc = McBarrierEngine(n_paths=80_000, seed=mc_seed).calc_present_value(opt, env)
        assert abs(mc - analytic) <= 0.5 + abs(analytic) * 0.05

    def test_golden_barrier_uoc(self, env):
        golden_path = GOLDEN_DIR / "barrier_uoc_atm.json"
        data = json.loads(golden_path.read_text())
        opt = BarrierOption.from_params(data["params"], "SPX")
        pv = AnalyticBarrierEngine().calc_present_value(opt, env)
        assert abs(pv - data["pv"]) <= data["tolerance"]


class TestDigital:
    def test_analytic_european_call(self, env):
        opt = DigitalOption(
            strike=100,
            rebate=10.0,
            call_put=CallPut.CALL,
            exercise=ExerciseType.EUROPEAN,
            maturity=1.0,
            underlying_id="SPX",
        )
        pv = AnalyticDigitalEngine().calc_present_value(opt, env)
        assert 4.0 < pv < 6.0

    def test_analytic_vs_mc(self, env, mc_seed):
        opt = DigitalOption(
            strike=100,
            rebate=10.0,
            call_put=CallPut.CALL,
            exercise=ExerciseType.EUROPEAN,
            maturity=1.0,
            underlying_id="SPX",
        )
        analytic = AnalyticDigitalEngine().calc_present_value(opt, env)
        mc = McDigitalEngine(n_paths=80_000, seed=mc_seed).calc_present_value(opt, env)
        assert abs(mc - analytic) <= 0.3 + abs(analytic) * 0.05

    def test_golden_digital_call(self, env):
        golden_path = GOLDEN_DIR / "digital_call_atm.json"
        data = json.loads(golden_path.read_text())
        opt = DigitalOption.from_params(data["params"], "SPX")
        pv = AnalyticDigitalEngine().calc_present_value(opt, env)
        assert abs(pv - data["pv"]) <= data["tolerance"]


class TestAsian:
    def test_analytic_geometric_call(self, env):
        opt = AsianOption(
            strike=100,
            call_put=CallPut.CALL,
            ave_method=AverageMethod.GEOMETRIC,
            substitute=AsianAveSubstitution.UNDERLYING,
            maturity=1.0,
            underlying_id="SPX",
        )
        pv = AnalyticAsianEngine().calc_present_value(opt, env)
        assert 5.0 < pv < 8.0

    def test_analytic_vs_mc_geometric(self, env, mc_seed):
        opt = AsianOption(
            strike=100,
            call_put=CallPut.CALL,
            ave_method=AverageMethod.GEOMETRIC,
            maturity=1.0,
            underlying_id="SPX",
        )
        analytic = AnalyticAsianEngine().calc_present_value(opt, env)
        mc = McAsianEngine(n_paths=80_000, seed=mc_seed).calc_present_value(opt, env)
        assert abs(mc - analytic) <= 0.4 + abs(analytic) * 0.05

    def test_golden_asian_geometric(self, env):
        golden_path = GOLDEN_DIR / "asian_geometric_atm.json"
        data = json.loads(golden_path.read_text())
        opt = AsianOption.from_params(data["params"], "SPX")
        pv = AnalyticAsianEngine().calc_present_value(opt, env)
        assert abs(pv - data["pv"]) <= data["tolerance"]


@pytest.mark.integration
@pytest.mark.parametrize(
    "yaml_name,product_type",
    [
        ("barrier_up_and_out.yaml", "barrier.up_and_out"),
        ("digital_european.yaml", "digital.cash"),
        ("asian_geometric.yaml", "asian.geometric"),
    ],
)
def test_dsl_examples(yaml_name, product_type):
    from derivkit.dsl.loader import load_spec

    path = Path(__file__).resolve().parents[2] / "src" / "derivkit" / "dsl" / "examples" / yaml_name
    spec = load_spec(path)
    assert spec.product.type == product_type
    result = run_pricing(spec)
    assert result.pv > 0


@pytest.mark.integration
def test_build_product_routing(env):
    specs = [
        PricingSpec.model_validate(
            {
                "market": {
                    "valuation_date": "2024-01-05",
                    "underlyings": [{"id": "SPX", "spot": 100.0}],
                },
                "product": {
                    "type": "barrier.up_and_out",
                    "params": {
                        "strike": 100,
                        "barrier": 120,
                        "rebate": 1.0,
                        "maturity": "1y",
                        "barrier_type": "up_and_out",
                    },
                },
            }
        ),
        PricingSpec.model_validate(
            {
                "market": {
                    "valuation_date": "2024-01-05",
                    "underlyings": [{"id": "SPX", "spot": 100.0}],
                },
                "product": {
                    "type": "digital.cash",
                    "params": {"strike": 100, "rebate": 10.0, "maturity": "1y"},
                },
            }
        ),
        PricingSpec.model_validate(
            {
                "market": {
                    "valuation_date": "2024-01-05",
                    "underlyings": [{"id": "SPX", "spot": 100.0}],
                },
                "product": {
                    "type": "asian.geometric",
                    "params": {"strike": 100, "maturity": "1y", "ave_method": "geometric"},
                },
            }
        ),
    ]
    types = (BarrierOption, DigitalOption, AsianOption)
    for spec, expected in zip(specs, types, strict=True):
        product = build_product(spec, env)
        assert isinstance(product, expected)
