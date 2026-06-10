"""Tests for DSL product.type alias normalization."""

from __future__ import annotations

import derivkit as dk
import pytest

from derivkit.dsl.loader import load_spec
from derivkit.dsl.product_normalize import canonicalize_product, resolve_product_alias


@pytest.mark.parametrize(
    ("alias", "canonical", "exercise"),
    [
        ("american", "vanilla.european", "american"),
        ("american_call", "vanilla.european", "american"),
        ("vanilla.american", "vanilla.european", "american"),
        ("european_put", "vanilla.european", "european"),
        ("snowball", "snowball.standard", None),
        ("asian", "asian.geometric", None),
        ("asian_arithmetic", "asian.arithmetic", None),
        ("barrier_up_and_out", "barrier.up_and_out", None),
        ("digital", "digital.cash", None),
        ("phoenix", "phoenix.standard", None),
        ("fcn", "fcn.standard", None),
    ],
)
def test_resolve_product_alias(alias: str, canonical: str, exercise: str | None):
    resolved, defaults = resolve_product_alias(alias)
    assert resolved == canonical
    if exercise is not None:
        assert defaults.get("exercise") == exercise


def test_canonicalize_product_hoists_exercise():
    product = canonicalize_product(
        {
            "type": "american",
            "strike": 12200,
            "maturity": "3m",
            "call_put": "call",
        }
    )
    assert product["type"] == "vanilla.european"
    assert product["params"]["exercise"] == "american"
    assert product["params"]["strike"] == 12200


def _minimal_market() -> dict:
    return {
        "valuation_date": "2024-06-14",
        "underlyings": [{"id": "LH2609", "asset_class": "commodity", "spot": 11750.0}],
        "rates": [{"id": "CNY_RF", "kind": "constant", "value": 0.025}],
        "vols": [
            {
                "id": "LH2609_IV",
                "kind": "constant",
                "value": 0.22,
                "underlying_id": "LH2609",
            }
        ],
    }


def test_american_vanilla_mc_prices_via_load_spec():
    spec = load_spec(
        {
            "task": "price",
            "market": _minimal_market(),
            "product": {
                "type": "american",
                "params": {"strike": 12200, "maturity": "3m", "call_put": "call"},
            },
            "engine": {"method": "mc", "params": {"n_paths": 5000, "seed": 1}},
            "output": {"fields": ["pv", "delta"], "deterministic": True, "seed": 1},
        }
    )
    assert spec.product.type == "vanilla.european"
    assert spec.product.params.exercise.value == "american"
    result = dk.price(spec)
    assert result.pv > 0


def test_snowball_alias_loads():
    spec = load_spec(
        {
            "task": "price",
            "market": {
                "valuation_date": "2024-01-05",
                "underlyings": [{"id": "CSI1000", "asset_class": "index", "spot": 100.0}],
                "rates": [{"id": "CN_RF", "kind": "constant", "value": 0.05}],
                "vols": [
                    {
                        "id": "CSI1000",
                        "kind": "constant",
                        "value": 0.2,
                        "underlying_id": "CSI1000",
                    }
                ],
            },
            "product": {
                "type": "snowball",
                "params": {
                    "s0": 100,
                    "barrier_out": 103,
                    "barrier_in": 80,
                    "coupon_out": 0.113,
                    "maturity": "1y",
                    "lock_term": "3m",
                },
            },
            "engine": {"method": "mc", "params": {"n_paths": 1000, "seed": 42}},
            "output": {"fields": ["pv"], "deterministic": True, "seed": 42},
        }
    )
    assert spec.product.type == "snowball.standard"
