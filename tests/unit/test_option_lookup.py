"""Unit tests for Tushare option contract matching."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from priceagent.option_lookup import find_nearby_option_contract, target_expiry_date


def _sample_contracts() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ts_code": "LH2609-C-12000.DCE",
                "name": "生猪2609购12000",
                "opt_code": "LH",
                "call_put": "C",
                "exercise_price": 12000.0,
                "maturity_date": "20260807",
            },
            {
                "ts_code": "LH2609-C-12200.DCE",
                "name": "生猪2609购12200",
                "opt_code": "LH",
                "call_put": "C",
                "exercise_price": 12200.0,
                "maturity_date": "20260807",
            },
            {
                "ts_code": "LH2609-P-12200.DCE",
                "name": "生猪2609沽12200",
                "opt_code": "LH",
                "call_put": "P",
                "exercise_price": 12200.0,
                "maturity_date": "20260807",
            },
        ]
    )


def test_target_expiry_date_three_months():
    assert target_expiry_date(date(2026, 6, 8), "3m") == date(2026, 9, 7)


def test_find_nearby_option_prefers_matching_strike():
    match = find_nearby_option_contract(
        _sample_contracts(),
        valuation_date="2026-06-08",
        strike=12200,
        maturity="3m",
        call_put="call",
        underlying_symbol="LH2609",
    )
    assert match["ts_code"] == "LH2609-C-12200.DCE"
    assert match["exercise_price"] == 12200.0


def test_find_nearby_option_filters_put():
    match = find_nearby_option_contract(
        _sample_contracts(),
        valuation_date="2026-06-08",
        strike=12200,
        maturity="3m",
        call_put="put",
        underlying_symbol="LH2609",
    )
    assert match["ts_code"] == "LH2609-P-12200.DCE"


def test_find_nearby_option_raises_when_no_match():
    with pytest.raises(ValueError, match="No active"):
        find_nearby_option_contract(
            _sample_contracts(),
            valuation_date="2027-01-01",
            strike=12200,
            maturity="3m",
            call_put="call",
            underlying_symbol="LH2609",
        )
