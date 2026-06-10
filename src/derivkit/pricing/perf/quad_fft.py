"""FFT-accelerated quadrature utilities for log-normal convolution.

Adapted from PriceLib (Apache 2.0):
pricelib/common/pricing_engine_base/quad_engine_base.py
"""

from __future__ import annotations

import numba as nb
import numpy as np
from scipy.stats import norm

from derivkit.core.enums import QuadMethod


@nb.njit(cache=True, fastmath=True)
def get_quad_vector_jit(n_points: int, is_simpson: bool) -> tuple[np.ndarray, int]:
    """JIT quadrature weights (is_simpson=True for Simpson, else trapezoid)."""
    quad_vector = np.ones(n_points)
    if is_simpson:
        quad_vector[1::2] *= 4
        quad_vector[0::2] *= 2
        quad_vector[0] = quad_vector[-1] = 1
        return quad_vector, 3
    quad_vector[1:-1] *= 2
    return quad_vector, 2


@nb.njit(cache=True, fastmath=True, parallel=True)
def step_backward_jit(
    x: np.ndarray,
    y: np.ndarray,
    v: np.ndarray,
    t: float,
    r: float,
    q: float,
    vol: float,
    quad_vector: np.ndarray,
    quad_index: int,
) -> np.ndarray:
    """Direct quadrature backward step (non-FFT), JIT-accelerated."""
    upper_barrier = np.max(y)
    lower_barrier = np.min(y)
    tvar = 0.5 * vol * vol * t
    rho = 1.0 / (2.0 * np.sqrt(np.pi * tvar) * y)
    log_ratio = np.log(y / x.reshape(-1, 1))
    rho = rho * np.exp(-1.0 / (4.0 * tvar) * (log_ratio - (r - q) * t + tvar) ** 2)
    target_v = np.dot(quad_vector, (rho * v).T) * (upper_barrier - lower_barrier)
    target_v /= (y.shape[0] - 1) * quad_index
    target_v *= np.exp(-r * t)
    return target_v


def get_quad_vector(n_points: int, quad_method: QuadMethod) -> tuple[np.ndarray, int]:
    """Simpson or trapezoid quadrature weights."""
    quad_vector = np.ones(n_points)
    if quad_method == QuadMethod.TRAPEZOID:
        quad_vector[1:-1] *= 2
        return quad_vector, 2
    quad_vector[1::2] *= 4
    quad_vector[0::2] *= 2
    quad_vector[0] = quad_vector[-1] = 1
    return quad_vector, 3


def fft_convolve(
    v: np.ndarray,
    pdf: np.ndarray,
    t: float,
    r: float,
    ln_ds: float,
    quad_vector: np.ndarray,
    quad_index: int,
) -> np.ndarray:
    """FFT convolution for uniform log-price grid backward step (numpy FFT)."""
    len_v = v.size
    len_pdf = pdf.size
    v_pad = np.hstack((v * quad_vector, np.zeros(len_pdf - len_v)))
    fft_res = np.fft.ifft(np.fft.fft(v_pad) * np.fft.fft(pdf)).real
    return fft_res[len_v - 1 :] / quad_index * ln_ds * np.exp(-r * t)


def transition_pdf(
    x_vec: np.ndarray,
    y_vec: np.ndarray,
    t: float,
    r: float,
    q: float,
    vol: float,
) -> np.ndarray:
    """Log-price transition density for FFT convolution (x → y)."""
    quad_vec = np.concatenate(((x_vec - x_vec[-1] + y_vec[0])[:-1], y_vec))
    quad_vec -= x_vec[0]
    mu = (r - q - 0.5 * vol**2) * t
    sig = vol * np.sqrt(t)
    return np.flip(norm.pdf(quad_vec, mu, sig))


def init_log_grid(
    spot: float,
    vol: float,
    tau: float,
    n_points: int,
    barrier_low: float | None = None,
    barrier_high: float | None = None,
) -> tuple[np.ndarray, float, np.ndarray]:
    """Uniform log-price grid for FFT quadrature."""
    c = np.exp(10 * vol * np.sqrt(tau) + 0.5 * vol**2 * tau)
    boundary = np.array([spot / c, spot * c])
    if barrier_low is not None:
        boundary[0] = max(barrier_low, boundary[0])
    if barrier_high is not None:
        boundary[1] = min(barrier_high, boundary[1])
    ln_boundary = np.log(boundary)
    ln_s_vec = np.linspace(ln_boundary[0], ln_boundary[1], n_points)
    ln_ds = ln_s_vec[1] - ln_s_vec[0]
    return ln_s_vec, ln_ds, ln_boundary
