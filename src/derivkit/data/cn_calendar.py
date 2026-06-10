"""Chinese mainland trading calendar (statutory holidays 2004–2026).

Holiday data adapted from PriceLib (Apache 2.0):
pricelib/common/time/calendars.py
"""

from __future__ import annotations

import json
import logging
from datetime import date
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

from derivkit.data.calendars import Calendar

logger = logging.getLogger(__name__)

_PACKAGE = "derivkit.data.resources"


@lru_cache(maxsize=1)
def load_cn_holidays() -> dict[date, str]:
    """Load CN statutory holidays from bundled JSON."""
    try:
        raw = resources.files(_PACKAGE).joinpath("cn_holidays.json").read_text(encoding="utf-8")
    except (FileNotFoundError, TypeError):
        path = Path(__file__).resolve().parent / "resources" / "cn_holidays.json"
        raw = path.read_text(encoding="utf-8")
    data: dict[str, str] = json.loads(raw)
    return {date.fromisoformat(k): v for k, v in data.items()}


class ChineseCalendar(Calendar):
    """Mainland China calendar: Mon–Fri minus statutory holidays."""

    def __init__(self, extra_holidays: dict[date, str] | None = None) -> None:
        holidays = load_cn_holidays()
        if extra_holidays:
            holidays = {**holidays, **extra_holidays}
        super().__init__(holidays=set(holidays.keys()), name="CN")
        self.holidays_dict: dict[date, str] = holidays

    def holiday_name(self, d: date) -> str | None:
        return self.holidays_dict.get(d)

    def to_meta(self) -> dict[str, Any]:
        years = sorted({d.year for d in self.holidays_dict})
        return {
            "name": self.name,
            "holiday_count": len(self.holidays_dict),
            "year_range": [years[0], years[-1]] if years else None,
        }


CN_CALENDAR = ChineseCalendar()
