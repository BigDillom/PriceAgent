"""PDE engine for standard snowball (autocallable) products.

Adapted from PriceLib (Apache 2.0):
pricelib/pricing_engines/fdm_engines/fdm_autocallable_engine.py
"""

from __future__ import annotations

import logging
from datetime import date

import numpy as np

from derivkit.core.enums import EngineMethod, FdmScheme
from derivkit.core.interfaces import PricingEngine, Product
from derivkit.data.market_env import MarketEnv
from derivkit.pricing.engines.fdm import THETA_MAP, _make_pde_coef_fn
from derivkit.pricing.perf.fdm_grid import FdmGrid
from derivkit.pricing.products.snowball import StandardSnowball

logger = logging.getLogger(__name__)


def _disc_factor(rate: float, t_from: float, t_to: float | np.ndarray) -> float | np.ndarray:
    """Discount factor from t_from to t_to under constant rate."""
    return np.exp(-rate * (np.asarray(t_to, dtype=float) - t_from))


class FdmSnowballEngine(PricingEngine):
    """Crank-Nicolson FDM for standard snowball with knock-in/knock-out grids."""

    method = EngineMethod.FDM

    def __init__(
        self,
        s_step: int = 400,
        n_smax: float = 2.0,
        scheme: str | FdmScheme = "crank_nicolson",
        t_step_per_year: int = 243,
        european_knock_in: bool = False,
        trigger: bool = False,
    ) -> None:
        self.s_step = max(s_step, 50)
        self.n_smax = n_smax
        self.t_step_per_year = t_step_per_year
        self.european_knock_in = european_knock_in
        self.trigger = trigger
        if isinstance(scheme, str):
            scheme = FdmScheme(scheme)
        self.fdm_theta = THETA_MAP.get(scheme, 0.5)

        self.prod: StandardSnowball | None = None
        self.out_dates: np.ndarray | None = None
        self.pay_dates: np.ndarray | None = None
        self.diff_obs_pay_dates: np.ndarray | None = None
        self.smax: float | None = None
        self.t_step: int = 0
        self.dt: float = 0.0
        self.j_vec: np.ndarray | None = None
        self.fd_not_in: FdmGrid | None = None
        self.fd_knockin: FdmGrid | None = None
        self.next_paydate: np.ndarray | None = None
        self.next_barrier_in: float = 0.0
        self.reversed_barrier_in: np.ndarray | None = None
        self.next_barrier_out: float = 0.0
        self.reversed_barrier_out: np.ndarray | None = None
        self.in_idx: int = 0
        self.out_idxs: np.ndarray | None = None
        self.next_coupon_out: float = 0.0
        self.reversed_coupon_out: np.ndarray | None = None
        self.coupon_outs: np.ndarray | None = None
        self.itm: np.ndarray | None = None
        self.next_diff_obspaydate: np.ndarray | None = None
        self._rate: float = 0.0
        self._div: float = 0.0
        self.knocked_in: bool = False

    def calc_present_value(
        self,
        product: Product,
        env: MarketEnv,
        t: float | None = None,
        spot: float | None = None,
    ) -> float:
        if not isinstance(product, StandardSnowball):
            raise TypeError(f"FdmSnowballEngine supports StandardSnowball, got {type(product)}")

        self.prod = product
        self.knocked_in = bool(getattr(product, "knocked_in", False))
        spot = spot if spot is not None else env.spot(product.underlying_id)
        maturity = product.maturity
        val_date = env.valuation_date

        self._rate = env.rate(maturity)
        self._div = env.div_yield(product.underlying_id)
        sigma = env.vol(product.underlying_id, maturity)

        maturity_bdays = maturity
        self.t_step = max(round(product.t_step_per_year * maturity_bdays), 0)
        self.dt = 0.0 if self.t_step == 0 else maturity_bdays / self.t_step
        self.j_vec = np.linspace(0, self.t_step, self.t_step + 1)

        obs_steps = self._obs_step_indices(val_date, product, self.t_step, maturity)
        if obs_steps[-1] != self.t_step:
            obs_steps = np.append(obs_steps, self.t_step)
        self.pay_dates = obs_steps.astype(float) * (maturity / max(self.t_step, 1))
        self.diff_obs_pay_dates = np.zeros(len(self.pay_dates), dtype=float)

        fn_pde_coef = _make_pde_coef_fn(env, product.underlying_id, maturity, sigma)

        if self.t_step == 0:
            self.smax = spot
            smin = spot
        else:
            smin = 0.0
            self.smax = self.n_smax * product.s0

        self.fd_not_in = FdmGrid(
            smax=self.smax,
            maturity=maturity_bdays,
            t_step_per_year=product.t_step_per_year,
            s_step=self.s_step,
            fn_pde_coef=fn_pde_coef,
            fdm_theta=self.fdm_theta,
            smin=smin,
        )
        self.fd_knockin = FdmGrid(
            smax=self.smax,
            maturity=maturity_bdays,
            t_step_per_year=product.t_step_per_year,
            s_step=self.s_step,
            fn_pde_coef=fn_pde_coef,
            fdm_theta=self.fdm_theta,
            smin=smin,
        )

        out_dates = np.round(np.flip(obs_steps)).astype(int)
        self.out_dates = out_dates

        self._init_terminal_condition(self.fd_not_in.s_vec, maturity)

        if self.t_step == 0:
            grid = self.fd_knockin if self.knocked_in else self.fd_not_in
            return float(grid.v_grid[1, 0])

        self._init_boundary_condition(self.smax, maturity)
        self._backward_induction()

        grid = self.fd_knockin if self.knocked_in else self.fd_not_in
        return float(grid.functionize(grid.v_grid[1:-1, 0], kind="cubic")(spot))

    def _obs_step_indices(
        self, val_date: date, product: StandardSnowball, t_step: int, maturity: float
    ) -> np.ndarray:
        dt = maturity / t_step if t_step > 0 else maturity
        indices: list[int] = []
        for obs in product.obs_dates:
            days = (obs - val_date).days
            if days < 0:
                continue
            t_years = days / product.annual_days
            idx = int(round(t_years / dt)) if dt > 0 else t_step
            idx = min(max(idx, 1), t_step)
            indices.append(idx)
        if not indices:
            indices = [t_step]
        return np.array(sorted(set(indices)), dtype=int)

    def _init_boundary_condition(self, smax: float, maturity: float) -> None:
        assert self.prod is not None and self.fd_not_in is not None and self.fd_knockin is not None
        prod = self.prod
        t_vec = self.dt * self.j_vec
        interest_maturity_discount_factor = _disc_factor(self._rate, maturity, t_vec)

        self.fd_not_in.v_grid[0, :] = self.fd_knockin.v_grid[0, :] = (
            prod.margin_lvl * prod.s0 - prod.strike_upper + prod.strike_lower
        ) * interest_maturity_discount_factor

        assert self.out_dates is not None and self.pay_dates is not None
        self.next_paydate = self.pay_dates.repeat(
            np.diff(np.append(np.zeros((1,)), self.out_dates[::-1])).astype(int)
        )
        self.next_paydate = np.append(self.pay_dates[0], self.next_paydate)

        coupon_t = 1 if self.trigger else self.next_paydate
        interest_next_paydate_discount_factor = _disc_factor(self._rate, self.next_paydate, t_vec)
        div_next_paydate_discount_factor = _disc_factor(self._div, self.next_paydate, t_vec)
        v_smax = (
            smax * div_next_paydate_discount_factor
            - prod.strike_call * interest_next_paydate_discount_factor
        ) * prod.parti_out + (
            prod.margin_lvl + self.coupon_outs * coupon_t
        ) * prod.s0 * interest_next_paydate_discount_factor
        s_idx = self.fd_not_in.v_grid.shape[0] - 1
        self.fd_knockin.v_grid[s_idx, :] = self.fd_not_in.v_grid[s_idx, :] = v_smax

    def _init_terminal_condition(self, s_vec: np.ndarray, maturity: float) -> None:
        assert self.prod is not None and self.fd_not_in is not None and self.fd_knockin is not None
        prod = self.prod
        n_obs = len(self.out_dates) if self.out_dates is not None else len(prod._barrier_out)

        barrier_in = prod._barrier_in[-n_obs:].copy()
        barrier_out = prod._barrier_out[-n_obs:].copy()
        coupon_out = prod._coupon_out[-n_obs:].copy()

        if barrier_in.size > 1 and not np.allclose(barrier_in, barrier_in[0]):
            self._barrier_in = barrier_in
            self.next_barrier_in = float(self._barrier_in[-1])
            self.reversed_barrier_in = np.flip(self._barrier_in)
        else:
            self.reversed_barrier_in = None
            self.next_barrier_in = float(barrier_in[-1])

        if barrier_out.size > 1 and not np.allclose(barrier_out, barrier_out[0]):
            self._barrier_out = barrier_out
            self.next_barrier_out = float(self._barrier_out[-1])
            self.reversed_barrier_out = np.flip(self._barrier_out)
        else:
            self.reversed_barrier_out = None
            self.next_barrier_out = float(barrier_out[-1])

        if coupon_out.size > 1 and not np.allclose(coupon_out, coupon_out[0]):
            self._coupon_out = coupon_out
            self.next_coupon_out = float(self._coupon_out[-1])
            self.reversed_coupon_out = np.flip(self._coupon_out)
            coupon_outs = np.array(self._coupon_out).repeat(
                np.diff(np.append(np.zeros((1,)), self.out_dates[::-1])).astype(int)
            )
            self.coupon_outs = np.append(self._coupon_out[0], coupon_outs)
        else:
            self.reversed_coupon_out = None
            self.next_coupon_out = float(coupon_out[-1])
            self.coupon_outs = np.full(self.t_step + 1, self.next_coupon_out)

        if self.next_barrier_in > 0 and s_vec[0] < self.next_barrier_in:
            self.in_idx = 1 + int(np.where(s_vec <= self.next_barrier_in)[0][-1])
        else:
            self.in_idx = 0

        self.out_idxs = 1 + np.array(np.where(s_vec >= self.next_barrier_out)[0])
        self.itm = np.where(
            s_vec - prod.strike_call > 0, (s_vec - prod.strike_call) * prod.parti_out, 0.0
        )

        assert self.pay_dates is not None
        coupon_t = 1 if self.trigger else self.pay_dates[-1]

        self.fd_knockin.v_grid[1:-1, self.t_step] = np.where(
            s_vec < self.next_barrier_out,
            np.minimum(
                np.where(s_vec <= prod.strike_lower, prod.strike_lower, s_vec) - prod.strike_upper,
                0,
            )
            + prod.s0 * prod.margin_lvl,
            np.where(
                s_vec > prod.strike_call,
                (s_vec - prod.strike_call) * prod.parti_out
                + (prod.margin_lvl + self.next_coupon_out * coupon_t) * prod.s0,
                (prod.margin_lvl + self.next_coupon_out * coupon_t) * prod.s0,
            ),
        )

        self.fd_not_in.v_grid[1:-1, self.t_step] = np.where(
            s_vec <= self.next_barrier_in,
            np.where(s_vec <= prod.strike_lower, prod.strike_lower, s_vec)
            - prod.strike_upper
            + prod.s0 * prod.margin_lvl,
            np.where(
                s_vec > prod.strike_call,
                (s_vec - prod.strike_call) * prod.parti_out
                + (prod.margin_lvl + self.next_coupon_out * coupon_t) * prod.s0,
                np.where(
                    s_vec >= self.next_barrier_out,
                    (prod.margin_lvl + self.next_coupon_out * coupon_t) * prod.s0,
                    (prod.margin_lvl + prod.coupon_div * coupon_t) * prod.s0,
                ),
            ),
        )

    def _backward_induction(self) -> None:
        assert (
            self.prod is not None
            and self.fd_not_in is not None
            and self.fd_knockin is not None
            and self.out_dates is not None
            and self.pay_dates is not None
            and self.diff_obs_pay_dates is not None
        )
        prod = self.prod
        self.next_diff_obspaydate = self.diff_obs_pay_dates.repeat(
            np.diff(np.append(np.zeros((1,)), self.out_dates[::-1])).astype(int)
        )
        self.next_diff_obspaydate = np.append(self.diff_obs_pay_dates[0], self.next_diff_obspaydate)

        if self.european_knock_in:
            self.next_barrier_in = -1.0
            self.in_idx = 0

        for j in range(self.t_step - 1, -1, -1):
            self.fd_knockin.v_grid[1:-1, j] = self.fd_knockin.evolve(
                j, self.fd_knockin.v_grid[1:-1, j + 1], self.dt
            )
            self.fd_not_in.v_grid[1:-1, j] = self.fd_not_in.evolve(
                j, self.fd_not_in.v_grid[1:-1, j + 1], self.dt
            )

            if j in self.out_dates:
                coupon_t = 1 if self.trigger else self.next_paydate[j]
                if self.reversed_barrier_out is not None:
                    idx = int(np.where(self.out_dates == j)[0][0])
                    self.next_barrier_out = float(self.reversed_barrier_out[idx])
                else:
                    self.next_barrier_out = float(prod.barrier_out)
                self.out_idxs = 1 + np.array(
                    np.where(self.fd_not_in.s_vec >= self.next_barrier_out)[0]
                )

                if self.reversed_coupon_out is not None:
                    idx = int(np.where(self.out_dates == j)[0][0])
                    self.next_coupon_out = float(self.reversed_coupon_out[idx])
                else:
                    self.next_coupon_out = float(prod.coupon_out)

                knock_out_payoff = (
                    self.itm[self.out_idxs - 1]
                    + (prod.margin_lvl + self.next_coupon_out * coupon_t) * prod.s0
                ) * _disc_factor(
                    self._rate,
                    self.next_paydate[j],
                    self.next_paydate[j] - self.next_diff_obspaydate[j],
                )
                self.fd_not_in.v_grid[self.out_idxs, j] = self.fd_knockin.v_grid[
                    self.out_idxs, j
                ] = knock_out_payoff

                if not self.european_knock_in:
                    if self.reversed_barrier_in is not None:
                        idx = int(np.where(self.out_dates == j)[0][0])
                        self.next_barrier_in = float(self.reversed_barrier_in[idx])
                    else:
                        self.next_barrier_in = float(prod.barrier_in)
                    self.in_idx = (
                        1 + int(np.where(self.fd_not_in.s_vec <= self.next_barrier_in)[0][-1])
                        if self.next_barrier_in > 0
                        else 0
                    )

            self.fd_not_in.v_grid[: self.in_idx + 1, j] = self.fd_knockin.v_grid[
                : self.in_idx + 1, j
            ]
