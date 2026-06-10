"""Numerical solvers adapted from PriceLib (Apache 2.0, Galaxy Technologies)."""

from __future__ import annotations

import numpy as np
from numba import njit, prange


def tdma(X: np.ndarray, d: np.ndarray) -> np.ndarray:
    """Solve tridiagonal system Xp = d via Thomas algorithm."""
    n = len(d)
    a = np.array(X[np.arange(n - 1) + 1, np.arange(n - 1)])[0]
    b = np.array(X[np.arange(n), np.arange(n)])[0]
    c = np.array(X[np.arange(n - 1), np.arange(n - 1) + 1])[0]
    w = np.zeros(n - 1, float)
    g = np.zeros(n, float)
    p = np.zeros(n, float)

    w[0] = c[0] / b[0]
    g[0] = d[0] / b[0]

    for i in range(1, n - 1):
        w[i] = c[i] / (b[i] - a[i - 1] * w[i - 1])
    for i in range(1, n):
        g[i] = (d[i] - a[i - 1] * g[i - 1]) / (b[i] - a[i - 1] * w[i - 1])
    p[n - 1] = g[n - 1]
    for i in range(n - 1, 0, -1):
        p[i - 1] = g[i - 1] - w[i - 1] * p[i]
    return p.reshape(n)


@njit(cache=True, fastmath=True)
def tdma_jit(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray) -> np.ndarray:
    """JIT-accelerated Thomas algorithm on LDU diagonal vectors."""
    n = len(d)
    b = b.copy()
    d = d.copy()
    for i in prange(1, n):
        m = a[i - 1] / b[i - 1]
        b[i] = b[i] - m * c[i - 1]
        d[i] = d[i] - m * d[i - 1]
    p = b
    p[-1] = d[-1] / b[-1]
    indices = np.arange(n - 2, -1, -1)
    for j in prange(n - 1):
        i = indices[j]
        p[i] = (d[i] - c[i] * p[i + 1]) / b[i]
    return p
