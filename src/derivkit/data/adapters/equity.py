"""Equity market data adapter."""

from __future__ import annotations

import pandas as pd

from derivkit.core.enums import AssetClass
from derivkit.data.adapters import base
from derivkit.data.adapters.base import load_csv, series_summary

__all__ = ["load_csv", "normalize", "series_summary", "ASSET_CLASS"]

ASSET_CLASS = AssetClass.EQUITY


def normalize(
    df: pd.DataFrame, instrument_id: str, asset_class: AssetClass | str = ASSET_CLASS
) -> pd.DataFrame:
    return base.normalize(df, instrument_id, asset_class)
