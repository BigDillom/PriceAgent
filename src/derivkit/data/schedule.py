"""Observation schedule generation for OTC structured products.

Logic adapted from PriceLib (Apache 2.0):
pricelib/common/time/timeutils.py
"""

from __future__ import annotations

import calendar as cal_mod
import logging
from datetime import date, timedelta
from enum import Enum

from derivkit.core.enums import BusinessConvention
from derivkit.data.calendars import Calendar

logger = logging.getLogger(__name__)

# Natural-day spacing used to estimate observation count (matches PriceLib FREQS).
_FREQ_NATURAL_DAYS = {"w": 7.0, "d": 14.0, "m": 30.416, "s": 91.25}


class MonthAdjustment(str, Enum):
    """When adjusting a non-business observation date, avoid crossing month boundary."""

    YES = "yes"
    NO = "no"


class EndOfMonthModify(str, Enum):
    """End-date adjustment when start is last business day of month."""

    YES = "yes"
    NO = "no"


def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    year = d.year + m // 12
    month = m % 12 + 1
    max_day = cal_mod.monthrange(year, month)[1]
    return date(year, month, min(d.day, max_day))


def _freq_step(freq: str, i: int, start: date) -> date:
    if freq == "w":
        return start + timedelta(weeks=i)
    if freq == "d":
        return start + timedelta(weeks=2 * i)
    if freq == "m":
        return _add_months(start, i)
    if freq == "s":
        return _add_months(start, 3 * i)
    raise ValueError(f"Unknown schedule frequency: {freq!r}")


class Schedule:
    """Generate knock-out / observation date sequences on a trading calendar."""

    def __init__(
        self,
        trade_calendar: Calendar,
        start: date | None = None,
        end: date | None = None,
        freq: str = "m",
        lock_term: int = 1,
        convention: BusinessConvention = BusinessConvention.FOLLOWING,
        correction: MonthAdjustment = MonthAdjustment.YES,
        endofmonthmodify: EndOfMonthModify = EndOfMonthModify.YES,
        date_schedule: list[date] | None = None,
    ) -> None:
        self.start = start
        self.end = end
        self.freq = freq
        self.lock_term = lock_term
        self.convention = convention
        self.correction = correction
        self.endofmonthmodify = endofmonthmodify
        self.trade_calendar = trade_calendar
        if date_schedule is None:
            if start is None or end is None:
                raise ValueError("Schedule requires start and end, or date_schedule")
            self.date_schedule = self.generate_schedule()
        else:
            self.date_schedule = list(date_schedule)
        self.count_business: list[int] | None = None
        self.count_calendar: list[int] | None = None

    def generate_schedule(self) -> list[date]:
        assert self.start is not None and self.end is not None
        start, end = self.start, self.end
        cal = self.trade_calendar

        if self.endofmonthmodify == EndOfMonthModify.YES and (
            end in cal.holidays or end.weekday() > 4
        ):
            next_startday = cal.advance(start, timedelta(days=1))
            if start.month != next_startday.month:
                prev_endday = cal.advance(end, timedelta(days=-1))
                next_endday = cal.advance(end, timedelta(days=1))
                if prev_endday.month != next_endday.month:
                    end = prev_endday
        self.end = end

        n_dates = (end - start).days + 1
        fq = _FREQ_NATURAL_DAYS[self.freq]
        n_obs = round(n_dates / fq) + 1
        n_obs_dates = [_freq_step(self.freq, i, start) for i in range(n_obs)][self.lock_term :]

        schedule: list[date] = []
        for obs_date in n_obs_dates:
            if obs_date in cal.holidays or obs_date.weekday() > 4:
                if self.convention == BusinessConvention.PRECEDING:
                    obs_date_adj = cal.advance(obs_date, timedelta(days=-1))
                    if (
                        self.correction == MonthAdjustment.YES
                        and obs_date_adj.month != obs_date.month
                    ):
                        obs_date_adj = cal.advance(obs_date, timedelta(days=1))
                else:
                    obs_date_adj = cal.advance(obs_date, timedelta(days=1))
                    if (
                        self.correction == MonthAdjustment.YES
                        and obs_date_adj.month != obs_date.month
                    ):
                        obs_date_adj = cal.advance(obs_date, timedelta(days=-1))
                schedule.append(obs_date_adj)
            else:
                schedule.append(obs_date)

        if schedule and schedule[-1] > end:
            schedule[-1] = cal.advance(schedule[-1], timedelta(days=-1))

        self.date_schedule = list(dict.fromkeys(schedule))
        return self.date_schedule

    def dates(self) -> list[date]:
        return list(self.date_schedule)

    def count_business_days(self, base_date: date) -> list[int]:
        self.count_business = [
            self.trade_calendar.business_days_between(base_date, d) for d in self.date_schedule
        ]
        return self.count_business

    def count_calendar_days(self, base_date: date) -> list[int]:
        self.count_calendar = [(d - base_date).days for d in self.date_schedule]
        return self.count_calendar

    def to_meta(self) -> dict:
        return {
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "freq": self.freq,
            "lock_term": self.lock_term,
            "convention": self.convention.value,
            "correction": self.correction.value,
            "endofmonthmodify": self.endofmonthmodify.value,
            "n_observations": len(self.date_schedule),
            "calendar": self.trade_calendar.name,
        }
