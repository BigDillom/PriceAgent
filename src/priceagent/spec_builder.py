"""Build and normalize DerivKit DSL specs for LLM tool calls."""

from __future__ import annotations

from typing import Any

PRODUCT_TYPE_ALIASES: dict[str, tuple[str, str | None]] = {
    "european_call": ("vanilla.european", "call"),
    "european_put": ("vanilla.european", "put"),
    "vanilla_call": ("vanilla.european", "call"),
    "vanilla_put": ("vanilla.european", "put"),
    "call": ("vanilla.european", "call"),
    "put": ("vanilla.european", "put"),
}


def build_vanilla_spec(
    *,
    valuation_date: str,
    instrument_id: str,
    spot: float,
    strike: float,
    maturity: str = "3m",
    call_put: str = "call",
    rate: float = 0.025,
    volatility: float = 0.22,
    asset_class: str = "commodity",
    engine: str = "analytic",
) -> dict[str, Any]:
    """Build a valid PricingSpec dict for a European vanilla option."""
    return {
        "task": "price",
        "market": {
            "valuation_date": valuation_date,
            "calendar": "CN",
            "underlyings": [
                {"id": instrument_id, "asset_class": asset_class, "spot": float(spot)},
            ],
            "rates": [
                {
                    "id": "CNY_RF",
                    "kind": "constant",
                    "value": float(rate),
                    "day_count": "ACT/365",
                    "compounding": "continuous",
                }
            ],
            "vols": [
                {
                    "id": f"{instrument_id}_IV",
                    "kind": "constant",
                    "value": float(volatility),
                    "underlying_id": instrument_id,
                }
            ],
        },
        "product": {
            "type": "vanilla.european",
            "params": {
                "strike": float(strike),
                "maturity": maturity,
                "call_put": call_put,
            },
        },
        "engine": {"method": engine},
        "output": {"fields": ["pv", "delta"], "deterministic": True, "seed": 42},
    }


def normalize_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Coerce common LLM mistakes into a valid PricingSpec-shaped dict."""
    out = dict(spec)
    out.setdefault("task", "price")

    market = dict(out.get("market") or {})
    valuation_date = market.get("valuation_date")

    # Flat market: {spot, rate, volatility} at top level
    if "underlyings" not in market and "spot" in market:
        instrument_id = market.get("instrument_id") or market.get("symbol") or "UNDERLYING"
        market["underlyings"] = [
            {
                "id": instrument_id,
                "asset_class": market.get("asset_class", "commodity"),
                "spot": market.pop("spot"),
            }
        ]

    # underlyings as dict keyed by id
    underlyings = market.get("underlyings")
    if isinstance(underlyings, dict):
        market["underlyings"] = [
            {"id": uid, **(vals if isinstance(vals, dict) else {"spot": vals})}
            for uid, vals in underlyings.items()
        ]

    # list items use name instead of id
    if isinstance(market.get("underlyings"), list):
        fixed_underlyings = []
        for u in market["underlyings"]:
            item = dict(u)
            if "id" not in item and "name" in item:
                item["id"] = item.pop("name")
            if "symbol" in item and "id" not in item:
                item["id"] = item.pop("symbol")
            fixed_underlyings.append(item)
        market["underlyings"] = fixed_underlyings

    # per-underlying volatility -> vols array
    if market.get("underlyings") and not market.get("vols"):
        vols = []
        for u in market["underlyings"]:
            vol = u.pop("volatility", None) or u.pop("vol", None)
            if vol is not None:
                uid = u["id"]
                vols.append(
                    {
                        "id": f"{uid}_IV",
                        "kind": "constant",
                        "value": float(vol),
                        "underlying_id": uid,
                    }
                )
        if vols:
            market["vols"] = vols

    # flat rate at market level
    if "rate" in market and not market.get("rates"):
        market["rates"] = [
            {
                "id": "CNY_RF",
                "kind": "constant",
                "value": float(market.pop("rate")),
                "day_count": "ACT/365",
                "compounding": "continuous",
            }
        ]

    if "volatility" in market and not market.get("vols"):
        uid = market["underlyings"][0]["id"] if market.get("underlyings") else "UNDERLYING"
        market["vols"] = [
            {
                "id": f"{uid}_IV",
                "kind": "constant",
                "value": float(market.pop("volatility")),
                "underlying_id": uid,
            }
        ]

    if valuation_date:
        market["valuation_date"] = str(valuation_date)[:10]

    out["market"] = market

    product = dict(out.get("product") or {})
    ptype = str(product.get("type", "vanilla.european")).lower()
    params = dict(product.get("params") or {})

    # product fields at product top level
    for key in ("strike", "maturity", "call_put"):
        if key in product and key not in params:
            params[key] = product.pop(key)

    if ptype in PRODUCT_TYPE_ALIASES:
        canonical, cp = PRODUCT_TYPE_ALIASES[ptype]
        product["type"] = canonical
        if cp:
            params.setdefault("call_put", cp)
    else:
        product["type"] = ptype

    product["params"] = params
    out["product"] = product

    engine = out.get("engine")
    if isinstance(engine, str):
        out["engine"] = {"method": engine}
    elif isinstance(engine, dict) and "method" not in engine:
        engine.setdefault("method", "analytic")

    out.setdefault("engine", {"method": "analytic"})
    out.setdefault(
        "output",
        {"fields": ["pv", "delta"], "deterministic": True, "seed": 42},
    )
    return out
