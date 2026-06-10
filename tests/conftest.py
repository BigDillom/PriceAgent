"""Shared test fixtures."""

from __future__ import annotations

import pytest

from derivkit.dsl.schema import PricingSpec


@pytest.fixture
def vanilla_spec_dict() -> dict:
    return {
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
        "output": {"deterministic": True, "seed": 42},
    }


@pytest.fixture
def vanilla_spec(vanilla_spec_dict) -> PricingSpec:
    return PricingSpec.model_validate(vanilla_spec_dict)


@pytest.fixture
def tol() -> dict[str, float]:
    return {
        "analytic": 0.0,
        "tree": 0.05,
        "fdm": 0.1,
        "mc": 0.2,
        "quad": 0.1,
    }
