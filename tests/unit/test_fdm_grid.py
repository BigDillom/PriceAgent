"""Unit tests for FdmGrid-based vanilla FDM engine."""

from datetime import date

import pytest

from derivkit.core.enums import AssetClass, CallPut
from derivkit.data.market_env import MarketEnv, UnderlyingSpec
from derivkit.data.term_structures import ConstantRate
from derivkit.data.volmodels import ConstantVol
from derivkit.pricing.engines.analytic import AnalyticEngine
from derivkit.pricing.engines.fdm import FdmEngine
from derivkit.pricing.products.vanilla import EuropeanVanilla


@pytest.fixture
def env():
    return MarketEnv(
        valuation_date=date(2024, 1, 5),
        underlyings={"SPX": UnderlyingSpec("SPX", AssetClass.INDEX, 100.0)},
        rates=ConstantRate(0.05),
        vols={"SPX": ConstantVol(0.2)},
    )


class TestFdmGridEngine:
    def test_european_call_vs_analytic(self, env):
        opt = EuropeanVanilla(strike=100, maturity=1.0, call_put=CallPut.CALL, underlying_id="SPX")
        analytic = AnalyticEngine().calc_present_value(opt, env)
        fdm = FdmEngine(n_s=400, n_smax=4.0).calc_present_value(opt, env)
        assert abs(fdm - analytic) < 0.05

    def test_european_put_vs_analytic(self, env):
        opt = EuropeanVanilla(strike=100, maturity=1.0, call_put=CallPut.PUT, underlying_id="SPX")
        analytic = AnalyticEngine().calc_present_value(opt, env)
        fdm = FdmEngine(n_s=400).calc_present_value(opt, env)
        assert abs(fdm - analytic) < 0.05

    def test_american_call_ge_european(self, env):
        from derivkit.core.enums import ExerciseType

        eu = EuropeanVanilla(
            strike=100,
            maturity=1.0,
            call_put=CallPut.CALL,
            underlying_id="SPX",
            exercise=ExerciseType.EUROPEAN,
        )
        am = EuropeanVanilla(
            strike=100,
            maturity=1.0,
            call_put=CallPut.CALL,
            underlying_id="SPX",
            exercise=ExerciseType.AMERICAN,
        )
        pv_eu = FdmEngine(n_s=300).calc_present_value(eu, env)
        pv_am = FdmEngine(n_s=300).calc_present_value(am, env)
        assert pv_am >= pv_eu - 0.01
