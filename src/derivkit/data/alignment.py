"""Cross-asset alignment and convention switching."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any
import pandas as pd

from derivkit.core.enums import AlignPolicy

logger = logging.getLogger(__name__)


def parse_session_close(session_close: str) -> time:
    """Parse HH:MM session close time."""
    parts = session_close.strip().split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    return time(hour, minute)


def build_valuation_datetime(
    val_date: date,
    session_close: str = "16:00",
    tz: str = "UTC",
) -> datetime:
    """Combine valuation date with asset session close (e.g. night session 23:00)."""
    close_time = parse_session_close(session_close)
    return datetime.combine(val_date, close_time)


def _normalize_valuation_timestamp(val_ts: pd.Timestamp, index: pd.DatetimeIndex) -> pd.Timestamp:
    """Align valuation timestamp dtype with price series index (naive vs tz-aware)."""
    if val_ts.tz is not None and index.tz is None:
        return val_ts.tz_convert(val_ts.tzinfo).tz_localize(None)
    if val_ts.tz is None and index.tz is not None:
        return val_ts.tz_localize(index.tz)
    return val_ts


@dataclass
class AlignmentRecord:
    """Audit trail for a single alignment operation."""

    instrument_id: str
    rule: str
    input_value: Any
    output_value: Any
    policy: AlignPolicy | None = None
    matched_timestamp: str | None = None
    delta_days: int | None = None
    source_path: str | None = None
    session_close: str | None = None
    tz: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "rule": self.rule,
            "input": self.input_value,
            "output": self.output_value,
            "policy": self.policy.value if self.policy else None,
            "matched_timestamp": self.matched_timestamp,
            "delta_days": self.delta_days,
            "source_path": self.source_path,
            "session_close": self.session_close,
            "tz": self.tz,
        }


@dataclass
class AlignmentResult:
    """Result of cross-asset alignment with provenance."""

    aligned_spots: dict[str, float] = field(default_factory=dict)
    records: list[AlignmentRecord] = field(default_factory=list)
    valuation_date: str | None = None

    def to_meta(self) -> dict[str, Any]:
        policies = {r.instrument_id: r.policy.value if r.policy else None for r in self.records}
        return {
            "valuation_date": self.valuation_date,
            "aligned_spots": dict(self.aligned_spots),
            "n_instruments": len(self.aligned_spots),
            "policies": policies,
            "records": [r.to_dict() for r in self.records],
        }


def align_spot_to_valuation(
    df: pd.DataFrame,
    valuation_date: datetime,
    field: str = "close",
    align_policy: AlignPolicy = AlignPolicy.NEAREST_AVAILABLE,
    instrument_id: str = "",
    source_path: str | None = None,
    session_close: str | None = None,
    tz: str | None = None,
) -> tuple[float, AlignmentRecord]:
    """Align a price series to a valuation datetime."""
    if df.empty:
        raise ValueError(f"No data for {instrument_id}")

    df = df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        if "datetime" in df.columns:
            df = df.set_index("datetime")
        else:
            raise ValueError("DataFrame must have DatetimeIndex or 'datetime' column")

    val_ts = _normalize_valuation_timestamp(pd.Timestamp(valuation_date), df.index)
    audit_kwargs = {
        "session_close": session_close,
        "tz": tz,
        "source_path": source_path,
    }

    if val_ts in df.index:
        spot = float(df.loc[val_ts, field])
        record = AlignmentRecord(
            instrument_id,
            "exact_match",
            val_ts.isoformat(),
            spot,
            align_policy,
            matched_timestamp=val_ts.isoformat(),
            delta_days=0,
            **audit_kwargs,
        )
        return spot, record

    if align_policy == AlignPolicy.SAME_DAY:
        same_day = df[df.index.date == val_ts.date()]
        if same_day.empty:
            raise ValueError(f"No same-day data for {instrument_id} on {val_ts.date()}")
        matched_ts = same_day.index[-1]
        spot = float(same_day.iloc[-1][field])
        record = AlignmentRecord(
            instrument_id,
            "same_day",
            val_ts.date().isoformat(),
            spot,
            align_policy,
            matched_timestamp=matched_ts.isoformat(),
            delta_days=(matched_ts.normalize() - val_ts.normalize()).days,
            **audit_kwargs,
        )
        return spot, record

    if align_policy == AlignPolicy.PREV_BUSINESS_DAY:
        prior = df[df.index < val_ts]
        if prior.empty:
            raise ValueError(f"No prior data for {instrument_id}")
        matched_ts = prior.index[-1]
        spot = float(prior.iloc[-1][field])
        record = AlignmentRecord(
            instrument_id,
            "prev_business_day",
            val_ts.isoformat(),
            spot,
            align_policy,
            matched_timestamp=matched_ts.isoformat(),
            delta_days=(matched_ts.normalize() - val_ts.normalize()).days,
            **audit_kwargs,
        )
        return spot, record

    idx = df.index.get_indexer([val_ts], method="nearest")[0]
    nearest_ts = df.index[idx]
    spot = float(df.iloc[idx][field])
    record = AlignmentRecord(
        instrument_id,
        "nearest_available",
        val_ts.isoformat(),
        spot,
        align_policy,
        matched_timestamp=nearest_ts.isoformat(),
        delta_days=(nearest_ts.normalize() - val_ts.normalize()).days,
        **audit_kwargs,
    )
    return spot, record


def align_spots_batch(
    specs: list[dict[str, Any]],
    valuation_date: datetime,
    default_policy: AlignPolicy = AlignPolicy.NEAREST_AVAILABLE,
) -> AlignmentResult:
    """Align multiple instruments from CSV-backed spot specs."""
    result = AlignmentResult(valuation_date=valuation_date.date().isoformat())
    for spec in specs:
        uid = spec["id"]
        spot_cfg = spec.get("spot", {})
        if isinstance(spot_cfg, (int, float)):
            spot = float(spot_cfg)
            result.aligned_spots[uid] = spot
            result.records.append(
                AlignmentRecord(uid, "literal", spot, spot, None, delta_days=0)
            )
            continue
        if spot_cfg.get("source") != "csv":
            raise ValueError(f"Unsupported spot source for {uid}")
        path = spec.get("spot", {}).get("path") or spot_cfg.get("path")
        df = pd.read_csv(path, parse_dates=["datetime"]).set_index("datetime")
        field = spot_cfg.get("field", "close")
        policy = AlignPolicy(spot_cfg.get("align_policy", default_policy.value))
        session_close = spot_cfg.get("session_close", "16:00")
        tz = spot_cfg.get("tz", "UTC")
        if isinstance(valuation_date, datetime):
            val_dt = valuation_date
        else:
            val_dt = build_valuation_datetime(valuation_date, session_close, tz)
        spot, record = align_spot_to_valuation(
            df,
            val_dt,
            field,
            policy,
            uid,
            source_path=str(path),
            session_close=session_close,
            tz=tz,
        )
        result.aligned_spots[uid] = spot
        result.records.append(record)
    return result
