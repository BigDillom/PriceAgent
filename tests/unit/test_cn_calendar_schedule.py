"""Tests for Chinese calendar and OTC observation Schedule."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from derivkit.core.enums import BusinessConvention
from derivkit.data.calendars import Calendar
from derivkit.data.cn_calendar import CN_CALENDAR, ChineseCalendar, load_cn_holidays
from derivkit.data.schedule import EndOfMonthModify, MonthAdjustment, Schedule
from derivkit.data.validators import (
    validate_market_inputs,
    validate_rate_curve,
    validate_vol_surface,
)


def test_cn_holidays_loaded():
    holidays = load_cn_holidays()
    assert len(holidays) >= 600
    assert holidays[date(2024, 10, 1)] == "national_day"


def test_chinese_calendar_weekend_not_in_statutory_set():
    cal = ChineseCalendar()
    sat = date(2024, 1, 6)
    assert sat not in cal.holidays
    assert not cal.is_business_day(sat)
    assert cal.is_holiday(sat)


def test_chinese_calendar_statutory_holiday():
    cal = CN_CALENDAR
    spring = date(2024, 2, 10)
    assert spring in cal.holidays
    assert not cal.is_business_day(spring)


def test_cn_calendar_business_days_2022():
    """Golden value from PriceLib test_time_utils."""
    start = date(2022, 1, 5)
    end = start + timedelta(days=365)
    assert end == date(2023, 1, 5)
    assert CN_CALENDAR.business_days_between(start, end) == 243


def test_schedule_monthly_knockout_golden():
    """Match PriceLib Schedule output for 1y snowball with 3m lock."""
    start = date(2022, 1, 5)
    end = start + timedelta(days=365)
    sched = Schedule(
        trade_calendar=CN_CALENDAR,
        start=start,
        end=end,
        freq="m",
        lock_term=3,
        convention=BusinessConvention.FOLLOWING,
        correction=MonthAdjustment.YES,
        endofmonthmodify=EndOfMonthModify.YES,
    )
    expected = [
        date(2022, 4, 6),
        date(2022, 5, 5),
        date(2022, 6, 6),
        date(2022, 7, 5),
        date(2022, 8, 5),
        date(2022, 9, 5),
        date(2022, 10, 10),
        date(2022, 11, 7),
        date(2022, 12, 5),
        date(2023, 1, 5),
    ]
    assert sched.date_schedule == expected
    assert sched.count_business_days(start) == [58, 76, 97, 118, 141, 162, 181, 201, 221, 243]
    assert sched.count_calendar_days(start) == [91, 120, 152, 181, 212, 243, 278, 306, 334, 365]


def test_schedule_holiday_boundary_following():
    """Observation on National Day week should roll following within month."""
    cal = Calendar(holidays={date(2024, 10, 1), date(2024, 10, 2), date(2024, 10, 3)})
    start = date(2024, 9, 1)
    end = date(2024, 10, 31)
    sched = Schedule(
        trade_calendar=cal,
        start=start,
        end=end,
        freq="m",
        lock_term=0,
        convention=BusinessConvention.FOLLOWING,
        correction=MonthAdjustment.YES,
        endofmonthmodify=EndOfMonthModify.NO,
    )
    assert all(cal.is_business_day(d) for d in sched.date_schedule)


def test_schedule_lock_term_skips_early_observations():
    start = date(2024, 1, 2)
    end = date(2024, 7, 2)
    full = Schedule(
        trade_calendar=CN_CALENDAR,
        start=start,
        end=end,
        freq="m",
        lock_term=0,
    )
    locked = Schedule(
        trade_calendar=CN_CALENDAR,
        start=start,
        end=end,
        freq="m",
        lock_term=2,
    )
    assert len(locked.date_schedule) == len(full.date_schedule) - 2


def test_calendar_advance_business_days():
    cal = CN_CALENDAR
    # Last business day before 2024 National Day golden week
    assert cal.advance(date(2024, 9, 30), timedelta(days=1)) == date(2024, 10, 8)


def test_validators_rate_curve_warnings():
    tenors = np.array([0.5, 1.0])
    rates = np.array([0.03, 0.04])
    report = validate_rate_curve(tenors, rates, max_tenor=2.0)
    assert report.passed
    assert any(i.level == "warning" for i in report.issues)


def test_validators_vol_surface_grid():
    times = np.array([0.25, 0.5])
    spots = np.array([90.0, 100.0, 110.0])
    vols = np.array([[0.2, 0.21, 0.22], [0.19, 0.2, 0.21]])
    report = validate_vol_surface(vols, spots=spots, times=times)
    assert report.passed


def test_validators_market_inputs_rejects_bad_spot():
    report = validate_market_inputs({"X": -1.0}, {"X": 0.2})
    assert not report.passed
