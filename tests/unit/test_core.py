"""Unit tests for dk.core."""

import numpy as np
import pytest

from derivkit.core.conventions import discount_factor, parse_tenor, year_fraction
from derivkit.core.enums import Compounding, DayCount
from derivkit.core.observable import Observer, Quote
from derivkit.core.rng import get_seed, normal_random, set_seed


class TestConventions:
    def test_parse_tenor(self):
        assert parse_tenor("1y") == 1.0
        assert parse_tenor("3m") == pytest.approx(0.25)
        assert parse_tenor("6w") == pytest.approx(6 / 52)
        assert parse_tenor(0.5) == 0.5

    def test_year_fraction(self):
        from datetime import date

        yf = year_fraction(date(2024, 1, 1), date(2025, 1, 1), DayCount.ACT365)
        assert yf == pytest.approx(1.0, rel=0.01)

    def test_discount_factor(self):
        df = discount_factor(0.05, 1.0, Compounding.CONTINUOUS)
        assert df == pytest.approx(0.9512, rel=0.001)


class TestObservable:
    def test_quote_notify(self):
        updates = []

        class TestObserver(Observer):
            def update(self, observable, *args, **kwargs):
                updates.append(kwargs.get("value"))

        q = Quote(100.0)
        obs = TestObserver()
        q.attach(obs)
        q.value = 105.0
        assert updates == [105.0]


class TestRng:
    def test_determinism(self):
        set_seed(42)
        a = normal_random(100, seed=42)
        set_seed(42)
        b = normal_random(100, seed=42)
        np.testing.assert_array_equal(a, b)

    def test_set_seed(self):
        set_seed(123)
        assert get_seed() == 123
