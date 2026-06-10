"""W9 release-prep tests: coverage for core modules and API contract."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import derivkit as dk
from derivkit.api.errors import DerivKitError, DslValidationError, PricingError
from derivkit.contract.output_contract import OutputContract, PricingResult, validate_result
from derivkit.core.conventions import discount_factor, parse_tenor, year_fraction
from derivkit.core.enums import (
    AlignPolicy,
    AsianAveSubstitution,
    AssetClass,
    AverageMethod,
    BarrierType,
    BusinessConvention,
    CallPut,
    Compounding,
    DayCount,
    EngineMethod,
    ExerciseType,
    InOut,
    PaymentType,
    ProcessType,
    RandsMethod,
    UpDown,
)
from derivkit.core.rng import get_generator, get_seed, normal_random, set_seed
from derivkit.data.adapters import commodity, equity
from derivkit.data.calendars import Calendar
from derivkit.data.market_env import MarketEnv, UnderlyingSpec
from derivkit.data.term_structures import ConstantRate, RateCurve
from derivkit.data.volmodels import ConstantVol, LocalVolSurface
from derivkit.dsl.schema import PricingSpec
from derivkit.engine_orchestrator import build_product, run_pricing, run_risk
from derivkit.pricing.engines import create_engine, validate_compatibility
from derivkit.pricing.engines.analytic import AnalyticEngine
from derivkit.pricing.engines.analytic_asian import AnalyticAsianEngine
from derivkit.pricing.engines.analytic_barrier import AnalyticBarrierEngine
from derivkit.pricing.engines.analytic_digital import AnalyticDigitalEngine
from derivkit.pricing.engines.mc_barrier import McBarrierEngine
from derivkit.pricing.formulas.bsm import bs_call_put, bs_delta, bs_gamma, bs_rho, bs_theta, bs_vega
from derivkit.pricing.greeks import calc_greeks
from derivkit.pricing.perf.numerical import tdma_jit
from derivkit.pricing.processes.bsm import BSMProcess
from derivkit.pricing.products.asian import AsianOption
from derivkit.pricing.products.barrier import BarrierOption, barrier_components
from derivkit.pricing.products.digital import DigitalOption
from derivkit.pricing.products.vanilla import EuropeanVanilla


@pytest.fixture
def env():
    return MarketEnv(
        valuation_date=date(2024, 1, 5),
        underlyings={"SPX": UnderlyingSpec("SPX", AssetClass.INDEX, 100.0, div_yield=0.02)},
        rates=ConstantRate(0.05),
        vols={"SPX": ConstantVol(0.2)},
    )


class TestAdapters:
    def test_equity_normalize(self):
        df = pd.DataFrame(
            {
                "datetime": pd.to_datetime(["2024-01-02", "2024-01-03"]),
                "close": [100.0, 101.0],
            }
        )
        out = equity.normalize(df, "AAPL")
        assert out["instrument_id"].iloc[0] == "AAPL"
        assert out["asset_class"].iloc[0] == AssetClass.EQUITY.value

    def test_commodity_normalize(self):
        df = pd.DataFrame({"datetime": pd.to_datetime(["2024-06-14"]), "close": [50.0]})
        out = commodity.normalize(df, "LH2409")
        assert out["asset_class"].iloc[0] == AssetClass.COMMODITY.value


class TestBSMProcess:
    def test_evolve_and_pde_coef(self, env):
        proc = BSMProcess(env, "SPX")
        assert proc.drift(0.5) == pytest.approx(0.03)
        assert proc.diffusion(0.5, 100.0) == pytest.approx(20.0)
        a, b, c = proc.pde_coef(0.5, 100.0)
        assert a > 0 and c < 0
        x = np.array([100.0, 101.0])
        dw = np.array([0.1, -0.1])
        out = proc.evolve(0.0, x, 1 / 252, dw)
        assert out.shape == x.shape
        assert np.all(out > 0)


class TestNumerical:
    def test_tdma_jit_solves_system(self):
        n = 15
        a = np.full(n - 1, -0.1)
        b = np.full(n, 2.0)
        c = np.full(n - 1, -0.1)
        rhs = np.ones(n)
        sol = tdma_jit(a, b, c, rhs)
        assert sol.shape == (n,)
        assert np.all(np.isfinite(sol))


class TestCoreExtended:
    def test_conventions_all_compounding(self):
        assert discount_factor(0.05, 1.0, Compounding.SIMPLE) < 1.0
        assert discount_factor(0.05, 1.0, Compounding.ANNUAL) < 1.0
        with pytest.raises(ValueError, match="Invalid tenor"):
            parse_tenor("bad")
        with pytest.raises(ValueError, match="Unknown compounding"):
            discount_factor(0.05, 1.0, "invalid")  # type: ignore[arg-type]

    def test_year_fraction_act360(self):
        yf = year_fraction("2024-01-01", "2024-07-01", DayCount.ACT360)
        assert yf == pytest.approx(181 / 360, rel=0.01)
        assert parse_tenor("30d") == pytest.approx(30 / 365)
        assert parse_tenor("2w") == pytest.approx(2 / 52)

    def test_rng_sobol_halton(self):
        set_seed(99)
        sobol = normal_random(50, method=RandsMethod.SOBOL)
        halton = normal_random(50, method=RandsMethod.HALTON)
        assert sobol.shape == (50,)
        assert halton.shape == (50,)
        gen = get_generator(7, RandsMethod.PSEUDO)
        assert gen.normal(0, 1, 10).shape == (10,)

    def test_get_seed_default(self):
        import derivkit.core.rng as rng_mod

        rng_mod._global_seed = None
        assert get_seed() == 0
        set_seed(0)
        assert get_seed() == 0

    def test_product_price_requires_engine(self, env):
        opt = EuropeanVanilla(strike=100, maturity=1.0, call_put=CallPut.CALL, underlying_id="SPX")
        with pytest.raises(ValueError, match="required"):
            opt.price()
        with pytest.raises(ValueError, match="required"):
            opt.price(AnalyticEngine(), None)

    def test_finite_diff_greeks_via_tree_engine(self, env):
        from derivkit.pricing.engines.tree import TreeEngine

        opt = EuropeanVanilla(strike=100, maturity=0.5, call_put=CallPut.CALL, underlying_id="SPX")
        g = TreeEngine(n_steps=50).calc_greeks(opt, env, ["delta", "gamma", "vega", "theta", "rho"])
        assert all(k in g for k in ("delta", "gamma", "vega", "theta", "rho"))

    def test_calc_greeks_wrapper(self, env):
        opt = EuropeanVanilla(strike=100, maturity=1.0, call_put=CallPut.CALL, underlying_id="SPX")
        g = calc_greeks(AnalyticEngine(), opt, env, ["delta"])
        assert "delta" in g


class TestDataModules:
    def test_constant_rate_notify(self):
        from derivkit.core.observable import Observer

        updates = []

        class Obs(Observer):
            def update(self, *_args, **_kwargs):
                updates.append(1)

        rate = ConstantRate(0.05)
        obs = Obs()
        rate.attach(obs)
        rate.detach(obs)
        rate.attach(obs)
        rate.rate = 0.06
        assert updates == [1]
        assert rate(0.5) == 0.06
        assert rate.disc_factor(1.0) < 1.0
        assert rate.disc_factor(1.0, 1.0) == 1.0

    def test_rate_curve(self):
        curve = RateCurve([0.5, 1.0, 2.0], [0.04, 0.05, 0.06])
        assert curve(0.75) == pytest.approx(0.045)
        assert curve.disc_factor(1.0) < 1.0
        bumped = curve.bump(0.01)
        assert bumped(1.0) == pytest.approx(0.06)
        with pytest.raises(ValueError, match="same length"):
            RateCurve([1.0], [0.05, 0.06])
        with pytest.raises(ValueError, match="increasing"):
            RateCurve([2.0, 1.0], [0.05, 0.06])

    def test_vol_models(self):
        vol = ConstantVol(0.25)
        assert vol(0.5, 100.0) == 0.25
        vol.sigma = 0.3
        assert vol.bump(0.01).sigma == pytest.approx(0.31)
        surface = LocalVolSurface(
            np.array([0.25, 0.5, 1.0]),
            np.array([90.0, 100.0, 110.0]),
            np.array([[0.2, 0.21, 0.22], [0.19, 0.2, 0.21], [0.18, 0.19, 0.2]]),
        )
        assert 0.15 < surface(0.5, 100.0) < 0.25

    def test_calendar(self):
        cal = Calendar(holidays={date(2024, 1, 1)})
        assert cal.is_statutory_holiday(date(2024, 1, 1))
        assert cal.is_holiday(date(2024, 1, 6))  # Saturday
        cal.remove_holiday(date(2024, 1, 1))
        assert not cal.is_statutory_holiday(date(2024, 1, 1))
        fri = date(2024, 1, 5)
        assert cal.advance(fri, timedelta(days=0)) == fri
        assert cal.advance(fri, timedelta(days=1)) == date(2024, 1, 8)
        assert cal.advance_business_days(fri, 0) == fri
        assert cal.business_days_between(date(2024, 1, 2), date(2024, 1, 10)) >= 0
        assert cal.business_days_between(date(2024, 1, 10), date(2024, 1, 2)) < 0
        hol = date(2024, 1, 8)
        cal2 = Calendar(holidays={hol})
        assert cal2.advance_business_days(hol, 0, BusinessConvention.FOLLOWING) > hol

    def test_market_env_bumps_and_errors(self, env):
        assert env.spot("SPX") == 100.0
        bumped = env.bump_spot("SPX", 1.0)
        assert bumped.spot("SPX") == 101.0
        assert env.bump_vol("SPX", 0.01).vol("SPX") == pytest.approx(0.21)
        assert env.bump_rate(0.001).rate() == pytest.approx(0.051)
        assert env.bump_time(-1 / 365).valuation_date < env.valuation_date
        with pytest.raises(KeyError):
            env.spot("UNKNOWN")

    def test_market_env_from_spec_spot_csv_dict(self):
        csv_path = (
            Path(__file__).resolve().parents[2] / "examples" / "commodity" / "data" / "lh2409.csv"
        )
        spec = {
            "valuation_date": "2024-06-14",
            "calendar": "CN",
            "underlyings": [
                {
                    "id": "LH2409",
                    "asset_class": "commodity",
                    "spot": {
                        "source": "csv",
                        "path": str(csv_path),
                        "field": "close",
                        "session_close": "23:00",
                        "tz": "Asia/Shanghai",
                    },
                }
            ],
        }
        env = MarketEnv.from_spec(spec)
        assert env.spot("LH2409") == 15520.0
        assert env.alignment is not None
        assert len(env.alignment.records) == 1

    def test_market_env_unknown_spot_source(self):
        spec = {
            "valuation_date": "2024-06-14",
            "underlyings": [
                {
                    "id": "LH2409",
                    "spot": {"source": "tushare", "symbol": "LH2409"},
                }
            ],
        }
        with pytest.raises(ValueError, match="Unknown spot source"):
            MarketEnv.from_spec(spec)

    def test_market_env_from_spec_rate_curve_csv(self, tmp_path):
        csv_path = tmp_path / "curve.csv"
        csv_path.write_text("tenor,rate\n0.5,0.04\n1.0,0.05\n")
        spec = {
            "valuation_date": "2024-01-05",
            "underlyings": [{"id": "SPX", "spot": 100.0}],
            "rates": [
                {
                    "id": "USD",
                    "kind": "curve",
                    "data": {"source": "csv", "path": str(csv_path)},
                }
            ],
        }
        env = MarketEnv.from_spec(spec)
        assert env.rate(0.75) == pytest.approx(0.045)


class TestBarrierDigitalAsianExtended:
    def test_barrier_components_and_from_params(self):
        assert barrier_components(BarrierType.UP_AND_OUT) == (UpDown.UP, InOut.OUT)
        opt = BarrierOption.from_params(
            {"updown": "down", "inout": "in", "strike": 100, "barrier": 80},
            "SPX",
        )
        assert opt.barrier_type == BarrierType.DOWN_AND_IN
        payoff = opt.payoff(np.array([70.0, 90.0]))
        assert payoff.shape == (2,)

    def test_barrier_all_types_analytic(self, env):
        configs = [
            (BarrierType.UP_AND_IN, 120, CallPut.CALL),
            (BarrierType.UP_AND_OUT, 120, CallPut.PUT),
            (BarrierType.DOWN_AND_IN, 80, CallPut.PUT),
            (BarrierType.DOWN_AND_OUT, 80, CallPut.CALL),
        ]
        engine = AnalyticBarrierEngine()
        for btype, barrier, cp in configs:
            opt = BarrierOption(
                strike=100,
                barrier=barrier,
                rebate=1.0,
                call_put=cp,
                barrier_type=btype,
                maturity=1.0,
                underlying_id="SPX",
            )
            pv = engine.calc_present_value(opt, env)
            assert pv >= 0.0

    def test_barrier_touched_and_expired(self, env):
        opt = BarrierOption(
            strike=100,
            barrier=95,
            rebate=2.0,
            call_put=CallPut.CALL,
            barrier_type=BarrierType.DOWN_AND_OUT,
            maturity=0.0,
            underlying_id="SPX",
        )
        assert AnalyticBarrierEngine().calc_present_value(opt, env) >= 0.0
        opt2 = BarrierOption(
            strike=100,
            barrier=90,
            rebate=2.0,
            call_put=CallPut.CALL,
            barrier_type=BarrierType.DOWN_AND_OUT,
            maturity=1.0,
            underlying_id="SPX",
            discrete_obs_interval=1 / 252,
        )
        assert AnalyticBarrierEngine(for_haug=True).calc_present_value(opt2, env) >= 0.0

    def test_digital_american_paths(self, env):
        opt = DigitalOption(
            strike=100,
            rebate=10.0,
            call_put=CallPut.CALL,
            exercise=ExerciseType.AMERICAN,
            payment_type=PaymentType.HIT,
            maturity=1.0,
            underlying_id="SPX",
        )
        assert AnalyticDigitalEngine().calc_present_value(opt, env) > 0
        opt2 = DigitalOption(
            strike=100,
            rebate=10.0,
            call_put=CallPut.PUT,
            exercise=ExerciseType.AMERICAN,
            payment_type=PaymentType.EXPIRE,
            maturity=1.0,
            underlying_id="SPX",
            discrete_obs_interval=1 / 252,
        )
        assert AnalyticDigitalEngine().calc_present_value(opt2, env) >= 0.0
        opt3 = DigitalOption.from_params(
            {"strike": 100, "rebate": 5.0, "exercise": "american", "maturity": "1y"},
            "SPX",
        )
        assert opt3.payment_type == PaymentType.HIT
        assert DigitalOption.from_params({"strike": 100}, "SPX").payoff(110.0) == 1.0

    def test_asian_arithmetic_and_errors(self, env):
        opt = AsianOption(
            strike=100,
            call_put=CallPut.CALL,
            ave_method=AverageMethod.ARITHMETIC,
            maturity=1.0,
            underlying_id="SPX",
            obs_start_frac=0.25,
        )
        pv = AnalyticAsianEngine().calc_present_value(opt, env)
        assert pv > 0
        with pytest.raises(ValueError, match="enhanced"):
            AsianOption(strike=100, call_put=CallPut.CALL, enhanced=True)
        with pytest.raises(ValueError, match="enhanced"):
            AnalyticAsianEngine().calc_present_value(
                AsianOption(
                    strike=100,
                    call_put=CallPut.CALL,
                    enhanced=True,
                    limited_price=90.0,
                    maturity=1.0,
                    underlying_id="SPX",
                ),
                env,
            )


class TestApiContract:
    def test_pricing_result_and_validate(self):
        result = PricingResult(pv=10.0, greeks={"delta": 0.5}, meta={"engine": "analytic"})
        d = result.to_dict()
        assert d["pv"] == 10.0
        assert result.get("pv") == 10.0
        assert result.get("delta") == 0.5
        assert result.get("missing", 0) == 0
        contract = OutputContract(tolerance={"pv": 0.5})
        assert validate_result(result, 10.2, contract)
        assert not validate_result(result, 12.0, contract)
        assert validate_result(result, None, contract)

    def test_api_risk_and_calibrate(self, vanilla_spec_dict):
        risk_result = dk.risk(vanilla_spec_dict)
        assert "delta" in risk_result.greeks or risk_result.pv > 0
        cal_spec = {
            "task": "calibrate",
            "market": vanilla_spec_dict["market"],
            "product": vanilla_spec_dict["product"],
            "calibration": {
                "method": "implied",
                "market_price": 10.5,
                "underlying_id": "SPX",
            },
        }
        cal_result = dk.calibrate(cal_spec)
        assert cal_result.pv > 0
        assert cal_result.meta["calibration_method"] == "implied"

    def test_price_risk_task_redirect(self, vanilla_spec_dict):
        spec = dict(vanilla_spec_dict)
        spec["task"] = "risk"
        result = dk.price(spec)
        assert result.pv > 0

    def test_errors(self):
        err = DslValidationError([{"field": "market", "message": "required"}])
        assert "market" in str(err)
        pe = PricingError("failed", {"code": 1})
        assert pe.details["code"] == 1
        assert issubclass(PricingError, DerivKitError)

    def test_bsm_formulas(self):
        pv = bs_call_put(100, 100, 1.0, 0.05, 0.2, 1)
        assert pv > 0
        assert bs_delta(100, 100, 1.0, 0.05, 0.2, 1) > 0
        assert bs_gamma(100, 100, 1.0, 0.05, 0.2) > 0
        assert bs_vega(100, 100, 1.0, 0.05, 0.2) > 0
        assert bs_theta(100, 100, 1.0, 0.05, 0.2, 1) < 0
        assert bs_rho(100, 100, 1.0, 0.05, 0.2, 1) > 0


class TestOrchestrator:
    def test_engine_registry(self):
        with pytest.raises(ValueError):
            validate_compatibility(ProcessType.BSM, ExerciseType.EUROPEAN, EngineMethod("bad"))  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="not compatible"):
            validate_compatibility(ProcessType.BSM, ExerciseType.AMERICAN, EngineMethod.ANALYTIC)
        eng = create_engine("analytic")
        assert isinstance(eng, AnalyticEngine)

    def test_unsupported_product_raises(self, env):
        spec = PricingSpec.model_validate(
            {
                "market": {
                    "valuation_date": "2024-01-05",
                    "underlyings": [{"id": "SPX", "spot": 100}],
                },
                "product": {"type": "unknown.product", "params": {}},
            }
        )
        with pytest.raises(ValueError, match="Unsupported"):
            build_product(spec, env)

    def test_barrier_unsupported_engine(self, env):
        spec = PricingSpec.model_validate(
            {
                "market": {
                    "valuation_date": "2024-01-05",
                    "underlyings": [{"id": "SPX", "spot": 100}],
                },
                "product": {
                    "type": "barrier.up_and_out",
                    "params": {"strike": 100, "barrier": 120, "maturity": "1y"},
                },
                "engine": {"method": "tree"},
            }
        )
        product = build_product(spec, env)
        with pytest.raises(ValueError, match="does not support"):
            from derivkit.engine_orchestrator import _create_engine_for_product

            _create_engine_for_product(spec, product, {})

    def test_run_pricing_with_greeks(self, vanilla_spec_dict):
        spec_dict = dict(vanilla_spec_dict)
        spec_dict["output"] = {
            "fields": ["pv", "delta"],
            "deterministic": True,
            "seed": 42,
        }
        spec = PricingSpec.model_validate(spec_dict)
        result = run_pricing(spec)
        assert "delta" in result.greeks
        risk = run_risk(spec)
        assert risk.pv > 0

    def test_snowball_phoenix_fcn_routing(self):
        from derivkit.dsl.loader import load_spec

        yaml_path = (
            Path(__file__).resolve().parents[2] / "src/derivkit/dsl/examples/snowball_standard.yaml"
        )
        snowball = load_spec(yaml_path)
        snowball.engine.params = {"n_paths": 5000}
        snowball.output.seed = 1
        assert run_pricing(snowball).pv != 0.0


class TestAlignmentExtended:
    def test_exact_same_day_prev_policies(self):
        from derivkit.data.alignment import (
            AlignmentRecord,
            align_spot_to_valuation,
            parse_session_close,
        )

        idx = pd.date_range("2024-01-02 09:00", periods=3, freq="D")
        df = pd.DataFrame({"close": [10.0, 11.0, 12.0]}, index=idx)
        val_dt = idx[1]
        spot, rec = align_spot_to_valuation(df, val_dt.to_pydatetime(), instrument_id="X")
        assert spot == 11.0
        assert rec.rule == "exact_match"

        spot2, _ = align_spot_to_valuation(
            df, datetime(2024, 1, 3, 15, 0), align_policy=AlignPolicy.SAME_DAY, instrument_id="X"
        )
        assert spot2 == 11.0

        spot3, _ = align_spot_to_valuation(
            df,
            datetime(2024, 1, 5, 15, 0),
            align_policy=AlignPolicy.PREV_BUSINESS_DAY,
            instrument_id="X",
        )
        assert spot3 == 12.0

        assert parse_session_close("09:30").minute == 30
        rec2 = AlignmentRecord("A", "test", 1, 2, AlignPolicy.NEAREST_AVAILABLE, delta_days=0)
        assert rec2.to_dict()["policy"] == AlignPolicy.NEAREST_AVAILABLE.value

    def test_align_spots_batch_literal_and_csv(self, tmp_path):
        from derivkit.data.alignment import align_spots_batch

        csv_path = tmp_path / "px.csv"
        csv_path.write_text("datetime,close\n2024-01-02,50.0\n2024-01-03,51.0\n")
        specs = [
            {"id": "LIT", "spot": 99.0},
            {
                "id": "CSV",
                "spot": {
                    "source": "csv",
                    "path": str(csv_path),
                    "align_policy": "nearest_available",
                },
            },
        ]
        result = align_spots_batch(specs, datetime(2024, 1, 3, 16, 0))
        assert result.aligned_spots["LIT"] == 99.0
        assert "CSV" in result.aligned_spots

    def test_alignment_errors(self):
        from derivkit.data.alignment import align_spot_to_valuation

        with pytest.raises(ValueError, match="No data"):
            align_spot_to_valuation(pd.DataFrame(), datetime(2024, 1, 1), instrument_id="E")
        df = pd.DataFrame({"close": [1.0]}, index=pd.DatetimeIndex(["2024-01-02"]))
        with pytest.raises(ValueError, match="same-day"):
            align_spot_to_valuation(
                df, datetime(2024, 1, 10), align_policy=AlignPolicy.SAME_DAY, instrument_id="E"
            )


class TestMcEnginesSmoke:
    def test_mc_barrier_digital_asian(self, env):
        set_seed(11)
        barrier = BarrierOption(
            strike=100,
            barrier=120,
            rebate=1.0,
            call_put=CallPut.CALL,
            barrier_type=BarrierType.UP_AND_OUT,
            maturity=0.5,
            underlying_id="SPX",
        )
        assert McBarrierEngine(n_paths=5000, seed=11).calc_present_value(barrier, env) > 0
        digital = DigitalOption(
            strike=100,
            rebate=5.0,
            call_put=CallPut.PUT,
            exercise=ExerciseType.EUROPEAN,
            maturity=0.5,
            underlying_id="SPX",
        )
        from derivkit.pricing.engines.mc_asian import McAsianEngine
        from derivkit.pricing.engines.mc_digital import McDigitalEngine

        assert McDigitalEngine(n_paths=5000, seed=11).calc_present_value(digital, env) > 0
        asian = AsianOption(
            strike=100,
            call_put=CallPut.CALL,
            ave_method=AverageMethod.ARITHMETIC,
            maturity=0.5,
            underlying_id="SPX",
        )
        assert McAsianEngine(n_paths=5000, seed=11).calc_present_value(asian, env) > 0


class TestDigitalExtended:
    def test_european_expired_and_american_hit(self, env):
        expired_itm = DigitalOption(
            strike=90,
            rebate=8.0,
            call_put=CallPut.CALL,
            maturity=0.0,
            underlying_id="SPX",
        )
        assert AnalyticDigitalEngine().calc_present_value(expired_itm, env) == 8.0
        expired_otm = DigitalOption(
            strike=110,
            rebate=8.0,
            call_put=CallPut.CALL,
            maturity=0.0,
            underlying_id="SPX",
        )
        assert AnalyticDigitalEngine().calc_present_value(expired_otm, env) == 0.0
        touched = DigitalOption(
            strike=95,
            rebate=6.0,
            call_put=CallPut.CALL,
            exercise=ExerciseType.AMERICAN,
            payment_type=PaymentType.HIT,
            maturity=1.0,
            underlying_id="SPX",
        )
        assert AnalyticDigitalEngine().calc_present_value(touched, env) == 6.0
        with pytest.raises(TypeError):
            AnalyticDigitalEngine().calc_present_value(
                EuropeanVanilla(strike=100, maturity=1.0, underlying_id="SPX"), env
            )


class TestValidatorsExtended:
    def test_validation_report_merge_and_errors(self):
        from derivkit.data.validators import (
            ValidationReport,
            validate_market_inputs,
            validate_rate_curve,
            validate_spot,
            validate_vol_surface,
        )

        r1 = ValidationReport()
        r1.add_warning("a", "warn")
        r2 = ValidationReport()
        r2.add_error("b", "err")
        r1.merge(r2)
        assert not r1.passed
        assert len(r1.to_dict()["issues"]) == 2

        empty = validate_rate_curve(np.array([]), np.array([]))
        assert not empty.passed
        bad_len = validate_rate_curve(np.array([1.0, 2.0]), np.array([0.05]))
        assert not bad_len.passed
        bad_tenor = validate_rate_curve(np.array([1.0, 0.5]), np.array([0.05, 0.06]))
        assert not bad_tenor.passed

        vol_err = validate_vol_surface(np.array([-0.1]))
        assert not vol_err.passed
        shape_err = validate_vol_surface(
            np.ones((2, 2)),
            spots=np.array([90.0, 100.0]),
            times=np.array([0.5, 1.0, 1.5]),
        )
        assert not shape_err.passed

        nan_spot = validate_spot(float("nan"))
        assert not nan_spot.passed
        market = validate_market_inputs(
            {"X": 100.0},
            {"X": 0.2},
            rate_tenors=np.array([1.0]),
            rate_values=np.array([0.05]),
        )
        assert market.passed


class TestAsianProduct:
    def test_strike_substitute_mc_only(self):
        opt = AsianOption(
            strike=100,
            call_put=CallPut.CALL,
            substitute=AsianAveSubstitution.STRIKE,
            maturity=1.0,
            underlying_id="SPX",
        )
        assert EngineMethod.ANALYTIC not in opt.supported_engines
        assert opt.payoff(105.0) == 5.0

    def test_enhanced_requires_limited_price(self):
        with pytest.raises(ValueError, match="limited_price"):
            AsianOption(
                strike=100,
                call_put=CallPut.CALL,
                enhanced=True,
                maturity=1.0,
                underlying_id="SPX",
            )


class TestOracleExtended:
    def test_oracle_requires_product(self):
        from derivkit.verify.oracle import cross_check

        spec = PricingSpec.model_validate(
            {
                "task": "price",
                "market": {
                    "valuation_date": "2024-01-05",
                    "underlyings": [{"id": "SPX", "spot": 100.0}],
                },
            }
        )
        with pytest.raises(ValueError, match="product section is required"):
            cross_check(spec)

    def test_oracle_helpers_and_cross_check(self):
        from derivkit.verify.oracle import (
            cross_check,
            default_tolerances,
            tolerance_for,
        )

        assert default_tolerances()["analytic"] == 0.0
        assert tolerance_for("vanilla.european", "tree", ref_pv=10.0) > 0
        spec = PricingSpec.model_validate(
            {
                "market": {
                    "valuation_date": "2024-01-05",
                    "underlyings": [{"id": "SPX", "spot": 100.0}],
                    "rates": [{"id": "RF", "kind": "constant", "value": 0.05}],
                    "vols": [
                        {
                            "id": "SPX",
                            "kind": "constant",
                            "value": 0.2,
                            "underlying_id": "SPX",
                        }
                    ],
                },
                "product": {
                    "type": "vanilla.european",
                    "params": {"strike": 100, "maturity": "1y", "call_put": "call"},
                },
                "engine": {"method": "analytic"},
                "output": {"seed": 42, "deterministic": True},
            }
        )
        report = cross_check(spec, methods=[EngineMethod.ANALYTIC, EngineMethod.TREE], seed=42)
        assert report["passed"]


class TestScheduleExtended:
    def test_schedule_weekly_freq(self):
        from derivkit.data.schedule import Schedule

        start = date(2024, 1, 2)
        end = date(2024, 3, 2)
        sched = Schedule(
            trade_calendar=Calendar(),
            start=start,
            end=end,
            freq="w",
            lock_term=0,
        )
        assert len(sched.date_schedule) >= 4


class TestVanillaProduct:
    def test_american_engines_and_price(self, env):
        from derivkit.core.enums import ExerciseType

        am = EuropeanVanilla(
            strike=100,
            maturity=1.0,
            call_put=CallPut.PUT,
            underlying_id="SPX",
            exercise=ExerciseType.AMERICAN,
        )
        assert EngineMethod.ANALYTIC not in am.supported_engines
        assert am.payoff(90.0) == 10.0
        assert am.price(AnalyticEngine(), env) > 0
