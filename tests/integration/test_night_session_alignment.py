"""W8 night-session align_policy end-to-end tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

import derivkit as dk
from derivkit.core.enums import AlignPolicy
from derivkit.data.alignment import align_spot_to_valuation, build_valuation_datetime
from derivkit.data.market_env import MarketEnv
from derivkit.dsl.loader import load_spec

COMMODITY_DIR = Path(__file__).resolve().parents[2] / "examples" / "commodity"


def _night_session_df() -> pd.DataFrame:
    return pd.DataFrame(
        {"close": [15180.0, 15250.0, 15320.0, 15450.0, 15520.0]},
        index=pd.to_datetime(
            [
                "2024-06-10 23:00:00",
                "2024-06-11 23:00:00",
                "2024-06-12 23:00:00",
                "2024-06-13 23:00:00",
                "2024-06-14 23:00:00",
            ]
        ),
    )


def test_build_valuation_datetime_night_session():
    val_dt = build_valuation_datetime(date(2024, 6, 14), "23:00", "Asia/Shanghai")
    assert val_dt.hour == 23
    assert val_dt.minute == 0
    assert val_dt.date() == date(2024, 6, 14)


def test_night_session_exact_match_vs_midnight_mismatch():
    df = _night_session_df()
    val_dt = build_valuation_datetime(date(2024, 6, 14), "23:00", "Asia/Shanghai")
    spot, record = align_spot_to_valuation(
        df,
        val_dt,
        align_policy=AlignPolicy.NEAREST_AVAILABLE,
        instrument_id="LH2409",
        session_close="23:00",
        tz="Asia/Shanghai",
    )
    assert spot == 15520.0
    assert record.rule == "exact_match"

    from datetime import datetime

    midnight = datetime(2024, 6, 14, 0, 0)
    spot_mid, record_mid = align_spot_to_valuation(
        df, midnight, align_policy=AlignPolicy.NEAREST_AVAILABLE, instrument_id="LH2409"
    )
    assert spot_mid != spot
    assert record_mid.rule == "nearest_available"


@pytest.mark.integration
def test_night_session_market_env_from_spec():
    spec = {
        "market": {
            "valuation_date": "2024-06-14",
            "calendar": "CN",
            "underlyings": [
                {
                    "id": "LH2409",
                    "asset_class": "commodity",
                    "spot": {
                        "source": "csv",
                        "path": str(COMMODITY_DIR / "data" / "lh2409.csv"),
                        "field": "close",
                        "tz": "Asia/Shanghai",
                        "session_close": "23:00",
                        "align_policy": "nearest_available",
                    },
                }
            ],
            "rates": [{"kind": "constant", "value": 0.025}],
            "vols": [{"id": "LH_IV", "kind": "constant", "value": 0.22, "underlying_id": "LH2409"}],
        }
    }
    env = MarketEnv.from_spec(spec)
    assert env.spot("LH2409") == 15520.0
    record = env.alignment.records[0]
    assert record.session_close == "23:00"
    assert record.rule == "exact_match"


@pytest.mark.integration
@pytest.mark.parametrize("align_policy", ["nearest_available", "prev_business_day", "same_day"])
def test_night_session_align_policies_end_to_end(align_policy: str):
    spec = load_spec(COMMODITY_DIR / "lh_vanilla_call.yaml")
    raw = spec.to_dict()
    raw["market"]["underlyings"][0]["spot"]["align_policy"] = align_policy
    result = dk.price(raw)
    assert result.pv > 0
    assert "alignment" in result.meta
    assert result.meta["alignment"]["policies"]["LH2409"] == align_policy


@pytest.mark.integration
def test_weekend_valuation_nearest_night_bar():
    """Saturday valuation should snap to nearest night-session bar."""
    spec = load_spec(COMMODITY_DIR / "lh_vanilla_call.yaml")
    raw = spec.to_dict()
    raw["market"]["valuation_date"] = "2024-06-15"
    result = dk.price(raw)
    alignment = result.meta["alignment"]
    record = next(r for r in alignment["records"] if r["instrument_id"] == "LH2409")
    assert record["rule"] == "nearest_available"
    assert alignment["aligned_spots"]["LH2409"] == 15520.0
