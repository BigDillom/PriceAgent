"""Volatility models."""

from __future__ import annotations

import logging

import numpy as np

from derivkit.core.enums import VolType
from derivkit.core.interfaces import VolModel
from derivkit.core.observable import Observable

logger = logging.getLogger(__name__)


class ConstantVol(Observable, VolModel):
    """Constant implied volatility."""

    vol_type = VolType.CONSTANT

    def __init__(self, sigma: float, vol_id: str = "default") -> None:
        Observable.__init__(self)
        self.vol_id = vol_id
        self._sigma = float(sigma)

    @property
    def sigma(self) -> float:
        return self._sigma

    @sigma.setter
    def sigma(self, value: float) -> None:
        self._sigma = float(value)
        self.notify()

    def __call__(self, t: float, spot: float) -> float:
        return self._sigma

    def bump(self, amount: float) -> ConstantVol:
        return ConstantVol(self._sigma + amount, self.vol_id)


class LocalVolSurface(Observable, VolModel):
    """Local volatility surface sigma(t, S) via bilinear interpolation."""

    vol_type = VolType.LOCAL

    def __init__(
        self,
        times: np.ndarray,
        spots: np.ndarray,
        vols: np.ndarray,
        vol_id: str = "default",
    ) -> None:
        Observable.__init__(self)
        self.vol_id = vol_id
        self._times = np.asarray(times, dtype=float)
        self._spots = np.asarray(spots, dtype=float)
        self._vols = np.asarray(vols, dtype=float)

    def __call__(self, t: float, spot: float) -> float:
        t_idx = np.searchsorted(self._times, t)
        s_idx = np.searchsorted(self._spots, spot)
        t_idx = np.clip(t_idx, 0, len(self._times) - 1)
        s_idx = np.clip(s_idx, 0, len(self._spots) - 1)
        return float(self._vols[t_idx, s_idx])
