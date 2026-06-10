"""Performance utilities: numba kernels, parallel, FFT, numerical solvers."""

from derivkit.pricing.perf.fdm_grid import FdmGrid, FdmGridWithBound
from derivkit.pricing.perf.mc_kernels import evolve_bs_log, simulate_gbm_terminal
from derivkit.pricing.perf.numerical import tdma, tdma_jit
from derivkit.pricing.perf.pde_kernels import fdm_evolve_step
from derivkit.pricing.perf.quad_fft import get_quad_vector_jit, step_backward_jit

__all__ = [
    "tdma",
    "tdma_jit",
    "FdmGrid",
    "FdmGridWithBound",
    "evolve_bs_log",
    "simulate_gbm_terminal",
    "fdm_evolve_step",
    "get_quad_vector_jit",
    "step_backward_jit",
]
