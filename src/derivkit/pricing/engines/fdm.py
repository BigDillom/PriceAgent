"""Finite difference (PDE) pricing engine using FdmGrid."""

from __future__ import annotations

import logging
import math

import numpy as np

from derivkit.core.enums import CallPut, EngineMethod, ExerciseType, FdmScheme
from derivkit.core.interfaces import PricingEngine, Product
from derivkit.data.market_env import MarketEnv
from derivkit.pricing.perf.fdm_grid import FdmGrid, FdmGridWithBound
from derivkit.pricing.products.vanilla import EuropeanVanilla

logger = logging.getLogger(__name__)

THETA_MAP = {
    FdmScheme.EXPLICIT: 0.0,
    FdmScheme.IMPLICIT: 1.0,
    FdmScheme.CRANK_NICOLSON: 0.5,
}


def _disc_factor(rate: float, t_from: float, t_to: float) -> float:
    """Discount factor from t_from to t_to under constant rate."""
    return math.exp(-rate * (t_to - t_from))


def _make_pde_coef_fn(env: MarketEnv, underlying_id: str, maturity: float, sigma: float):
    """Return PDE coefficient function (a, b, c) for BSM."""

    def fn_pde_coef(t: float, _s_vec: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        r_t = env.rate(t)
        q_t = env.div_yield(underlying_id)
        vol = env.vol(underlying_id, t) if t != maturity else sigma
        a = np.full_like(_s_vec, vol**2, dtype=float)
        b = np.full_like(_s_vec, r_t - q_t, dtype=float)
        c = np.full_like(_s_vec, r_t, dtype=float)
        return a, b, c

    return fn_pde_coef


class FdmEngine(PricingEngine):
    """Crank-Nicolson FDM for European/American vanilla options."""

    method = EngineMethod.FDM

    def __init__(
        self,
        n_s: int = 200,
        n_smax: float = 4.0,
        scheme: str | FdmScheme = "crank_nicolson",
        t_step_per_year: int = 243,
    ) -> None:
        self.n_s = n_s
        self.n_smax = n_smax
        self.t_step_per_year = t_step_per_year
        if isinstance(scheme, str):
            scheme = FdmScheme(scheme)
        self.fdm_theta = THETA_MAP.get(scheme, 0.5)

    def calc_present_value(
        self,
        product: Product,
        env: MarketEnv,
        t: float | None = None,
        spot: float | None = None,
    ) -> float:
        if not isinstance(product, EuropeanVanilla):
            raise TypeError(f"FdmEngine supports EuropeanVanilla, got {type(product)}")

        s0 = spot if spot is not None else env.spot(product.underlying_id)
        k = product.strike
        tau = product.maturity
        if tau <= 0:
            return float(product.payoff(s0))

        r = env.rate(tau)
        q = env.div_yield(product.underlying_id)
        sigma = env.vol(product.underlying_id, tau)
        smax = s0 * self.n_smax
        sign = 1 if product.call_put == CallPut.CALL else -1

        fn_pde_coef = _make_pde_coef_fn(env, product.underlying_id, tau, sigma)

        if product.call_put == CallPut.CALL:
            fn_bound = [
                lambda u: 0.0,
                lambda u: smax * _disc_factor(q, u, tau) - k * _disc_factor(r, u, tau),
            ]
        else:
            fn_bound = [
                lambda u: k * _disc_factor(r, u, tau),
                lambda u: 0.0,
            ]

        if product.exercise == ExerciseType.EUROPEAN:
            fdm = FdmGridWithBound(
                smax=smax,
                t_step_per_year=self.t_step_per_year,
                s_step=self.n_s,
                fn_pde_coef=fn_pde_coef,
                fdm_theta=self.fdm_theta,
            )
            fdm.set_boundary_condition(fn_bound)
            yv = np.maximum(sign * (fdm.s_vec - k), 0.0)
            yv = fdm.evolve_with_interval(start=tau, end=0.0, yv=yv)
        else:
            fdm = FdmGrid(
                smax=smax,
                maturity=tau,
                t_step_per_year=self.t_step_per_year,
                s_step=self.n_s,
                fn_pde_coef=fn_pde_coef,
                fdm_theta=self.fdm_theta,
            )
            fdm.set_boundary_condition(fn_bound)
            t_vec = fdm.tv
            fdm.v_grid[0, :] = [fn_bound[0](t) for t in t_vec]
            fdm.v_grid[-1, :] = [fn_bound[1](t) for t in t_vec]
            yv = np.maximum(sign * (fdm.s_vec - k), 0.0)
            intrinsic = sign * (fdm.s_vec - k)
            t_step = len(t_vec) - 1
            for j in range(t_step - 1, -1, -1):
                yv = fdm.evolve(j, yv, fdm.dt)
                yv = np.maximum(yv, intrinsic)

        return float(fdm.functionize(yv, kind="cubic")(s0))
