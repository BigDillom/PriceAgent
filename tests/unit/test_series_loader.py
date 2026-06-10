"""Unit tests for calibration series loading."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from derivkit.data.series_loader import load_csv_series, load_series_for_calibration

LH_CSV = Path(__file__).resolve().parents[2] / "examples" / "commodity" / "data" / "lh2409.csv"


def test_load_csv_series_with_field_rename():
    df = load_csv_series(LH_CSV, "LH2409", field="close")
    assert "close" in df.columns
    assert len(df) >= 1


def test_load_series_for_calibration_csv_data_block():
    df, meta = load_series_for_calibration(
        valuation_date="2024-06-14",
        instrument_id="LH2409",
        data={"source": "csv", "path": str(LH_CSV)},
    )
    assert meta["source"] == "csv"
    assert len(df) >= 1


def test_load_series_for_calibration_tushare_mocked():
    mock_df = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2024-06-10", "2024-06-14"]),
            "open": [15000.0, 15500.0],
            "high": [15100.0, 15600.0],
            "low": [14900.0, 15400.0],
            "close": [15050.0, 15520.0],
            "volume": [100, 200],
            "instrument_id": ["LH2409", "LH2409"],
            "asset_class": ["commodity", "commodity"],
        }
    )

    class FakeClient:
        def fetch_series(self, ts_code, start, end, asset_class="commodity"):
            return mock_df

    with patch("derivkit.data.tushare_loader.TushareClient", FakeClient):
        df, meta = load_series_for_calibration(
            valuation_date="2024-06-14",
            instrument_id="LH2409",
            data={"source": "tushare", "symbol": "LH2409", "exchange": "DCE"},
        )
    assert meta["source"] == "tushare"
    assert df["close"].iloc[-1] == 15520.0


def test_load_series_for_calibration_spot_tushare_mocked():
    mock_df = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2024-06-14"]),
            "close": [15520.0],
            "volume": [100],
            "instrument_id": ["LH2409"],
            "asset_class": ["commodity"],
        }
    )

    class FakeClient:
        def fetch_series(self, ts_code, start, end, asset_class="commodity"):
            return mock_df

    with patch("derivkit.data.tushare_loader.TushareClient", FakeClient):
        df, meta = load_series_for_calibration(
            valuation_date="2024-06-14",
            instrument_id="LH2409",
            underlying_spot={"source": "tushare", "symbol": "LH2409"},
        )
    assert meta["source"] == "tushare"
    assert df["close"].iloc[-1] == 15520.0


def test_load_series_for_calibration_requires_source():
    with pytest.raises(ValueError, match="Calibration requires"):
        load_series_for_calibration(
            valuation_date="2024-06-14",
            instrument_id="LH2409",
            underlying_spot=15520.0,
        )


def test_load_series_for_calibration_unknown_source():
    with pytest.raises(ValueError, match="Unknown calibration data source"):
        load_series_for_calibration(
            valuation_date="2024-06-14",
            instrument_id="LH2409",
            data={"source": "bloomberg"},
        )
