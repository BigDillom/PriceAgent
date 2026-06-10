"""LLM tool schemas and execution handlers for DerivKit."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

import derivkit as dk
from derivkit.dsl.loader import load_spec

from priceagent.data_service import DataService
from priceagent.spec_builder import build_vanilla_spec, normalize_spec

logger = logging.getLogger(__name__)


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "calibrate_volatility",
            "description": (
                "Calibrate annualized volatility. method=historical: pass symbol (e.g. LH2609) "
                "to pull ~lookback_days of Tushare futures daily bars; optional dataset_id for "
                "built-in CSV only. method=implied inverts BSM from market_price; if market_price "
                "is omitted, fetches a nearby option from Tushare opt_daily (settle by default)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["historical", "implied"]},
                    "symbol": {"type": "string", "description": "Futures symbol, e.g. LH2609"},
                    "valuation_date": {"type": "string"},
                    "exchange": {"type": "string", "description": "DCE for hog futures"},
                    "lookback_days": {
                        "type": "integer",
                        "description": "Calendar days of history for Tushare (default 90 ≈ 3 months)",
                        "default": 90,
                    },
                    "dataset_id": {
                        "type": "string",
                        "description": "Optional built-in CSV (lh2409); omit to use Tushare",
                    },
                    "window": {
                        "type": "integer",
                        "description": "Rolling return window in trading days; auto-shrinks if too large",
                    },
                    "annualization": {"type": "number", "default": 243},
                    "market_price": {
                        "type": "number",
                        "description": "Observed option price for implied; omit to auto-fetch from Tushare",
                    },
                    "strike": {"type": "number", "description": "Required for implied vol"},
                    "maturity": {"type": "string", "default": "3m"},
                    "call_put": {"type": "string", "enum": ["call", "put"], "default": "call"},
                    "rate": {"type": "number", "default": 0.025},
                    "spot": {"type": "number", "description": "Override underlying spot for implied"},
                    "price_field": {
                        "type": "string",
                        "enum": ["settle", "close"],
                        "default": "settle",
                        "description": "Tushare opt_daily field when auto-fetching option price",
                    },
                },
                "required": ["method", "symbol", "valuation_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "price_tushare_vanilla",
            "description": (
                "Preferred: fetch Tushare spot and price a European vanilla option in one step. "
                "Use this instead of manually building price_from_spec."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "e.g. LH2409"},
                    "valuation_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "strike": {"type": "number"},
                    "maturity": {"type": "string", "default": "3m"},
                    "call_put": {"type": "string", "enum": ["call", "put"], "default": "call"},
                    "volatility": {"type": "number", "default": 0.22},
                    "rate": {"type": "number", "default": 0.025},
                    "engine": {"type": "string", "default": "analytic"},
                    "exchange": {"type": "string"},
                },
                "required": ["symbol", "valuation_date", "strike"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_market_datasets",
            "description": "List built-in offline market datasets (CSV) for commodity/equity pricing.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_pricing_examples",
            "description": "List available DerivKit DSL YAML examples and QFbench tasks.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "load_market_series",
            "description": "Load and summarize a market price series from a built-in dataset id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {
                        "type": "string",
                        "description": "Dataset id, e.g. lh2409, lc2409",
                    },
                    "field": {"type": "string", "description": "Price field", "default": "close"},
                },
                "required": ["dataset_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_spot_quote",
            "description": "Get aligned spot price for a valuation date from a dataset.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string"},
                    "valuation_date": {
                        "type": "string",
                        "description": "ISO date YYYY-MM-DD",
                    },
                    "align_policy": {
                        "type": "string",
                        "enum": ["same_day", "prev_business_day", "nearest_available"],
                        "default": "nearest_available",
                    },
                },
                "required": ["dataset_id", "valuation_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "price_from_yaml",
            "description": "Run DerivKit pricing from a YAML task file path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "yaml_path": {
                        "type": "string",
                        "description": "Absolute or project-relative path to task YAML",
                    },
                },
                "required": ["yaml_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "load_tushare_series",
            "description": "Fetch market data from Tushare Pro (requires TUSHARE_TOKEN).",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Contract symbol, e.g. LH2409, LC2409, or full ts_code LH2409.DCE",
                    },
                    "valuation_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "asset_class": {
                        "type": "string",
                        "enum": ["commodity", "equity"],
                        "default": "commodity",
                    },
                    "exchange": {
                        "type": "string",
                        "description": "Exchange suffix if symbol has no dot, e.g. DCE, GFE",
                    },
                },
                "required": ["symbol", "valuation_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tushare_option_quote",
            "description": (
                "Find a nearby listed option on Tushare (opt_basic + opt_daily) and return "
                "its aligned market price (settle or close) for implied vol calibration."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Underlying futures symbol, e.g. LH2609",
                    },
                    "valuation_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "strike": {"type": "number"},
                    "maturity": {"type": "string", "default": "3m"},
                    "call_put": {"type": "string", "enum": ["call", "put"], "default": "call"},
                    "exchange": {"type": "string", "description": "DCE for hog futures"},
                    "price_field": {
                        "type": "string",
                        "enum": ["settle", "close"],
                        "default": "settle",
                    },
                },
                "required": ["symbol", "valuation_date", "strike"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tushare_spot",
            "description": "Get aligned spot from Tushare for a valuation date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "valuation_date": {"type": "string"},
                    "session_close": {
                        "type": "string",
                        "description": "Session close time HH:MM, default 15:00 for futures daily",
                        "default": "15:00",
                    },
                    "asset_class": {"type": "string", "default": "commodity"},
                    "exchange": {"type": "string"},
                },
                "required": ["symbol", "valuation_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "price_from_spec",
            "description": (
                "Advanced: inline DSL spec. product.type must be vanilla.european (not european_call). "
                "market must have valuation_date and underlyings as a list with id field."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "spec": {
                        "type": "object",
                        "description": "PricingSpec dict; common mistakes are auto-corrected",
                    },
                },
                "required": ["spec"],
            },
        },
    },
]


class ToolRegistry:
    """Register tool handlers backed by DerivKit and DataService."""

    def __init__(self, data_service: DataService | None = None) -> None:
        self.data = data_service or DataService()
        self._handlers: dict[str, Callable[..., Any]] = {
            "list_market_datasets": lambda **_: self.data.list_datasets(),
            "list_pricing_examples": lambda **_: self.data.list_yaml_examples(),
            "load_market_series": self._load_market_series,
            "get_spot_quote": self._get_spot_quote,
            "load_tushare_series": self._load_tushare_series,
            "get_tushare_spot": self._get_tushare_spot,
            "get_tushare_option_quote": self._get_tushare_option_quote,
            "calibrate_volatility": self._calibrate_volatility,
            "price_tushare_vanilla": self._price_tushare_vanilla,
            "price_from_yaml": self._price_from_yaml,
            "price_from_spec": self._price_from_spec,
        }

    @staticmethod
    def schemas() -> list[dict[str, Any]]:
        return TOOL_SCHEMAS

    def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in self._handlers:
            raise KeyError(f"Unknown tool: {name}")
        return self._handlers[name](**arguments)

    def _load_market_series(self, dataset_id: str, field: str = "close") -> dict[str, Any]:
        return self.data.load_series(dataset_id=dataset_id, field=field)

    def _get_spot_quote(
        self,
        dataset_id: str,
        valuation_date: str,
        align_policy: str = "nearest_available",
    ) -> dict[str, Any]:
        return self.data.get_spot(
            valuation_date,
            dataset_id=dataset_id,
            align_policy=align_policy,
        )

    def _load_tushare_series(
        self,
        symbol: str,
        valuation_date: str,
        asset_class: str = "commodity",
        exchange: str | None = None,
    ) -> dict[str, Any]:
        return self.data.load_tushare_series(
            symbol,
            valuation_date,
            asset_class=asset_class,
            exchange=exchange,
        )

    def _get_tushare_spot(
        self,
        symbol: str,
        valuation_date: str,
        session_close: str = "15:00",
        asset_class: str = "commodity",
        exchange: str | None = None,
    ) -> dict[str, Any]:
        return self.data.get_tushare_spot(
            valuation_date,
            symbol,
            asset_class=asset_class,
            session_close=session_close,
            exchange=exchange,
        )

    def _get_tushare_option_quote(
        self,
        symbol: str,
        valuation_date: str,
        strike: float,
        maturity: str = "3m",
        call_put: str = "call",
        exchange: str | None = None,
        price_field: str = "settle",
    ) -> dict[str, Any]:
        return self.data.get_tushare_option_quote(
            valuation_date,
            symbol,
            strike,
            maturity=maturity,
            call_put=call_put,
            exchange=exchange,
            price_field=price_field,
        )

    def _calibrate_volatility(
        self,
        method: str,
        symbol: str,
        valuation_date: str,
        dataset_id: str | None = None,
        window: int | None = None,
        annualization: float = 243.0,
        lookback_days: int = 90,
        exchange: str | None = None,
        market_price: float | None = None,
        strike: float | None = None,
        maturity: str = "3m",
        call_put: str = "call",
        rate: float = 0.025,
        spot: float | None = None,
        price_field: str = "settle",
    ) -> dict[str, Any]:
        option_quote: dict[str, Any] | None = None
        if method == "implied" and market_price is None:
            if strike is None:
                raise ValueError(
                    "implied calibration requires strike when market_price is not provided"
                )
            option_quote = self.data.get_tushare_option_quote(
                valuation_date,
                symbol,
                strike,
                maturity=maturity,
                call_put=call_put,
                exchange=exchange,
                price_field=price_field,
            )
            market_price = option_quote["market_price"]

        market: dict[str, Any] = {
            "valuation_date": valuation_date,
            "calendar": "CN",
            "underlyings": [],
            "rates": [
                {
                    "id": "CNY_RF",
                    "kind": "constant",
                    "value": rate,
                }
            ],
        }
        calibration_block: dict[str, Any] = {
            "method": method,
            "underlying_id": symbol,
            "window": window,
            "annualization": annualization,
            "lookback_days": lookback_days,
        }

        if method == "historical" and dataset_id:
            info = self.data.resolve_dataset(dataset_id)
            market["underlyings"] = [
                {
                    "id": symbol,
                    "asset_class": info.asset_class,
                    "spot": {
                        "source": "csv",
                        "path": str(info.path),
                        "field": "close",
                        "tz": info.tz,
                        "session_close": info.session_close,
                    },
                }
            ]
        elif method == "historical":
            spot_info = self.data.get_tushare_spot(
                valuation_date, symbol=symbol, exchange=exchange
            )
            market["underlyings"] = [
                {
                    "id": spot_info["instrument_id"],
                    "asset_class": "commodity",
                    "spot": spot_info["spot"],
                }
            ]
            data_cfg: dict[str, Any] = {"source": "tushare", "symbol": symbol}
            if exchange:
                data_cfg["exchange"] = exchange
            calibration_block["data"] = data_cfg
            calibration_block["underlying_id"] = spot_info["instrument_id"]
        elif spot is not None:
            market["underlyings"] = [
                {"id": symbol, "asset_class": "commodity", "spot": spot},
            ]
        else:
            spot_info = self.data.get_tushare_spot(
                valuation_date, symbol=symbol, exchange=exchange
            )
            market["underlyings"] = [
                {"id": symbol, "asset_class": "commodity", "spot": spot_info["spot"]},
            ]

        spec: dict[str, Any] = {
            "task": "calibrate",
            "market": market,
            "calibration": calibration_block,
        }
        if method == "implied":
            if market_price is None or strike is None:
                raise ValueError("implied calibration requires market_price and strike")
            spec["product"] = {
                "type": "vanilla.european",
                "params": {"strike": strike, "maturity": maturity, "call_put": call_put},
            }
            spec["calibration"]["market_price"] = market_price

        result = dk.calibrate(spec)
        out = result.to_dict()
        if option_quote is not None:
            out["option_quote"] = option_quote
        return out

    def _price_tushare_vanilla(
        self,
        symbol: str,
        valuation_date: str,
        strike: float,
        maturity: str = "3m",
        call_put: str = "call",
        volatility: float = 0.22,
        rate: float = 0.025,
        engine: str = "analytic",
        exchange: str | None = None,
    ) -> dict[str, Any]:
        spot_info = self.data.get_tushare_spot(
            valuation_date,
            symbol,
            exchange=exchange,
        )
        instrument_id = spot_info["instrument_id"]
        spec = build_vanilla_spec(
            valuation_date=valuation_date,
            instrument_id=instrument_id,
            spot=spot_info["spot"],
            strike=strike,
            maturity=maturity,
            call_put=call_put,
            rate=rate,
            volatility=volatility,
            engine=engine,
        )
        pricing = dk.price(spec).to_dict()
        return {"tushare_spot": spot_info, "spec": spec, "pricing": pricing}

    def _price_from_yaml(self, yaml_path: str) -> dict[str, Any]:
        path = Path(yaml_path)
        if not path.is_absolute():
            root = Path(__file__).resolve().parents[2]
            candidate = root / path
            if candidate.exists():
                path = candidate
        result = dk.price(path)
        return result.to_dict()

    def _price_from_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_spec(spec)
        result = dk.price(normalized)
        return result.to_dict()


def execute_tool(
    name: str,
    arguments: str | dict[str, Any],
    registry: ToolRegistry | None = None,
) -> str:
    """Execute a tool and return JSON string (for LLM tool role messages)."""
    reg = registry or ToolRegistry()
    args = json.loads(arguments) if isinstance(arguments, str) else arguments
    try:
        payload = reg.execute(name, args)
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        logger.exception("Tool %s failed", name)
        return json.dumps({"error": str(exc), "tool": name})
