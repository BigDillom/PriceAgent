"""Pydantic models for controlled DSL configuration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from derivkit.core.enums import (
    AlignPolicy,
    AsianAveSubstitution,
    AssetClass,
    AverageMethod,
    BarrierType,
    CallPut,
    EngineMethod,
    ExerciseType,
    PaymentType,
)


class SpotSource(BaseModel):
    source: str = "inline"
    path: str | None = None
    field: str = "close"
    tz: str = "UTC"
    session_close: str = "16:00"
    align_policy: AlignPolicy = AlignPolicy.NEAREST_AVAILABLE
    value: float | None = None


class UnderlyingSpec(BaseModel):
    id: str
    asset_class: AssetClass = AssetClass.EQUITY
    spot: float | SpotSource
    div_yield: float = 0.0


class RateSpec(BaseModel):
    id: str = "default"
    kind: str = "constant"
    value: float | None = None
    day_count: str = "ACT/365"
    compounding: str = "continuous"
    calendar: str = "default"
    data: dict[str, Any] | None = None


class VolSpec(BaseModel):
    id: str
    kind: str = "constant"
    value: float | None = None
    underlying_id: str | None = None
    data: dict[str, Any] | None = None


class MarketSpec(BaseModel):
    valuation_date: str
    underlyings: list[UnderlyingSpec]
    rates: list[RateSpec] = Field(default_factory=list)
    vols: list[VolSpec] = Field(default_factory=list)


class ProductParams(BaseModel):
    strike: float | None = None
    maturity: str | float = "1y"
    call_put: CallPut = CallPut.CALL
    exercise: ExerciseType = ExerciseType.EUROPEAN
    s0: float | None = None
    barrier_out: float | None = None
    barrier_in: float | None = None
    coupon_out: float | None = None
    coupon: float | None = None
    barrier_yield: float | None = None
    lock_term: str | None = None
    margin_lvl: float = 1.0
    parti_in: float = 1.0
    # barrier / digital / asian (W3)
    barrier: float | None = None
    barrier_type: BarrierType | None = None
    rebate: float | None = None
    participation: float = 1.0
    payment_type: PaymentType | None = None
    discrete_obs_interval: float | None = None
    ave_method: AverageMethod = AverageMethod.GEOMETRIC
    substitute: AsianAveSubstitution = AsianAveSubstitution.UNDERLYING
    obs_start_frac: float = 0.0
    obs_end_frac: float = 1.0
    s_average: float | None = None
    enhanced: bool = False
    limited_price: float | None = None
    t_step_per_year: int = 243

    model_config = {"extra": "allow"}


class ProductSpec(BaseModel):
    type: str
    params: ProductParams = Field(default_factory=ProductParams)


class EngineSpec(BaseModel):
    method: EngineMethod = EngineMethod.ANALYTIC
    params: dict[str, Any] = Field(default_factory=dict)


class OutputSpec(BaseModel):
    fields: list[str] = Field(default_factory=lambda: ["pv"])
    tolerance: dict[str, float] = Field(default_factory=lambda: {"pv": 1e-2})
    deterministic: bool = True
    seed: int = 0


class CalibrationSpec(BaseModel):
    """Volatility calibration configuration (task=calibrate)."""

    method: str = "historical"  # historical | implied
    underlying_id: str | None = None
    lookback_days: int = 120
    window: int | None = None
    annualization: float = 243.0
    field: str = "close"
    data: dict[str, Any] | None = None
    market_price: float | None = None

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        key = v.strip().lower()
        if key not in ("historical", "implied"):
            raise ValueError(f"calibration.method must be historical|implied, got {v}")
        return key


class PricingSpec(BaseModel):
    """Root DSL specification."""

    task: str = "price"
    market: MarketSpec
    product: ProductSpec | None = None
    calibration: CalibrationSpec | None = None
    engine: EngineSpec = Field(default_factory=EngineSpec)
    output: OutputSpec = Field(default_factory=OutputSpec)
    backend: str | None = None  # reserved for future backend selection

    @field_validator("task")
    @classmethod
    def validate_task(cls, v: str) -> str:
        if v not in ("price", "risk", "calibrate"):
            raise ValueError(f"task must be price|risk|calibrate, got {v}")
        return v

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
