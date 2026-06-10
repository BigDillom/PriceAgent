"""Unit tests for derivkit Tushare loader helpers and client."""

from __future__ import annotations

import pandas as pd
import pytest

from derivkit.data.tushare_loader import (
    TushareClient,
    _normalize_call_put,
    resolve_exchange,
    resolve_option_opt_code,
    resolve_ts_code,
)


def test_resolve_ts_code_and_exchange():
    assert resolve_ts_code("LH2409") == "LH2409.DCE"
    assert resolve_exchange("LH2409") == "DCE"
    assert resolve_option_opt_code("LH2609") == "OPLH2609.DCE"


def test_normalize_call_put():
    assert _normalize_call_put("call") == "C"
    assert _normalize_call_put("P") == "P"
    with pytest.raises(ValueError):
        _normalize_call_put("invalid")


def test_fetch_futures_and_options_mocked():
    fut_df = pd.DataFrame(
        {
            "trade_date": ["20240614"],
            "open": [15500.0],
            "high": [15600.0],
            "low": [15450.0],
            "close": [15520.0],
            "vol": [1000],
        }
    )
    opt_basic_df = pd.DataFrame(
        {
            "ts_code": ["LH2609-C-12200.DCE"],
            "name": ["生猪2609购12200"],
            "opt_code": ["OPLH2609.DCE"],
            "call_put": ["C"],
            "exercise_price": [12200.0],
            "maturity_date": ["20260818"],
        }
    )
    opt_daily_df = pd.DataFrame(
        {
            "trade_date": ["20240614"],
            "open": [500.0],
            "high": [520.0],
            "low": [490.0],
            "close": [515.0],
            "settle": [512.0],
            "vol": [800],
            "oi": [5000],
        }
    )

    class FakePro:
        def fut_daily(self, **kwargs):
            return fut_df

        def opt_basic(self, **kwargs):
            return opt_basic_df

        def opt_daily(self, **kwargs):
            return opt_daily_df

    client = TushareClient(token="test-token")
    client._pro = FakePro()

    fut = client.fetch_futures_daily("LH2409.DCE", "2024-06-01", "2024-06-14")
    assert fut["close"].iloc[-1] == 15520.0

    basic = client.fetch_option_basic("DCE", opt_code="OPLH2609.DCE", call_put="call")
    assert basic.iloc[0]["ts_code"] == "LH2609-C-12200.DCE"

    daily = client.fetch_option_daily("LH2609-C-12200.DCE", "2024-06-01", "2024-06-14")
    assert daily["settle"].iloc[-1] == 512.0

    start, end = client.default_date_window("2024-06-14", lookback_days=30)
    assert end == "2024-06-14"
    assert start == "2024-05-15"

    stock_df = pd.DataFrame(
        {
            "trade_date": ["20240614"],
            "open": [10.0],
            "high": [11.0],
            "low": [9.5],
            "close": [10.5],
            "vol": [1_000_000],
        }
    )

    class StockPro(FakePro):
        def daily(self, **kwargs):
            return stock_df

    client._pro = StockPro()
    eq = client.fetch_stock_daily("000001.SZ", "2024-06-01", "2024-06-14")
    assert eq["close"].iloc[-1] == 10.5
    assert (
        client.fetch_series("000001.SZ", "2024-06-01", "2024-06-14", asset_class="equity")[
            "close"
        ].iloc[-1]
        == 10.5
    )


def test_fetch_empty_data_raises():
    class EmptyPro:
        def fut_daily(self, **kwargs):
            return pd.DataFrame()

        def opt_basic(self, **kwargs):
            return None

        def opt_daily(self, **kwargs):
            return pd.DataFrame()

    client = TushareClient(token="test-token")
    client._pro = EmptyPro()

    with pytest.raises(ValueError, match="No futures data"):
        client.fetch_futures_daily("LH2409.DCE", "2024-06-01", "2024-06-14")
    with pytest.raises(ValueError, match="No option contracts"):
        client.fetch_option_basic("DCE")
    with pytest.raises(ValueError, match="No option daily data"):
        client.fetch_option_daily("LH2609-C-12200.DCE", "2024-06-01", "2024-06-14")


def test_resolve_exchange_unknown():
    with pytest.raises(ValueError, match="Cannot infer exchange"):
        resolve_exchange("UNKNOWN99")


def test_get_tushare_token_missing(monkeypatch):
    from derivkit.data import tushare_loader

    monkeypatch.setenv("TUSHARE_TOKEN", "")
    monkeypatch.setattr(tushare_loader, "_load_dotenv", lambda: None)
    with pytest.raises(OSError, match="TUSHARE_TOKEN"):
        tushare_loader.get_tushare_token()
