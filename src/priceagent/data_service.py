"""Market data interface for agents and tooling."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from derivkit.core.enums import AlignPolicy, AssetClass
from derivkit.data.adapters import commodity, equity
from derivkit.data.adapters.base import load_csv, series_summary
from derivkit.data.alignment import align_spot_to_valuation, build_valuation_datetime
from derivkit.data.tushare_loader import resolve_exchange, resolve_option_opt_code
from priceagent.option_lookup import find_nearby_option_contract
from priceagent.tushare_client import TushareClient, resolve_ts_code

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXAMPLES = PROJECT_ROOT / "examples" / "commodity"
DSL_EXAMPLES = PROJECT_ROOT / "src" / "derivkit" / "dsl" / "examples"
QF_TASKS = PROJECT_ROOT / "src" / "derivkit" / "integ" / "tasks"


@dataclass
class DatasetInfo:
    """Registered offline market dataset."""

    id: str
    path: Path
    asset_class: str
    instrument_id: str
    description: str
    session_close: str = "16:00"
    tz: str = "Asia/Shanghai"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": str(self.path),
            "asset_class": self.asset_class,
            "instrument_id": self.instrument_id,
            "description": self.description,
            "session_close": self.session_close,
            "tz": self.tz,
        }


BUILTIN_DATASETS: list[DatasetInfo] = [
    DatasetInfo(
        id="lh2409",
        path=DEFAULT_EXAMPLES / "data" / "lh2409.csv",
        asset_class="commodity",
        instrument_id="LH2409",
        description="Live hog futures LH2409 (night session close 23:00)",
        session_close="23:00",
        tz="Asia/Shanghai",
    ),
    DatasetInfo(
        id="lc2409",
        path=DEFAULT_EXAMPLES / "data" / "lc2409.csv",
        asset_class="commodity",
        instrument_id="LC2409",
        description="Lithium carbonate futures LC2409 (night session close 23:00)",
        session_close="23:00",
        tz="Asia/Shanghai",
    ),
    DatasetInfo(
        id="lh_asf_shock",
        path=DEFAULT_EXAMPLES / "data" / "lh_asf_shock.csv",
        asset_class="commodity",
        instrument_id="LH_ASF",
        description="ASF shock scenario for live hog robustness tests",
        session_close="23:00",
        tz="Asia/Shanghai",
    ),
]


class DataService:
    """Unified read-only interface for offline CSV and Tushare market data."""

    def __init__(
        self,
        examples_root: Path | None = None,
        tushare_client: TushareClient | None = None,
    ) -> None:
        self.examples_root = examples_root or DEFAULT_EXAMPLES
        self._datasets = {d.id: d for d in BUILTIN_DATASETS}
        self._tushare = tushare_client

    def list_datasets(self) -> list[dict[str, Any]]:
        """List built-in CSV datasets available for pricing demos."""
        return [d.to_dict() for d in self._datasets.values()]

    def list_yaml_examples(self) -> list[dict[str, str]]:
        """List DerivKit DSL and QFbench task YAML files."""
        items: list[dict[str, str]] = []
        for root, label in ((DSL_EXAMPLES, "dsl"), (QF_TASKS, "qfbench"), (self.examples_root, "commodity")):
            if not root.exists():
                continue
            for path in sorted(root.rglob("*.yaml")):
                items.append({"id": path.stem, "category": label, "path": str(path)})
        return items

    def resolve_dataset(self, dataset_id: str) -> DatasetInfo:
        key = dataset_id.lower()
        if key not in self._datasets:
            raise KeyError(f"Unknown dataset: {dataset_id}. Available: {list(self._datasets)}")
        return self._datasets[key]

    def load_series(
        self,
        dataset_id: str | None = None,
        *,
        path: str | Path | None = None,
        instrument_id: str | None = None,
        asset_class: str = "commodity",
        field: str = "close",
    ) -> dict[str, Any]:
        """Load and summarize a price series."""
        if dataset_id:
            info = self.resolve_dataset(dataset_id)
            path = info.path
            instrument_id = info.instrument_id
            asset_class = info.asset_class

        if path is None or instrument_id is None:
            raise ValueError("Provide dataset_id or both path and instrument_id")

        adapter = commodity if asset_class == "commodity" else equity
        df = adapter.load_csv(path, instrument_id, asset_class)
        summary = series_summary(df, field)
        summary["path"] = str(path)
        return summary

    def get_spot(
        self,
        valuation_date: str,
        *,
        dataset_id: str | None = None,
        path: str | Path | None = None,
        instrument_id: str | None = None,
        asset_class: str = "commodity",
        field: str = "close",
        session_close: str = "23:00",
        tz: str = "Asia/Shanghai",
        align_policy: str = "nearest_available",
    ) -> dict[str, Any]:
        """Align spot to a valuation date using DerivKit alignment rules."""
        if dataset_id:
            info = self.resolve_dataset(dataset_id)
            path = info.path
            instrument_id = info.instrument_id
            asset_class = info.asset_class
            session_close = info.session_close
            tz = info.tz

        if path is None or instrument_id is None:
            raise ValueError("Provide dataset_id or both path and instrument_id")

        adapter = commodity if asset_class == "commodity" else equity
        df = adapter.load_csv(path, instrument_id, asset_class)
        df = df.set_index("datetime")

        val_date = date.fromisoformat(valuation_date[:10])
        val_dt = build_valuation_datetime(val_date, session_close, tz)
        policy = AlignPolicy(align_policy)
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
        return {
            "instrument_id": instrument_id,
            "valuation_date": valuation_date,
            "spot": spot,
            "alignment": record.to_dict(),
        }

    def inspect_csv(self, path: str | Path, rows: int = 5) -> dict[str, Any]:
        """Return head rows and column info for a CSV file."""
        p = Path(path)
        df = pd.read_csv(p, nrows=rows)
        return {
            "path": str(p.resolve()),
            "columns": list(df.columns),
            "preview": df.to_dict(orient="records"),
        }

    @property
    def tushare(self) -> TushareClient:
        if self._tushare is None:
            self._tushare = TushareClient()
        return self._tushare

    def load_tushare_series(
        self,
        symbol: str,
        valuation_date: str,
        *,
        ts_code: str | None = None,
        exchange: str | None = None,
        asset_class: str = "commodity",
        lookback_days: int = 60,
    ) -> dict[str, Any]:
        """Fetch and summarize a Tushare price series."""
        code = ts_code or resolve_ts_code(symbol, exchange)
        start, end = self.tushare.default_date_window(valuation_date, lookback_days)
        df = self.tushare.fetch_series(code, start, end, asset_class=asset_class)
        from derivkit.data.adapters.base import series_summary

        summary = series_summary(df, "close")
        summary.update(
            {
                "symbol": symbol,
                "ts_code": code,
                "source": "tushare",
                "start": start,
                "end": end,
            }
        )
        return summary

    def get_tushare_spot(
        self,
        valuation_date: str,
        symbol: str,
        *,
        ts_code: str | None = None,
        exchange: str | None = None,
        asset_class: str = "commodity",
        field: str = "close",
        session_close: str = "15:00",
        tz: str = "Asia/Shanghai",
        align_policy: str = "nearest_available",
        lookback_days: int = 60,
    ) -> dict[str, Any]:
        """Fetch Tushare series and align spot to valuation date."""
        code = ts_code or resolve_ts_code(symbol, exchange)
        instrument_id = code.split(".")[0]
        start, end = self.tushare.default_date_window(valuation_date, lookback_days)
        df = self.tushare.fetch_series(code, start, end, asset_class=asset_class)
        df = df.set_index("datetime")

        val_date = date.fromisoformat(valuation_date[:10])
        val_dt = build_valuation_datetime(val_date, session_close, tz)
        policy = AlignPolicy(align_policy)
        spot, record = align_spot_to_valuation(
            df,
            val_dt,
            field,
            policy,
            instrument_id,
            source_path=f"tushare:{code}",
            session_close=session_close,
            tz=tz,
        )
        return {
            "instrument_id": instrument_id,
            "symbol": symbol,
            "ts_code": code,
            "valuation_date": valuation_date,
            "spot": spot,
            "source": "tushare",
            "alignment": record.to_dict(),
        }

    def get_tushare_option_quote(
        self,
        valuation_date: str,
        symbol: str,
        strike: float,
        *,
        maturity: str = "3m",
        call_put: str = "call",
        exchange: str | None = None,
        price_field: str = "settle",
        session_close: str = "15:00",
        tz: str = "Asia/Shanghai",
        align_policy: str = "nearest_available",
    ) -> dict[str, Any]:
        """Find a nearby listed option and align its market price to valuation_date."""
        if price_field not in ("settle", "close"):
            raise ValueError("price_field must be 'settle' or 'close'")

        ex = resolve_exchange(symbol, exchange)
        opt_code = resolve_option_opt_code(symbol, exchange)
        contracts = self.tushare.fetch_option_basic(ex, opt_code=opt_code, call_put=call_put)
        match = find_nearby_option_contract(
            contracts,
            valuation_date=valuation_date,
            strike=strike,
            maturity=maturity,
            call_put=call_put,
            underlying_symbol=symbol,
        )

        ts_code = match["ts_code"]
        start, end = self.tushare.default_date_window(valuation_date, lookback_days=30)
        df = self.tushare.fetch_option_daily(ts_code, start, end, exchange=ex)
        df = df.set_index("datetime")

        val_date = date.fromisoformat(valuation_date[:10])
        val_dt = build_valuation_datetime(val_date, session_close, tz)
        policy = AlignPolicy(align_policy)
        market_price, record = align_spot_to_valuation(
            df,
            val_dt,
            price_field,
            policy,
            ts_code,
            source_path=f"tushare:opt_daily:{ts_code}",
            session_close=session_close,
            tz=tz,
        )
        return {
            "valuation_date": valuation_date,
            "underlying_symbol": symbol,
            "exchange": ex,
            "opt_code": opt_code,
            "matched_contract": match,
            "ts_code": ts_code,
            "price_field": price_field,
            "market_price": market_price,
            "source": "tushare",
            "alignment": record.to_dict(),
        }
