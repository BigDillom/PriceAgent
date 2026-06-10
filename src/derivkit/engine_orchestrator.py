"""L3 orchestration: DSL → MarketEnv → Product → Engine → Result."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from derivkit.contract.output_contract import PricingResult
from derivkit.core.enums import EngineMethod
from derivkit.core.rng import set_seed
from derivkit.data.calibration import historical_volatility, implied_volatility
from derivkit.data.market_env import MarketEnv
from derivkit.data.series_loader import load_series_for_calibration
from derivkit.dsl.schema import CalibrationSpec, PricingSpec
from derivkit.pricing.engines import create_engine
from derivkit.pricing.engines.analytic_asian import AnalyticAsianEngine
from derivkit.pricing.engines.analytic_barrier import AnalyticBarrierEngine
from derivkit.pricing.engines.analytic_digital import AnalyticDigitalEngine
from derivkit.pricing.engines.mc_asian import McAsianEngine
from derivkit.pricing.engines.mc_barrier import McBarrierEngine
from derivkit.pricing.engines.mc_digital import McDigitalEngine
from derivkit.pricing.engines.fdm_snowball import FdmSnowballEngine
from derivkit.pricing.engines.mc_phoenix import McPhoenixEngine
from derivkit.pricing.engines.mc_snowball import McSnowballEngine
from derivkit.pricing.engines.quad_fcn import QuadFcnEngine
from derivkit.pricing.engines.quad_snowball import QuadSnowballEngine
from derivkit.pricing.products.asian import AsianOption
from derivkit.pricing.products.barrier import BarrierOption
from derivkit.pricing.products.digital import DigitalOption
from derivkit.pricing.products.fcn import FCN
from derivkit.pricing.products.phoenix import Phoenix
from derivkit.pricing.products.snowball import StandardSnowball
from derivkit.pricing.products.vanilla import EuropeanVanilla

logger = logging.getLogger(__name__)

SNOWBALL_TYPES = frozenset({"snowball.standard", "snowball"})
PHOENIX_TYPES = frozenset({"phoenix", "phoenix.standard"})
FCN_TYPES = frozenset({"fcn", "fcn.standard"})
BARRIER_TYPES = frozenset(
    {"barrier", "barrier.single", "barrier.up_and_out", "barrier.down_and_in"}
)
DIGITAL_TYPES = frozenset({"digital", "digital.cash", "digital.cash_or_nothing"})
ASIAN_TYPES = frozenset({"asian", "asian.geometric", "asian.arithmetic"})

ProductType = (
    EuropeanVanilla | StandardSnowball | Phoenix | FCN | BarrierOption | DigitalOption | AsianOption
)


def build_product(spec: PricingSpec, env: MarketEnv | None = None) -> ProductType:
    """Construct product from DSL product section."""
    ptype = spec.product.type
    params = spec.product.params
    uid = spec.market.underlyings[0].id
    raw = params.model_dump(exclude_none=True)

    if ptype in ("vanilla.european", "vanilla"):
        return EuropeanVanilla(
            strike=params.strike or 100.0,
            maturity=params.maturity,
            call_put=params.call_put,
            underlying_id=uid,
            exercise=params.exercise,
        )
    if ptype in SNOWBALL_TYPES:
        val_date = env.valuation_date if env else None
        return StandardSnowball.from_params(raw, uid, valuation_date=val_date)
    if ptype in PHOENIX_TYPES:
        val_date = env.valuation_date if env else None
        return Phoenix.from_params(raw, uid, valuation_date=val_date)
    if ptype in FCN_TYPES:
        val_date = env.valuation_date if env else None
        return FCN.from_params(raw, uid, valuation_date=val_date)
    if ptype in BARRIER_TYPES:
        return BarrierOption.from_params(raw, uid)
    if ptype in DIGITAL_TYPES:
        return DigitalOption.from_params(raw, uid)
    if ptype in ASIAN_TYPES:
        return AsianOption.from_params(raw, uid)
    raise ValueError(f"Unsupported product type: {ptype}")


def _mc_params(engine_params: dict[str, Any], seed: int) -> dict[str, Any]:
    out = {"n_paths": engine_params.get("n_paths", 100_000), "seed": engine_params.get("seed", seed)}
    if "rands_method" in engine_params:
        out["rands_method"] = engine_params["rands_method"]
    return out


def _create_engine_for_product(
    spec: PricingSpec,
    product: ProductType,
    engine_params: dict[str, Any],
):
    method = spec.engine.method
    seed = spec.output.seed

    if isinstance(product, StandardSnowball):
        if method == EngineMethod.MC:
            return McSnowballEngine(**_mc_params(engine_params, seed))
        if method == EngineMethod.FDM:
            fdm_keys = {"s_step", "n_smax", "scheme", "t_step_per_year", "european_knock_in", "trigger"}
            return FdmSnowballEngine(**{k: v for k, v in engine_params.items() if k in fdm_keys})
        if method == EngineMethod.QUAD:
            quad_keys = {"quad_method", "n_points", "trigger"}
            return QuadSnowballEngine(**{k: v for k, v in engine_params.items() if k in quad_keys})
        raise ValueError(f"Snowball does not support engine method: {method}")

    if isinstance(product, (Phoenix, FCN)):
        if method == EngineMethod.MC:
            mc_keys = {"n_paths", "seed", "rands_method", "t_step_per_year"}
            return McPhoenixEngine(**{k: v for k, v in {**_mc_params(engine_params, seed), **engine_params}.items() if k in mc_keys})
        if method == EngineMethod.QUAD and isinstance(product, FCN):
            quad_keys = {"quad_method", "n_points"}
            return QuadFcnEngine(**{k: v for k, v in engine_params.items() if k in quad_keys})
        raise ValueError(f"{type(product).__name__} does not support engine method: {method}")

    if isinstance(product, BarrierOption):
        if method == EngineMethod.ANALYTIC:
            return AnalyticBarrierEngine(**{k: v for k, v in engine_params.items() if k == "for_haug"})
        if method == EngineMethod.MC:
            return McBarrierEngine(**_mc_params(engine_params, seed))
        raise ValueError(f"BarrierOption does not support engine method: {method}")

    if isinstance(product, DigitalOption):
        if method == EngineMethod.ANALYTIC:
            return AnalyticDigitalEngine()
        if method == EngineMethod.MC:
            return McDigitalEngine(**_mc_params(engine_params, seed))
        raise ValueError(f"DigitalOption does not support engine method: {method}")

    if isinstance(product, AsianOption):
        if method == EngineMethod.ANALYTIC:
            return AnalyticAsianEngine()
        if method == EngineMethod.MC:
            return McAsianEngine(**_mc_params(engine_params, seed))
        raise ValueError(f"AsianOption does not support engine method: {method}")

    return create_engine(method, **engine_params)


def run_pricing(spec: PricingSpec) -> PricingResult:
    """Execute full pricing pipeline from validated spec."""
    if spec.product is None:
        raise ValueError("task=price requires product section")
    if spec.output.deterministic:
        set_seed(spec.output.seed)

    env = MarketEnv.from_spec(spec.to_dict())
    product = build_product(spec, env)
    engine_params = dict(spec.engine.params)
    if spec.engine.method == EngineMethod.MC and isinstance(product, EuropeanVanilla):
        engine_params.setdefault("seed", spec.output.seed)
    engine = _create_engine_for_product(spec, product, engine_params)

    pv = engine.calc_present_value(product, env)

    greek_fields = [f for f in spec.output.fields if f != "pv"]
    greeks: dict[str, float] = {}
    if greek_fields:
        greeks = engine.calc_greeks(product, env, greek_fields)

    meta: dict[str, Any] = {
        "engine": spec.engine.method.value,
        "product": spec.product.type,
        "process": "bsm",
        "backend": "derivkit",
        "valuation_date": str(env.valuation_date),
    }
    if env.alignment:
        meta["alignment"] = env.alignment.to_meta()

    return PricingResult(pv=pv, greeks=greeks, meta=meta)


def run_risk(spec: PricingSpec) -> PricingResult:
    """Run risk (greeks) calculation."""
    spec.output.fields = list(
        set(spec.output.fields)
        | {"pv", "delta", "gamma", "vega", "theta", "rho"}
    )
    return run_pricing(spec)


def _resolve_underlying(spec: PricingSpec, cal: CalibrationSpec) -> tuple[str, Any]:
    market = spec.market
    uid = cal.underlying_id
    if uid is None:
        if len(market.underlyings) != 1:
            raise ValueError("calibration.underlying_id required when multiple underlyings")
        uid = market.underlyings[0].id
    underlying = next((u for u in market.underlyings if u.id == uid), None)
    if underlying is None:
        raise ValueError(f"Unknown calibration.underlying_id: {uid}")
    return uid, underlying


def run_calibrate(spec: PricingSpec, *, base_dir: Path | None = None) -> PricingResult:
    """Calibrate volatility (historical or implied) from DSL spec."""
    if spec.calibration is None:
        raise ValueError("task=calibrate requires a calibration section")

    cal = spec.calibration
    uid, underlying = _resolve_underlying(spec, cal)
    val_date = spec.market.valuation_date
    env = MarketEnv.from_spec(spec.to_dict())
    greeks: dict[str, float] = {}

    if cal.method == "historical":
        spot_cfg = underlying.spot
        if hasattr(spot_cfg, "model_dump"):
            spot_cfg = spot_cfg.model_dump()
        elif isinstance(spot_cfg, (int, float)):
            spot_cfg = {"source": "inline", "value": float(spot_cfg)}
        df, source_meta = load_series_for_calibration(
            valuation_date=val_date,
            instrument_id=uid,
            asset_class=underlying.asset_class.value,
            field=cal.field,
            lookback_days=cal.lookback_days,
            data=cal.data,
            underlying_spot=spot_cfg if isinstance(spot_cfg, dict) else None,
            base_dir=base_dir,
        )
        prices = df.set_index("datetime")["close"]
        sigma, cal_meta = historical_volatility(
            prices,
            window=cal.window,
            annualization=cal.annualization,
        )
    else:
        source_meta = {"source": "market_env", "instrument_id": uid}
        if spec.product is None:
            raise ValueError("calibration.method=implied requires product section")
        if cal.market_price is None:
            raise ValueError("calibration.market_price required for implied vol")
        params = spec.product.params
        if params.strike is None:
            raise ValueError("product.params.strike required for implied vol")
        sigma, cal_meta = implied_volatility(
            cal.market_price,
            env.spot(uid),
            params.strike,
            params.maturity,
            env.rate(),
            params.call_put,
            env.div_yield(uid),
        )
        greeks["market_price"] = cal.market_price
        if "model_price" in cal_meta:
            greeks["model_price"] = cal_meta["model_price"]

    meta: dict[str, Any] = {
        "task": "calibrate",
        "calibration_method": cal.method,
        "underlying_id": uid,
        "volatility": sigma,
        "valuation_date": val_date,
        "data_source": source_meta,
        "calibration": cal_meta,
    }
    if env.alignment:
        meta["alignment"] = env.alignment.to_meta()

    return PricingResult(pv=sigma, greeks=greeks, meta=meta)
