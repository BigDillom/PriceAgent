"""Numba JIT kernels for GBM Monte Carlo path simulation.

Adapted from PriceLib (Apache 2.0): pricelib/common/processes/bsm_process.py (evolve_bs)
Uses log-normal exact stepping (equivalent to Euler in the limit).
"""

from __future__ import annotations

import numpy as np
from numba import njit, prange


@njit(cache=True, fastmath=True, parallel=True)
def evolve_bs_log(
    s0: float,
    drift_dt: float,
    vol_sqrt_dt: float,
    z: np.ndarray,
) -> np.ndarray:
    """Evolve GBM paths from standard normal shocks; shape (n_paths, n_steps + 1)."""
    n_paths, n_steps = z.shape
    out = np.empty((n_paths, n_steps + 1), dtype=np.float64)
    for i in prange(n_paths):
        out[i, 0] = s0
        log_s = 0.0
        for j in range(n_steps):
            log_s += drift_dt + vol_sqrt_dt * z[i, j]
            out[i, j + 1] = s0 * np.exp(log_s)
    return out


@njit(cache=True, fastmath=True, parallel=True)
def simulate_gbm_terminal(
    s0: float,
    drift_tau: float,
    vol_sqrt_tau: float,
    z: np.ndarray,
) -> np.ndarray:
    """Terminal spot from shocks z; shape (n_paths,)."""
    n = z.size
    out = np.empty(n, dtype=np.float64)
    for i in prange(n):
        out[i] = s0 * np.exp(drift_tau + vol_sqrt_tau * z[i])
    return out
