"""End-to-end vanilla option pricing example."""

import derivkit as dk

spec = {
    "task": "price",
    "market": {
        "valuation_date": "2024-01-05",
        "underlyings": [{"id": "SPX", "asset_class": "index", "spot": 100.0}],
        "rates": [{"id": "USD_RF", "kind": "constant", "value": 0.05}],
        "vols": [{"id": "SPX", "kind": "constant", "value": 0.2, "underlying_id": "SPX"}],
    },
    "product": {
        "type": "vanilla.european",
        "params": {"strike": 100, "maturity": "1y", "call_put": "call"},
    },
    "engine": {"method": "analytic"},
    "output": {
        "fields": ["pv", "delta", "gamma"],
        "tolerance": {"pv": 1e-2},
        "deterministic": True,
        "seed": 0,
    },
}

if __name__ == "__main__":
    result = dk.price(spec)
    print(f"PV: {result.pv:.4f}")
    print(f"Greeks: {result.greeks}")
    print(f"Meta: {result.meta}")
