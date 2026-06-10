"""Shared GBM path simulation for Monte Carlo engines."""

from __future__ import annotations

import numpy as np

from derivkit.core.enums import RandsMethod
from derivkit.core.rng import get_seed, normal_random
from derivkit.pricing.perf.mc_kernels import evolve_bs_log


def simulate_gbm_paths(
    s0: float,
    r: float,
    q: float,
    sigma: float,
    tau: float,
    n_steps: int,
    n_paths: int,
    seed: int | None = None,
    rands_method: RandsMethod = RandsMethod.PSEUDO,
    antithetic: bool = True,
) -> np.ndarray:
    """Simulate spot paths including t=0; shape (n_paths, n_steps + 1)."""
    if n_steps <= 0 or tau <= 0:
        return np.full((max(n_paths, 1), 1), s0)

    dt = tau / n_steps
    drift = (r - q - 0.5 * sigma**2) * dt
    vol = sigma * np.sqrt(dt)
    effective_seed = seed if seed is not None else get_seed()

    if antithetic:
        n_half = max(n_paths // 2, 1)
        z = normal_random((n_half, n_steps), effective_seed, rands_method)
        z_all = np.vstack([z, -z])
    else:
        z_all = normal_random((n_paths, n_steps), effective_seed, rands_method)

    return evolve_bs_log(s0, drift, vol, z_all)


def simulate_gbm_paths_from_shocks(
    s0: float,
    r: float,
    q: float,
    sigma: float,
    dt: float,
    z: np.ndarray,
) -> np.ndarray:
    """Build paths from pre-generated standard normal shocks; shape (n_paths, n_steps + 1)."""
    drift = (r - q - 0.5 * sigma**2) * dt
    vol = sigma * np.sqrt(dt)
    return evolve_bs_log(s0, drift, vol, z)
