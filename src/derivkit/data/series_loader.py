"""Load price series for calibration from CSV or Tushare."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from derivkit.core.enums import AssetClass
from derivkit.data.adapters import commodity, equity

logger = logging.getLogger(__name__)


def _adapter_for(asset_class: str):
    return commodity if asset_class == "commodity" else equity


def load_csv_series(
    path: str | Path,
    instrument_id: str,
    asset_class: str = "commodity",
    field: str = "close",
) -> pd.DataFrame:
    """Load and normalize a CSV price series."""
    adapter = _adapter_for(asset_class)
    df = adapter.load_csv(path, instrument_id, asset_class)
    if field != "close" and field in df.columns:
        df = df.rename(columns={field: "close"})
    return df


def load_tushare_series(
    symbol: str,
    valuation_date: str,
    *,
    exchange: str | None = None,
    asset_class: str = "commodity",
    lookback_days: int = 120,
    field: str = "close",
) -> pd.DataFrame:
    """Load futures/stock daily series from Tushare Pro."""
    from derivkit.data.tushare_loader import TushareClient, resolve_ts_code

    client = TushareClient()
    ts_code = resolve_ts_code(symbol, exchange)
    end = date.fromisoformat(valuation_date[:10])
    start = end - timedelta(days=lookback_days)
    df = client.fetch_series(
        ts_code,
        start.isoformat(),
        end.isoformat(),
        asset_class=asset_class,
    )
    if field != "close" and field in df.columns:
        df = df.rename(columns={field: "close"})
    return df


def load_series_for_calibration(
    *,
    valuation_date: str,
    instrument_id: str,
    asset_class: str = "commodity",
    field: str = "close",
    lookback_days: int = 120,
    data: dict[str, Any] | None = None,
    underlying_spot: Any = None,
    base_dir: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Resolve calibration data source and return normalized price series + meta."""
    meta: dict[str, Any] = {
        "instrument_id": instrument_id,
        "field": field,
        "lookback_days": lookback_days,
    }

    if data:
        source = data.get("source", "csv")
        meta["source"] = source
        if source == "csv":
            path = Path(data["path"])
            if base_dir and not path.is_absolute():
                path = (base_dir / path).resolve()
            df = load_csv_series(path, instrument_id, asset_class, field)
            meta["path"] = str(path)
            return df, meta
        if source == "tushare":
            symbol = data.get("symbol", instrument_id)
            df = load_tushare_series(
                symbol,
                valuation_date,
                exchange=data.get("exchange"),
                asset_class=asset_class,
                lookback_days=lookback_days,
                field=field,
            )
            meta["symbol"] = symbol
            meta["ts_code"] = data.get("ts_code")
            return df, meta
        raise ValueError(f"Unknown calibration data source: {source}")

    if isinstance(underlying_spot, dict):
        spot_cfg = dict(underlying_spot)
        source = spot_cfg.get("source", "csv")
        meta["source"] = source
        if source == "csv" and spot_cfg.get("path"):
            path = Path(spot_cfg["path"])
            if base_dir and not path.is_absolute():
                path = (base_dir / path).resolve()
            df = load_csv_series(path, instrument_id, asset_class, field)
            meta["path"] = str(path)
            return df, meta
        if source == "tushare":
            df = load_tushare_series(
                spot_cfg.get("symbol", instrument_id),
                valuation_date,
                exchange=spot_cfg.get("exchange"),
                asset_class=asset_class,
                lookback_days=lookback_days,
                field=field,
            )
            return df, meta

    raise ValueError(
        "Calibration requires calibration.data or underlyings[].spot with csv/tushare source"
    )
