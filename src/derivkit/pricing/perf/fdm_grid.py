"""PDE finite-difference grids (Crank-Nicolson).

Adapted from PriceLib (Apache 2.0): pricelib/common/pricing_engine_base/pde_engine_base.py
"""

from __future__ import annotations

from typing import Callable

import numpy as np
from scipy import sparse

from derivkit.pricing.perf.interpolation import CubicSplineFlat, LinearFlat
from derivkit.pricing.perf.pde_kernels import fdm_evolve_step

PdeCoefFn = Callable[[float, np.ndarray], tuple[np.ndarray, np.ndarray, np.ndarray]]
BoundFn = Callable[[float], float]


class FdmGrid:
    """FDM grid on [0, smax] with pre-built time mesh (American / autocallable)."""

    def __init__(
        self,
        smax: float,
        maturity: float,
        t_step_per_year: int = 243,
        s_step: int = 400,
        fn_pde_coef: PdeCoefFn | None = None,
        fdm_theta: float = 0.5,
        smin: float = 0.0,
    ) -> None:
        self._theta = fdm_theta
        self.t_step_per_year = t_step_per_year
        self.s_min = smin
        self.s_max = smax
        self.s_vec = np.linspace(self.s_min, self.s_max, int(max(s_step, 50)) + 1)[1:-1]
        self.ds = (self.s_vec[-1] - self.s_vec[0]) / max(self.s_vec.size - 1, 1)
        num = round(maturity * self.t_step_per_year)
        self.tv = np.linspace(0, maturity, num + 1)
        self.dt = (self.tv[-1] - self.tv[0]) / max(self.tv.size - 1, 1) if self.tv.size > 1 else 0.0
        self.i_vec = None if self.ds == 0 else np.round(self.s_vec / self.ds).astype(int)
        self.fn_pde_coef = fn_pde_coef
        self.eye = sparse.eye(self.s_vec.size)
        self.v_grid = np.zeros((self.s_vec.size + 2, self.tv.size))
        self.lower = self.diag = self.upper = None
        self.M1 = self.M2 = None
        self.fn_bound: list[BoundFn] | None = None

    def _set_matrix(self, a: np.ndarray, b: np.ndarray, c: np.ndarray, dt: float) -> None:
        diffusion_square = a * self.i_vec**2
        drift = b * self.i_vec
        self.lower = 0.5 * (diffusion_square - drift)
        self.diag = -diffusion_square - c
        self.upper = 0.5 * (diffusion_square + drift)
        A = sparse.diags((self.lower[1:], self.diag, self.upper[:-1]), (-1, 0, 1), format="csc") * dt
        self.M1 = self.eye - self._theta * A
        self.M2 = self.eye + (1 - self._theta) * A

    def _set_vector(self, j: int, yv: np.ndarray, dt: float) -> np.ndarray:
        v_vec = self.M2.dot(yv)
        if self.fn_bound is not None:
            v_vec[0] += (
                self._theta * self.fn_bound[0](self.tv[j])
                + (1 - self._theta) * self.fn_bound[0](self.tv[j - 1])
            ) * self.lower[0] * dt
            v_vec[-1] += (
                self._theta * self.fn_bound[1](self.tv[j])
                + (1 - self._theta) * self.fn_bound[1](self.tv[j - 1])
            ) * self.upper[-1] * dt
        else:
            v_vec[0] += (
                self._theta * self.v_grid[0, j] + (1 - self._theta) * self.v_grid[0, j - 1]
            ) * self.lower[0] * dt
            v_vec[-1] += (
                self._theta * self.v_grid[-1, j] + (1 - self._theta) * self.v_grid[-1, j - 1]
            ) * self.upper[-1] * dt
        return np.asarray(v_vec)

    def evolve(self, j: int, yv: np.ndarray, dt: float) -> np.ndarray:
        if self.fn_pde_coef is None or self.i_vec is None:
            raise ValueError("PDE coefficient function not set")
        a, b, c = self.fn_pde_coef(self.tv[j], self.s_vec)
        if self.fn_bound is not None:
            bound_lo_j = self.fn_bound[0](self.tv[j])
            bound_lo_jm1 = self.fn_bound[0](self.tv[j - 1])
            bound_hi_j = self.fn_bound[1](self.tv[j])
            bound_hi_jm1 = self.fn_bound[1](self.tv[j - 1])
        else:
            bound_lo_j = self.v_grid[0, j]
            bound_lo_jm1 = self.v_grid[0, j - 1]
            bound_hi_j = self.v_grid[-1, j]
            bound_hi_jm1 = self.v_grid[-1, j - 1]
        return fdm_evolve_step(
            self.i_vec, a, b, c, dt, self._theta, yv,
            bound_lo_j, bound_lo_jm1, bound_hi_j, bound_hi_jm1,
        )

    def functionize(self, yv: np.ndarray, kind: str = "linear"):
        if kind == "linear":
            return LinearFlat(self.s_vec, yv)
        return CubicSplineFlat(self.s_vec, yv)

    def set_boundary_condition(self, fn_bound: list[BoundFn]) -> None:
        self.fn_bound = fn_bound


class FdmGridWithBound(FdmGrid):
    """European vanilla grid: boundary via fn_bound, time mesh built in evolve_with_interval."""

    def __init__(
        self,
        smax: float,
        t_step_per_year: int = 243,
        s_step: int = 400,
        fn_pde_coef: PdeCoefFn | None = None,
        fdm_theta: float = 0.5,
        smin: float = 0.0,
    ) -> None:
        self._theta = fdm_theta
        self.t_step_per_year = t_step_per_year
        self.s_min = smin
        self.s_max = smax
        self.s_vec = np.linspace(self.s_min, self.s_max, int(max(s_step, 50)) + 1)[1:-1]
        self.ds = (self.s_vec[-1] - self.s_vec[0]) / max(self.s_vec.size - 1, 1)
        self.tv = np.array([0.0])
        self.dt = 0.0
        self.i_vec = None if self.ds == 0 else np.round(self.s_vec / self.ds).astype(int)
        self.fn_pde_coef = fn_pde_coef
        self.eye = sparse.eye(self.s_vec.size)
        self.v_grid = np.zeros((self.s_vec.size + 2, 1))
        self.lower = self.diag = self.upper = None
        self.M1 = self.M2 = None
        self.fn_bound: list[BoundFn] | None = None

    def evolve_with_interval(self, start: float, end: float, yv: np.ndarray) -> np.ndarray:
        num = max(round(abs(start - end) * self.t_step_per_year), 1)
        self.tv = np.linspace(start, end, num + 1)
        self.dt = (self.tv[-1] - self.tv[0]) / max(self.tv.size - 1, 1)
        step_dt = -self.dt
        for j in range(1, len(self.tv)):
            yv = self.evolve(j, yv, step_dt)
        return yv
