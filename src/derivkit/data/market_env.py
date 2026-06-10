"""MarketEnv: unified valuation context."""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from derivkit.core.enums import AlignPolicy, AssetClass, Compounding, DayCount
from derivkit.data.alignment import (
    AlignmentResult,
    align_spot_to_valuation,
    build_valuation_datetime,
)
from derivkit.data.calendars import Calendar
from derivkit.data.cn_calendar import CN_CALENDAR, ChineseCalendar
from derivkit.data.term_structures import ConstantRate, RateCurve
from derivkit.data.validators import validate_market_inputs, validate_spot
from derivkit.data.volmodels import ConstantVol

logger = logging.getLogger(__name__)


@dataclass
class UnderlyingSpec:
    """Normalized underlying specification."""

    id: str
    asset_class: AssetClass
    spot: float
    div_yield: float = 0.0


@dataclass
class MarketEnv:
    """Aggregated market environment for pricing."""

    valuation_date: date
    underlyings: dict[str, UnderlyingSpec] = field(default_factory=dict)
    rates: ConstantRate | RateCurve | None = None
    vols: dict[str, ConstantVol] = field(default_factory=dict)
    calendar: Calendar | None = None
    alignment: AlignmentResult | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def spot(self, underlying_id: str) -> float:
        if underlying_id not in self.underlyings:
            raise KeyError(f"Unknown underlying: {underlying_id}")
        return self.underlyings[underlying_id].spot

    def vol(self, underlying_id: str, t: float = 0.0) -> float:
        if underlying_id not in self.vols:
            raise KeyError(f"Unknown vol: {underlying_id}")
        return self.vols[underlying_id](t, self.spot(underlying_id))

    def rate(self, t: float = 0.0) -> float:
        if self.rates is None:
            return 0.0
        return self.rates(t)

    def disc_factor(self, t: float) -> float:
        if self.rates is None:
            return 1.0
        return self.rates.disc_factor(t)

    def div_yield(self, underlying_id: str) -> float:
        return self.underlyings[underlying_id].div_yield

    def bump_spot(self, underlying_id: str, amount: float) -> MarketEnv:
        """Return copy with bumped spot."""
        env = copy.deepcopy(self)
        u = env.underlyings[underlying_id]
        env.underlyings[underlying_id] = UnderlyingSpec(
            u.id, u.asset_class, u.spot + amount, u.div_yield
        )
        return env

    def bump_vol(self, underlying_id: str, amount: float) -> MarketEnv:
        env = copy.deepcopy(self)
        env.vols[underlying_id] = env.vols[underlying_id].bump(amount)
        return env

    def bump_rate(self, amount: float) -> MarketEnv:
        env = copy.deepcopy(self)
        if isinstance(env.rates, ConstantRate):
            env.rates = ConstantRate(
                env.rates.rate + amount,
                env.rates.day_count,
                env.rates.compounding,
                env.rates.rate_id,
            )
        elif isinstance(env.rates, RateCurve):
            env.rates = env.rates.bump(amount)
        return env

    def bump_time(self, dt: float) -> MarketEnv:
        """Shift valuation forward by dt years (for theta)."""
        env = copy.deepcopy(self)
        from datetime import timedelta

        env.valuation_date = env.valuation_date + timedelta(days=int(dt * 365))
        return env

    @classmethod
    def from_spec(cls, spec: dict[str, Any]) -> MarketEnv:
        """Build MarketEnv from DSL market section."""
        market = spec.get("market", spec)
        val_date = date.fromisoformat(str(market["valuation_date"])[:10])
        calendar = cls._resolve_calendar(market.get("calendar", "default"))
        alignment = AlignmentResult(valuation_date=val_date.isoformat())
        underlyings: dict[str, UnderlyingSpec] = {}
        vols: dict[str, ConstantVol] = {}

        for u in market.get("underlyings", []):
            uid = u["id"]
            asset_class = AssetClass(u.get("asset_class", "equity"))
            spot_data = u.get("spot")
            if isinstance(spot_data, (int, float)):
                spot = float(spot_data)
            elif isinstance(spot_data, dict):
                spot = cls._load_spot_from_source(spot_data, val_date, uid, alignment)
            else:
                raise ValueError(f"Invalid spot for {uid}")

            report = validate_spot(spot)
            if not report.passed:
                raise ValueError(report.issues[0].message)

            underlyings[uid] = UnderlyingSpec(
                uid, asset_class, spot, float(u.get("div_yield", 0.0))
            )
            alignment.aligned_spots[uid] = spot

        rates = cls._build_rates(market.get("rates", []))

        for v in market.get("vols", []):
            vid = v["id"]
            uid = v.get("underlying_id", vid.replace("_IV", ""))
            if uid not in underlyings and len(underlyings) == 1:
                uid = next(iter(underlyings))
            kind = v.get("kind", "constant")
            if kind == "constant":
                data = v.get("data") or {}
                sigma = float(v["value"] if v.get("value") is not None else data.get("value", 0.2))
            else:
                sigma = 0.2
            vols[uid] = ConstantVol(sigma, vid)

        spot_map = {uid: u.spot for uid, u in underlyings.items()}
        vol_map = {uid: v.sigma for uid, v in vols.items()}
        val_report = validate_market_inputs(spot_map, vol_map)
        if not val_report.passed:
            raise ValueError(val_report.issues[0].message)

        meta: dict[str, Any] = {
            "calendar": calendar.name if calendar else "default",
            "alignment": alignment.to_meta(),
        }
        if isinstance(calendar, ChineseCalendar):
            meta["calendar_detail"] = calendar.to_meta()

        env = cls(
            valuation_date=val_date,
            underlyings=underlyings,
            rates=rates,
            vols=vols,
            calendar=calendar,
            alignment=alignment,
            meta=meta,
        )
        return env

    @staticmethod
    def _resolve_calendar(name: str) -> Calendar | None:
        key = (name or "default").upper()
        if key in ("CN", "CHINA", "CHINESE"):
            return CN_CALENDAR
        if key == "DEFAULT":
            return Calendar(name="default")
        return Calendar(name=name)

    @staticmethod
    def _load_spot_from_source(
        spot_cfg: dict[str, Any],
        val_date: date,
        instrument_id: str,
        alignment: AlignmentResult,
    ) -> float:
        if spot_cfg.get("source") == "csv":
            path = Path(spot_cfg["path"])
            df = pd.read_csv(path, parse_dates=["datetime"])
            df = df.set_index("datetime")
            field = spot_cfg.get("field", "close")
            policy = AlignPolicy(spot_cfg.get("align_policy", "nearest_available"))
            session_close = spot_cfg.get("session_close", "16:00")
            tz = spot_cfg.get("tz", "UTC")
            val_dt = build_valuation_datetime(val_date, session_close, tz)
            spot, record = align_spot_to_valuation(
                df,
                val_dt,
                field,
                policy,
                instrument_id,
                source_path=str(path),
                session_close=session_close,
                tz=tz,
            )
            alignment.records.append(record)
            alignment.aligned_spots[instrument_id] = spot
            return spot
        raise ValueError(f"Unknown spot source: {spot_cfg.get('source')}")

    @staticmethod
    def _build_rates(rate_specs: list[dict[str, Any]]) -> ConstantRate | RateCurve | None:
        if not rate_specs:
            return ConstantRate(0.05)
        r = rate_specs[0]
        day_count = DayCount(r.get("day_count", "ACT/365"))
        compounding = Compounding(r.get("compounding", "continuous"))
        kind = r.get("kind", "constant")
        if kind == "constant":
            return ConstantRate(
                float(r.get("value", 0.05)),
                day_count,
                compounding,
                r.get("id", "default"),
            )
        if kind == "curve":
            data = r.get("data", {})
            if data.get("source") == "csv":
                df = pd.read_csv(data["path"])
                return RateCurve(
                    df["tenor"].tolist(),
                    df["rate"].tolist(),
                    day_count,
                    compounding,
                    r.get("id", "default"),
                )
        return ConstantRate(0.05)
