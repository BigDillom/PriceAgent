"""Match Tushare option contracts to target strike and maturity."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from derivkit.core.conventions import parse_tenor
from derivkit.data.tushare_loader import _normalize_call_put


def product_root(symbol: str) -> str:
    """Extract alphabetic product root from a futures symbol, e.g. LH2609 -> LH."""
    return "".join(ch for ch in symbol.strip().upper() if ch.isalpha())


def target_expiry_date(valuation_date: date, maturity: str) -> date:
    """Approximate calendar expiry from a tenor string like 3m."""
    days = max(1, int(round(parse_tenor(maturity) * 365)))
    return valuation_date + timedelta(days=days)


def _parse_contract_date(value: Any) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    return date.fromisoformat(text[:10])


def _filter_contracts(
    contracts: pd.DataFrame,
    *,
    valuation_date: date,
    call_put: str,
    underlying_symbol: str | None,
) -> pd.DataFrame:
    df = contracts.copy()
    cp = _normalize_call_put(call_put)
    if "call_put" in df.columns:
        df = df[df["call_put"].astype(str).str.upper() == cp]

    if "maturity_date" in df.columns:
        maturities = df["maturity_date"].map(_parse_contract_date)
        df = df[maturities.notna() & (maturities >= valuation_date)]

    if underlying_symbol:
        sym = underlying_symbol.strip().upper()
        root = product_root(sym)
        mask = pd.Series(False, index=df.index)
        if "opt_code" in df.columns:
            mask |= df["opt_code"].astype(str).str.upper() == root
        if "ts_code" in df.columns:
            mask |= df["ts_code"].astype(str).str.upper().str.startswith(sym)
        if "name" in df.columns:
            mask |= df["name"].astype(str).str.upper().str.contains(sym, regex=False)
        if mask.any():
            df = df[mask]

    if df.empty:
        raise ValueError(
            f"No active {call_put} options for underlying={underlying_symbol!r} on {valuation_date}"
        )
    return df


def score_contract(
    row: pd.Series,
    *,
    valuation_date: date,
    strike: float,
    maturity: str,
) -> float:
    """Lower score is a better match (strike distance + expiry distance)."""
    exercise = float(row["exercise_price"])
    strike_score = abs(exercise - strike) / max(strike, 1.0)

    expiry = _parse_contract_date(row.get("maturity_date"))
    target = target_expiry_date(valuation_date, maturity)
    if expiry is None:
        expiry_score = 1.0
    else:
        expiry_score = abs((expiry - target).days) / max((target - valuation_date).days, 1)

    return strike_score + expiry_score


def find_nearby_option_contract(
    contracts: pd.DataFrame,
    *,
    valuation_date: date | str,
    strike: float,
    maturity: str = "3m",
    call_put: str = "call",
    underlying_symbol: str | None = None,
) -> dict[str, Any]:
    """Pick the closest listed option by strike and expiry."""
    val_date = (
        valuation_date
        if isinstance(valuation_date, date)
        else date.fromisoformat(str(valuation_date)[:10])
    )
    filtered = _filter_contracts(
        contracts,
        valuation_date=val_date,
        call_put=call_put,
        underlying_symbol=underlying_symbol,
    )
    scores = filtered.apply(
        lambda row: score_contract(
            row,
            valuation_date=val_date,
            strike=strike,
            maturity=maturity,
        ),
        axis=1,
    )
    best_idx = scores.idxmin()
    row = filtered.loc[best_idx]
    expiry = _parse_contract_date(row.get("maturity_date"))
    return {
        "ts_code": str(row["ts_code"]),
        "name": str(row.get("name", "")),
        "exercise_price": float(row["exercise_price"]),
        "call_put": str(row.get("call_put", _normalize_call_put(call_put))),
        "maturity_date": expiry.isoformat() if expiry else None,
        "match_score": float(scores.loc[best_idx]),
        "target_strike": strike,
        "target_maturity": maturity,
    }
