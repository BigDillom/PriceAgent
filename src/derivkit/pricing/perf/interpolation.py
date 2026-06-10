"""Interpolation helpers for PDE greek surfaces.

Adapted from PriceLib (Apache 2.0): pricelib/common/utilities/numerical.py
"""

from __future__ import annotations

import numpy as np
from scipy.interpolate import UnivariateSpline, interp1d


class LinearFlat(interp1d):
    """Linear interpolation with flat extrapolation at boundaries."""

    def __init__(self, x: np.ndarray, y: np.ndarray) -> None:
        super().__init__(x, y, kind="linear", bounds_error=False, fill_value=(y[0], y[-1]))


class CubicSplineFlat(UnivariateSpline):
    """Cubic spline with flat extrapolation (ext=3)."""

    def __init__(self, x: np.ndarray, y: np.ndarray) -> None:
        super().__init__(x, y, s=0, ext=3)
