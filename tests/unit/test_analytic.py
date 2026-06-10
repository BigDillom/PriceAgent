"""Unit tests for analytic engine."""

from datetime import date

import pytest

from derivkit.core.enums import AssetClass, CallPut
from derivkit.data.market_env import MarketEnv, UnderlyingSpec
from derivkit.data.term_structures import ConstantRate
from derivkit.data.volmodels import ConstantVol
from derivkit.pricing.engines.analytic import AnalyticEngine
from derivkit.pricing.products.vanilla import EuropeanVanilla


@pytest.fixture
def env():
    return MarketEnv(
        valuation_date=date(2024, 1, 5),
        underlyings={"SPX": UnderlyingSpec("SPX", AssetClass.INDEX, 100.0)},
        rates=ConstantRate(0.05),
        vols={"SPX": ConstantVol(0.2)},
    )


class TestAnalyticEngine:
    def test_atm_call(self, env):
        opt = EuropeanVanilla(strike=100, maturity=1.0, call_put=CallPut.CALL, underlying_id="SPX")
        engine = AnalyticEngine()
        pv = engine.calc_present_value(opt, env)
        assert 10.0 < pv < 11.0

    def test_put_call_parity(self, env):
        call = EuropeanVanilla(strike=100, maturity=1.0, call_put=CallPut.CALL, underlying_id="SPX")
        put = EuropeanVanilla(strike=100, maturity=1.0, call_put=CallPut.PUT, underlying_id="SPX")
        engine = AnalyticEngine()
        c = engine.calc_present_value(call, env)
        p = engine.calc_present_value(put, env)
        # C - P = S*exp(-qT) - K*exp(-rT)
        parity = c - p - (100 * 1.0 - 100 * 0.9512)
        assert abs(parity) < 0.1

    def test_expired_option(self, env):
        opt = EuropeanVanilla(strike=100, maturity=0.0, call_put=CallPut.CALL, underlying_id="SPX")
        engine = AnalyticEngine()
        pv = engine.calc_present_value(opt, env)
        assert pv == 0.0
