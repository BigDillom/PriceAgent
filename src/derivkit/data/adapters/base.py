"""Shared CSV loading and normalization for market data adapters."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from derivkit.core.enums import AdjFlag, AssetClass

OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")


def load_csv(
    path: str | Path,
    instrument_id: str,
    asset_class: AssetClass | str,
    *,
    datetime_col: str = "datetime",
) -> pd.DataFrame:
    """Load a CSV price series and normalize to the internal schema."""
    df = pd.read_csv(path, parse_dates=[datetime_col])
    if datetime_col != "datetime":
        df = df.rename(columns={datetime_col: "datetime"})
    return normalize(df, instrument_id, asset_class)


def normalize(
    df: pd.DataFrame,
    instrument_id: str,
    asset_class: AssetClass | str,
) -> pd.DataFrame:
    """Normalize raw market data to the internal schema (§7.1)."""
    if "datetime" not in df.columns:
        raise ValueError("DataFrame must contain a datetime column")

    result = df.copy()
    result["instrument_id"] = instrument_id
    result["asset_class"] = (
        asset_class.value if isinstance(asset_class, AssetClass) else str(asset_class)
    )
    result["adj_flag"] = AdjFlag.NONE.value

    if not isinstance(result["datetime"].dtype, pd.DatetimeTZDtype):
        result["datetime"] = pd.to_datetime(result["datetime"])

    result = result.sort_values("datetime").reset_index(drop=True)
    return result


def series_summary(df: pd.DataFrame, field: str = "close") -> dict:
    """Return a JSON-serializable summary of a normalized series."""
    if field not in df.columns:
        raise KeyError(f"Field not found: {field}")

    series = df[field].dropna()
    start = df["datetime"].iloc[0]
    end = df["datetime"].iloc[-1]
    return {
        "instrument_id": df["instrument_id"].iloc[0],
        "asset_class": df["asset_class"].iloc[0],
        "field": field,
        "rows": len(df),
        "start": start.isoformat() if hasattr(start, "isoformat") else str(start),
        "end": end.isoformat() if hasattr(end, "isoformat") else str(end),
        "latest": float(series.iloc[-1]),
        "min": float(series.min()),
        "max": float(series.max()),
        "mean": float(series.mean()),
    }
