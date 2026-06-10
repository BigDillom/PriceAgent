"""Trading calendars and business-day utilities."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from derivkit.core.enums import BusinessConvention

logger = logging.getLogger(__name__)


class Calendar:
    """Business-day calendar with a statutory holiday set (weekends handled separately)."""

    def __init__(self, holidays: set[date] | None = None, name: str = "default") -> None:
        self.name = name
        self._holidays: set[date] = set(holidays) if holidays else set()

    @property
    def holidays(self) -> set[date]:
        return self._holidays

    def is_statutory_holiday(self, d: date) -> bool:
        return d in self._holidays

    def is_business_day(self, d: date) -> bool:
        return d.weekday() < 5 and d not in self._holidays

    def is_holiday(self, d: date) -> bool:
        """Non-business day (weekend or statutory holiday)."""
        return not self.is_business_day(d)

    def add_holiday(self, d: date) -> None:
        self._holidays.add(d)

    def remove_holiday(self, d: date) -> None:
        self._holidays.discard(d)

    def advance(self, d: date, period: timedelta) -> date:
        """Advance by |period.days| business days (sign follows period.days)."""
        new_date = d
        remaining = period.days
        if remaining == 0:
            return new_date
        step = 1 if remaining > 0 else -1
        count = abs(remaining)
        while count > 0:
            new_date += timedelta(days=step)
            if self.is_business_day(new_date):
                count -= 1
        return new_date

    def advance_business_days(
        self,
        d: date,
        n: int,
        convention: BusinessConvention = BusinessConvention.FOLLOWING,
    ) -> date:
        """Advance n signed business days, then apply convention if landing on non-business day."""
        if n == 0:
            current = d
        else:
            current = self.advance(d, timedelta(days=n))
        if convention == BusinessConvention.FOLLOWING and self.is_holiday(current):
            while self.is_holiday(current):
                current += timedelta(days=1)
        elif convention == BusinessConvention.PRECEDING and self.is_holiday(current):
            while self.is_holiday(current):
                current -= timedelta(days=1)
        return current

    def business_list_between(self, start: date, end: date) -> list[date]:
        """Business days from start through end (inclusive)."""
        if start > end:
            start, end = end, start
        days: list[date] = []
        current = start
        while current <= end:
            if self.is_business_day(current):
                days.append(current)
            current += timedelta(days=1)
        return days

    def business_days_between(self, start: date, end: date) -> int:
        """Business days after start through end (exclusive start, inclusive end)."""
        if start > end:
            return -self.business_days_between(end, start)
        return len(self.business_list_between(start, end)) - 1
