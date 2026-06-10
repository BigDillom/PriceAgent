"""Numba JIT kernels for Crank-Nicolson FDM backward steps.

Adapted from PriceLib (Apache 2.0): pricelib/common/pricing_engine_base/pde_engine_base.py
"""

from __future__ import annotations

import numpy as np
from numba import njit

from derivkit.pricing.perf.numerical import tdma_jit


@njit(cache=True, fastmath=True)
def fdm_tridiag_matvec(
    lower: np.ndarray,
    diag: np.ndarray,
    upper: np.ndarray,
    x: np.ndarray,
) -> np.ndarray:
    """Multiply tridiagonal matrix (lower, diag, upper) by vector x."""
    n = x.size
    out = np.empty(n, dtype=np.float64)
    out[0] = diag[0] * x[0] + upper[0] * x[1]
    for i in range(1, n - 1):
        out[i] = lower[i - 1] * x[i - 1] + diag[i] * x[i] + upper[i] * x[i + 1]
    out[n - 1] = lower[n - 2] * x[n - 2] + diag[n - 1] * x[n - 1]
    return out


@njit(cache=True, fastmath=True)
def fdm_evolve_step(
    i_vec: np.ndarray,
    a: np.ndarray,
    b: np.ndarray,
    c: np.ndarray,
    dt: float,
    theta: float,
    yv: np.ndarray,
    bound_lo_j: float,
    bound_lo_jm1: float,
    bound_hi_j: float,
    bound_hi_jm1: float,
) -> np.ndarray:
    """One backward CN step: build M2·yv + boundary correction, solve M1·result = rhs."""
    diffusion_square = a * i_vec * i_vec
    drift_coef = b * i_vec
    lower_coef = 0.5 * (diffusion_square - drift_coef)
    diag_coef = -diffusion_square - c
    upper_coef = 0.5 * (diffusion_square + drift_coef)

    one_m_theta = 1.0 - theta
    m2_lower = one_m_theta * lower_coef[1:] * dt
    m2_diag = 1.0 + one_m_theta * diag_coef * dt
    m2_upper = one_m_theta * upper_coef[:-1] * dt
    v_vec = fdm_tridiag_matvec(m2_lower, m2_diag, m2_upper, yv)

    v_vec[0] += (theta * bound_lo_j + one_m_theta * bound_lo_jm1) * lower_coef[0] * dt
    v_vec[-1] += (theta * bound_hi_j + one_m_theta * bound_hi_jm1) * upper_coef[-1] * dt

    m1_lower = -theta * lower_coef[1:] * dt
    m1_diag = 1.0 - theta * diag_coef * dt
    m1_upper = -theta * upper_coef[:-1] * dt
    return tdma_jit(m1_lower, m1_diag.copy(), m1_upper, v_vec)
