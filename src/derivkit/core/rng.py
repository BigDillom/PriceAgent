"""Unified random number generation with reproducible seeds."""

from __future__ import annotations

import numpy as np
from numpy.random import Generator, SeedSequence
from scipy.stats import qmc

from derivkit.core.enums import RandsMethod

_global_seed: int | None = None
_generators: dict[tuple[int, RandsMethod], Generator] = {}


def set_seed(seed: int) -> None:
    """Set global RNG seed for reproducibility."""
    global _global_seed
    _global_seed = seed
    _generators.clear()


def get_seed() -> int:
    """Return current global seed (defaults to 0)."""
    return 0 if _global_seed is None else _global_seed


def get_generator(seed: int | None = None, method: RandsMethod = RandsMethod.PSEUDO) -> Generator:
    """Return a seeded numpy Generator."""
    effective_seed = get_seed() if seed is None else seed
    key = (effective_seed, method)
    if key not in _generators:
        if method == RandsMethod.PSEUDO:
            _generators[key] = np.random.default_rng(SeedSequence(effective_seed))
        elif method == RandsMethod.SOBOL:
            _generators[key] = np.random.default_rng(SeedSequence(effective_seed))
        elif method == RandsMethod.HALTON:
            _generators[key] = np.random.default_rng(SeedSequence(effective_seed))
        else:
            raise ValueError(f"Unknown random method: {method}")
    return _generators[key]


def normal_random(
    size: int | tuple[int, ...],
    seed: int | None = None,
    method: RandsMethod = RandsMethod.PSEUDO,
) -> np.ndarray:
    """Generate standard normal random variates."""
    if method == RandsMethod.SOBOL:
        effective_seed = get_seed() if seed is None else seed
        sampler = qmc.Sobol(d=1, scramble=True, seed=effective_seed)
        n = int(np.prod(size)) if isinstance(size, tuple) else size
        samples = sampler.random(n)
        from scipy.stats import norm

        return norm.ppf(np.clip(samples.flatten(), 1e-10, 1 - 1e-10)).reshape(size)

    if method == RandsMethod.HALTON:
        effective_seed = get_seed() if seed is None else seed
        sampler = qmc.Halton(d=1, scramble=True, seed=effective_seed)
        n = int(np.prod(size)) if isinstance(size, tuple) else size
        samples = sampler.random(n)
        from scipy.stats import norm

        return norm.ppf(np.clip(samples.flatten(), 1e-10, 1 - 1e-10)).reshape(size)

    return get_generator(seed, method).normal(0.0, 1.0, size)
