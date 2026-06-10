"""Tushare Pro market data loader (optional dependency)."""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Any

import pandas as pd

from derivkit.core.enums import AssetClass
from derivkit.data.adapters import commodity, equity

logger = logging.getLogger(__name__)

FUTURES_EXCHANGE_SUFFIX: dict[str, str] = {
    "LH": "DCE",
    "LC": "GFE",
    "I": "DCE",
    "RB": "SHF",
    "CU": "SHF",
    "AU": "SHF",
}


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


def get_tushare_token() -> str:
    _load_dotenv()
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        raise OSError(
            "TUSHARE_TOKEN is not set. Register at https://tushare.pro and add the token to .env"
        )
    return token


def _normalize_call_put(call_put: str) -> str:
    cp = call_put.strip().upper()
    if cp in ("C", "CALL"):
        return "C"
    if cp in ("P", "PUT"):
        return "P"
    raise ValueError(f"call_put must be call/put or C/P, got {call_put!r}")


def resolve_exchange(symbol: str, exchange: str | None = None) -> str:
    """Resolve Tushare exchange code (DCE, GFE, SHF, ...) from futures symbol."""
    if exchange:
        return exchange.upper()
    root = "".join(ch for ch in symbol.strip().upper() if ch.isalpha())
    suffix = FUTURES_EXCHANGE_SUFFIX.get(root)
    if suffix:
        return suffix
    raise ValueError(
        f"Cannot infer exchange for {symbol}. "
        f"Pass exchange= or full ts_code. Known roots: {list(FUTURES_EXCHANGE_SUFFIX)}"
    )


def resolve_ts_code(symbol: str, exchange: str | None = None) -> str:
    """Resolve contract symbol to Tushare ts_code (e.g. LH2409 -> LH2409.DCE)."""
    symbol = symbol.strip().upper()
    if "." in symbol:
        return symbol
    if exchange:
        return f"{symbol}.{exchange.upper()}"
    return f"{symbol}.{resolve_exchange(symbol)}"


def resolve_option_opt_code(symbol: str, exchange: str | None = None) -> str:
    """Resolve Tushare opt_basic opt_code for a futures month (e.g. LH2609 -> OPLH2609.DCE)."""
    return f"OP{resolve_ts_code(symbol, exchange)}"


class TushareClient:
    """Thin wrapper around tushare.pro_api for DerivKit-compatible series."""

    def __init__(self, token: str | None = None) -> None:
        self.token = token or get_tushare_token()
        self._pro = None

    @property
    def pro(self):
        if self._pro is None:
            try:
                import tushare as ts
            except ImportError as exc:
                raise ImportError("Install data extras: pip install -e '.[data]'") from exc
            self._pro = ts.pro_api(self.token)
        return self._pro

    def fetch_futures_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        df = self.pro.fut_daily(
            ts_code=ts_code,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
        )
        if df is None or df.empty:
            raise ValueError(f"No futures data for {ts_code} between {start_date} and {end_date}")
        instrument_id = ts_code.split(".")[0]
        out = pd.DataFrame(
            {
                "datetime": pd.to_datetime(df["trade_date"], format="%Y%m%d"),
                "open": df["open"],
                "high": df["high"],
                "low": df["low"],
                "close": df["close"],
                "volume": df.get("vol", df.get("volume", 0)),
            }
        )
        return commodity.normalize(out, instrument_id, AssetClass.COMMODITY)

    def fetch_stock_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        df = self.pro.daily(
            ts_code=ts_code,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
        )
        if df is None or df.empty:
            raise ValueError(f"No stock data for {ts_code} between {start_date} and {end_date}")
        instrument_id = ts_code.split(".")[0]
        out = pd.DataFrame(
            {
                "datetime": pd.to_datetime(df["trade_date"], format="%Y%m%d"),
                "open": df["open"],
                "high": df["high"],
                "low": df["low"],
                "close": df["close"],
                "volume": df["vol"],
            }
        )
        return equity.normalize(out, instrument_id, AssetClass.EQUITY)

    def fetch_series(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
        *,
        asset_class: str = "commodity",
    ) -> pd.DataFrame:
        if asset_class == "equity":
            return self.fetch_stock_daily(ts_code, start_date, end_date)
        return self.fetch_futures_daily(ts_code, start_date, end_date)

    def fetch_option_basic(
        self,
        exchange: str,
        *,
        opt_code: str | None = None,
        call_put: str | None = None,
    ) -> pd.DataFrame:
        """List option contracts from Tushare opt_basic."""
        kwargs: dict[str, Any] = {"exchange": exchange.upper()}
        if opt_code:
            kwargs["opt_code"] = opt_code.upper()
        if call_put:
            kwargs["call_put"] = _normalize_call_put(call_put)
        df = self.pro.opt_basic(**kwargs)
        if df is None or df.empty:
            raise ValueError(
                f"No option contracts from opt_basic(exchange={exchange}, opt_code={opt_code})"
            )
        return df

    def fetch_option_daily(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
        *,
        exchange: str | None = None,
    ) -> pd.DataFrame:
        """Fetch option daily bars (close, settle, etc.) via opt_daily."""
        kwargs: dict[str, Any] = {
            "ts_code": ts_code,
            "start_date": start_date.replace("-", ""),
            "end_date": end_date.replace("-", ""),
        }
        if exchange:
            kwargs["exchange"] = exchange.upper()
        df = self.pro.opt_daily(**kwargs)
        if df is None or df.empty:
            raise ValueError(
                f"No option daily data for {ts_code} between {start_date} and {end_date}"
            )
        out = pd.DataFrame(
            {
                "datetime": pd.to_datetime(df["trade_date"], format="%Y%m%d"),
                "open": df["open"],
                "high": df["high"],
                "low": df["low"],
                "close": df["close"],
                "settle": df.get("settle", df["close"]),
                "volume": df.get("vol", df.get("volume", 0)),
                "oi": df.get("oi", 0),
            }
        )
        out["ts_code"] = ts_code
        return out

    def default_date_window(self, valuation_date: str, lookback_days: int = 60) -> tuple[str, str]:
        end = date.fromisoformat(valuation_date[:10])
        start = end - timedelta(days=lookback_days)
        return start.isoformat(), end.isoformat()
