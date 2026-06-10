"""Tests for alignment provenance and validator aggregation."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from derivkit.core.enums import AlignPolicy
from derivkit.data.alignment import (
    AlignmentResult,
    align_spot_to_valuation,
    build_valuation_datetime,
)
from derivkit.data.market_env import MarketEnv


def test_alignment_record_provenance_fields():
    idx = pd.date_range("2024-01-02", periods=5, freq="B")
    df = pd.DataFrame({"close": [100.0, 101.0, 102.0, 103.0, 104.0]}, index=idx)
    val_dt = datetime(2024, 1, 5, 15, 0)
    spot, record = align_spot_to_valuation(
        df, val_dt, align_policy=AlignPolicy.NEAREST_AVAILABLE, instrument_id="TEST"
    )
    assert spot == 103.0
    assert record.matched_timestamp is not None
    assert record.delta_days is not None
    assert record.to_dict()["rule"] == "nearest_available"


def test_alignment_result_meta():
    result = AlignmentResult(valuation_date="2024-01-05")
    meta = result.to_meta()
    assert meta["valuation_date"] == "2024-01-05"
    assert "n_instruments" in meta


def test_build_valuation_datetime_session_close():
    from datetime import date

    val_dt = build_valuation_datetime(date(2024, 6, 14), "23:00")
    assert val_dt.hour == 23
    assert val_dt.minute == 0


def test_market_env_cn_calendar_meta():
    spec = {
        "market": {
            "valuation_date": "2024-01-05",
            "calendar": "CN",
            "underlyings": [{"id": "CSI300", "asset_class": "index", "spot": 3500.0}],
            "rates": [{"kind": "constant", "value": 0.03}],
            "vols": [{"id": "CSI300", "kind": "constant", "value": 0.18, "underlying_id": "CSI300"}],
        }
    }
    env = MarketEnv.from_spec(spec)
    assert env.calendar is not None
    assert env.calendar.name == "CN"
    assert env.meta["calendar"] == "CN"
    assert "calendar_detail" in env.meta
