"""FFT quadrature engine base for path-dependent products."""

from __future__ import annotations

import numpy as np

from derivkit.core.enums import QuadMethod
from derivkit.pricing.perf.quad_fft import (
    fft_convolve,
    get_quad_vector_jit,
    init_log_grid,
    transition_pdf,
)


class QuadFftBase:
    """Shared FFT backward-step machinery (constant r, q, vol)."""

    def __init__(
        self,
        quad_method: QuadMethod = QuadMethod.SIMPSON,
        n_points: int = 1301,
    ) -> None:
        self.n_points = n_points if n_points % 2 == 1 else n_points + 1
        self.quad_method = quad_method
        self.r: float = 0.0
        self.q: float = 0.0
        self.vol: float = 0.0
        self.ln_s_vec: np.ndarray | None = None
        self.ln_ds: float = 0.0

    def set_quad_params(self, r: float, q: float, vol: float) -> None:
        self.r = r
        self.q = q
        self.vol = vol

    def init_grid(
        self,
        spot: float,
        vol: float,
        tau: float,
        barrier_low: float | None = None,
        barrier_high: float | None = None,
    ) -> None:
        self.ln_s_vec, self.ln_ds, _ = init_log_grid(
            spot, vol, tau, self.n_points, barrier_low, barrier_high
        )

    def fft_step_backward(
        self,
        x: np.ndarray,
        y: np.ndarray,
        v: np.ndarray,
        t: float,
    ) -> np.ndarray:
        is_simpson = self.quad_method.value == "simpson"
        quad_vector, quad_index = get_quad_vector_jit(y.size, is_simpson)
        pdf = transition_pdf(x, y, t, self.r, self.q, self.vol)
        return fft_convolve(v, pdf, t, self.r, self.ln_ds, quad_vector, quad_index)
