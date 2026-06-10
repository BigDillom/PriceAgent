"""FFT quadrature engine for standard snowball products.

Adapted from PriceLib (Apache 2.0):
pricelib/pricing_engines/integral_engines/quad_snowball_engine.py
"""

from __future__ import annotations

import logging
from datetime import date

import numpy as np

from derivkit.core.enums import EngineMethod, QuadMethod
from derivkit.core.interfaces import PricingEngine, Product
from derivkit.data.market_env import MarketEnv
from derivkit.pricing.engines.quad_fft_base import QuadFftBase
from derivkit.pricing.products.snowball import StandardSnowball

logger = logging.getLogger(__name__)


def _disc_factor(rate: float, t_from: float, t_to: float | np.ndarray) -> float | np.ndarray:
    return np.exp(-rate * (np.asarray(t_to, dtype=float) - t_from))


class QuadSnowballEngine(PricingEngine, QuadFftBase):
    """FFT quadrature for knock-in/knock-out snowball (non-European-KI only)."""

    method = EngineMethod.QUAD

    def __init__(
        self,
        quad_method: QuadMethod = QuadMethod.SIMPSON,
        n_points: int = 1301,
        trigger: bool = False,
    ) -> None:
        QuadFftBase.__init__(self, quad_method=quad_method, n_points=n_points)
        self.trigger = trigger
        self.prod: StandardSnowball | None = None
        self.backward_steps: int = 0
        self.out_dates: np.ndarray | None = None
        self.pay_dates: np.ndarray | None = None
        self.diff_obs_pay_dates: np.ndarray | None = None
        self.dt: float = 0.0
        self.j_vec: np.ndarray | None = None
        self.v_not_in: np.ndarray | None = None
        self.v_knock_in: np.ndarray | None = None
        self.next_paydate: np.ndarray | None = None
        self.next_diff_obspaydate: np.ndarray | None = None
        self.next_barrier_out: float = 0.0
        self.next_barrier_in: float = 0.0
        self.next_coupon_out: float = 0.0
        self.reversed_barrier_out: np.ndarray | None = None
        self.reversed_barrier_in: np.ndarray | None = None
        self.reversed_coupon_out: np.ndarray | None = None
        self.coupon_outs: np.ndarray | None = None
        self.in_idx: int = 0
        self.out_idxs: np.ndarray | None = None
        self.itm: np.ndarray | None = None
        self.knocked_in: bool = False

    def calc_present_value(
        self,
        product: Product,
        env: MarketEnv,
        t: float | None = None,
        spot: float | None = None,
    ) -> float:
        if not isinstance(product, StandardSnowball):
            raise TypeError(f"QuadSnowballEngine supports StandardSnowball, got {type(product)}")

        self.prod = product
        self.knocked_in = bool(getattr(product, "knocked_in", False))
        spot = spot if spot is not None else env.spot(product.underlying_id)
        maturity = product.maturity
        val_date = env.valuation_date

        r = env.rate(maturity)
        q = env.div_yield(product.underlying_id)
        vol = env.vol(product.underlying_id, maturity)
        self.set_quad_params(r, q, vol)

        self.backward_steps = max(round(product.t_step_per_year * maturity), 0)
        tau_grid = (
            self.backward_steps / product.t_step_per_year if self.backward_steps else maturity
        )
        self.init_grid(spot, vol, tau_grid)

        assert self.ln_s_vec is not None
        s_vec = np.exp(self.ln_s_vec)
        self.dt = 1.0 / product.t_step_per_year if self.backward_steps else 0.0
        self.j_vec = np.linspace(0, self.backward_steps, self.backward_steps + 1)
        self.v_not_in = np.zeros((self.n_points, self.backward_steps + 1))
        self.v_knock_in = np.zeros((self.n_points, self.backward_steps + 1))

        obs_steps = self._obs_step_indices(val_date, product, self.backward_steps, maturity)
        if obs_steps.size == 0 or obs_steps[-1] != self.backward_steps:
            obs_steps = np.append(obs_steps, self.backward_steps)
        self.out_dates = np.round(np.flip(obs_steps)).astype(int)
        self.pay_dates = obs_steps.astype(float) * (maturity / max(self.backward_steps, 1))
        self.diff_obs_pay_dates = np.zeros(len(self.pay_dates), dtype=float)

        self._init_terminal_condition(s_vec)

        self.next_diff_obspaydate = self.diff_obs_pay_dates.repeat(
            np.diff(np.append(np.zeros(1), self.out_dates[::-1])).astype(int)
        )
        self.next_diff_obspaydate = np.append(self.diff_obs_pay_dates[0], self.next_diff_obspaydate)
        self.next_paydate = self.pay_dates.repeat(
            np.diff(np.append(np.zeros(1), self.out_dates[::-1])).astype(int)
        )
        self.next_paydate = np.append(self.pay_dates[0], self.next_paydate)

        if self.backward_steps == 0:
            return float(self.v_knock_in[0, 0] if self.knocked_in else self.v_not_in[0, 0])

        if 0 in self.out_dates:
            j = 0
            start_barrier_out = self._barrier_at_obs(j, product.barrier_out)
            if spot >= start_barrier_out:
                start_coupon_out = self._coupon_at_obs(j, product.coupon_out)
                start_t = 1.0 if self.trigger else float(self.next_paydate[j])
                call = max(spot - product.strike_call, 0.0) * product.parti_out
                margin = (product.margin_lvl + start_coupon_out * start_t) * product.s0
                disc = _disc_factor(
                    r,
                    float(self.next_paydate[j]),
                    float(self.next_paydate[j] - self.next_diff_obspaydate[j]),
                )
                return float(call + margin * disc)

        for j in range(self.backward_steps - 1, 0, -1):
            if not self.knocked_in:
                self.v_not_in[:, j] = self.fft_step_backward(
                    self.ln_s_vec, self.ln_s_vec, self.v_not_in[:, j + 1], self.dt
                )
            self.v_knock_in[:, j] = self.fft_step_backward(
                self.ln_s_vec, self.ln_s_vec, self.v_knock_in[:, j + 1], self.dt
            )

            if j in self.out_dates:
                coupon_t = 1.0 if self.trigger else float(self.next_paydate[j])
                self.next_barrier_out = self._barrier_at_obs(j, product.barrier_out)
                self.out_idxs = np.array(np.where(s_vec >= self.next_barrier_out)[0])
                self.next_coupon_out = self._coupon_at_obs(j, product.coupon_out)
                knock_out_payoff = self.itm[self.out_idxs] + (
                    product.margin_lvl + self.next_coupon_out * coupon_t
                ) * product.s0 * _disc_factor(
                    r,
                    float(self.next_paydate[j]),
                    float(self.next_paydate[j] - self.next_diff_obspaydate[j]),
                )
                self.v_not_in[self.out_idxs, j] = self.v_knock_in[self.out_idxs, j] = (
                    knock_out_payoff
                )

                self.next_barrier_in = self._barrier_in_at_obs(j, product.barrier_in)
                if self.next_barrier_in > 0 and s_vec[0] <= self.next_barrier_in:
                    self.in_idx = int(np.where(s_vec <= self.next_barrier_in)[0][-1])
                else:
                    self.in_idx = 0

            if not self.knocked_in:
                self.v_not_in[: self.in_idx, j] = self.v_knock_in[: self.in_idx, j]

        x = np.array([np.log(spot)])
        if not self.knocked_in and spot > self.next_barrier_in:
            return float(self.fft_step_backward(x, self.ln_s_vec, self.v_not_in[:, 1], self.dt)[0])
        return float(self.fft_step_backward(x, self.ln_s_vec, self.v_knock_in[:, 1], self.dt)[0])

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

    def _barrier_at_obs(self, j: int, barrier_out: float | list | np.ndarray) -> float:
        if self.reversed_barrier_out is not None:
            idx = int(np.where(self.out_dates == j)[0][0])
            return float(self.reversed_barrier_out[idx])
        return float(barrier_out)

    def _barrier_in_at_obs(self, j: int, barrier_in: float | list | np.ndarray) -> float:
        if self.reversed_barrier_in is not None:
            idx = int(np.where(self.out_dates == j)[0][0])
            return float(self.reversed_barrier_in[idx])
        return float(barrier_in)

    def _coupon_at_obs(self, j: int, coupon_out: float | list | np.ndarray) -> float:
        if self.reversed_coupon_out is not None:
            idx = int(np.where(self.out_dates == j)[0][0])
            return float(self.reversed_coupon_out[idx])
        return float(coupon_out)

    def _init_terminal_condition(self, s_vec: np.ndarray) -> None:
        assert self.prod is not None and self.out_dates is not None and self.pay_dates is not None
        prod = self.prod
        n_obs = len(self.out_dates)

        barrier_in = prod._barrier_in[-n_obs:].copy()
        barrier_out = prod._barrier_out[-n_obs:].copy()
        coupon_out = prod._coupon_out[-n_obs:].copy()

        if barrier_in.size > 1 and not np.allclose(barrier_in, barrier_in[0]):
            self.reversed_barrier_in = np.flip(barrier_in)
            self.next_barrier_in = float(barrier_in[-1])
        else:
            self.reversed_barrier_in = None
            self.next_barrier_in = float(barrier_in[-1])

        if barrier_out.size > 1 and not np.allclose(barrier_out, barrier_out[0]):
            self.reversed_barrier_out = np.flip(barrier_out)
            self.next_barrier_out = float(barrier_out[-1])
        else:
            self.reversed_barrier_out = None
            self.next_barrier_out = float(barrier_out[-1])

        if coupon_out.size > 1 and not np.allclose(coupon_out, coupon_out[0]):
            self.reversed_coupon_out = np.flip(coupon_out)
            self.next_coupon_out = float(coupon_out[-1])
            coupon_outs = np.array(coupon_out).repeat(
                np.diff(np.append(np.zeros(1), self.out_dates[::-1])).astype(int)
            )
            self.coupon_outs = np.append(coupon_out[0], coupon_outs)
        else:
            self.reversed_coupon_out = None
            self.next_coupon_out = float(coupon_out[-1])
            self.coupon_outs = np.full(self.backward_steps + 1, self.next_coupon_out)

        if self.next_barrier_in > 0 and s_vec[0] <= self.next_barrier_in:
            self.in_idx = int(np.where(s_vec <= self.next_barrier_in)[0][-1])
        else:
            self.in_idx = 0

        self.out_idxs = np.array(np.where(s_vec >= self.next_barrier_out)[0])
        self.itm = np.where(
            s_vec - prod.strike_call > 0, (s_vec - prod.strike_call) * prod.parti_out, 0.0
        )

        coupon_t = 1.0 if self.trigger else float(self.pay_dates[-1])
        assert self.v_knock_in is not None and self.v_not_in is not None

        self.v_knock_in[:, -1] = np.where(
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
        self.v_not_in[:, -1] = np.where(
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
