"""W8 commodity end-to-end examples (live hog / lithium carbonate)."""

from __future__ import annotations

from pathlib import Path

import pytest

import derivkit as dk
from derivkit.dsl.loader import load_spec

COMMODITY_DIR = Path(__file__).resolve().parents[2] / "examples" / "commodity"


@pytest.mark.integration
@pytest.mark.parametrize(
    "yaml_name,underlying_id,expected_spot",
    [
        ("lh_vanilla_call.yaml", "LH2409", 15520.0),
        ("lc_vanilla_call.yaml", "LC2409", 102400.0),
    ],
)
def test_commodity_dsl_examples(yaml_name: str, underlying_id: str, expected_spot: float):
    path = COMMODITY_DIR / yaml_name
    spec = load_spec(path)
    result = dk.price(spec)
    assert result.pv > 0
    alignment = result.meta["alignment"]
    assert alignment["aligned_spots"][underlying_id] == expected_spot
    records = alignment["records"]
    assert any(r["instrument_id"] == underlying_id for r in records)
    night_record = next(r for r in records if r["instrument_id"] == underlying_id)
    assert night_record["session_close"] == "23:00"
    assert night_record["tz"] == "Asia/Shanghai"
    assert night_record["rule"] == "exact_match"
