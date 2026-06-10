"""FFT quadrature engine for FCN / European-KI autocallable products.

Adapted from PriceLib (Apache 2.0):
pricelib/pricing_engines/integral_engines/quad_fcn_engine.py
"""

from __future__ import annotations

import logging
from datetime import date

import numpy as np

from derivkit.core.enums import EngineMethod, QuadMethod
from derivkit.core.interfaces import PricingEngine, Product
from derivkit.data.market_env import MarketEnv
from derivkit.pricing.engines.quad_fft_base import QuadFftBase
from derivkit.pricing.products.fcn import FCN

logger = logging.getLogger(__name__)


class QuadFcnEngine(PricingEngine, QuadFftBase):
    """FFT quadrature for FCN (fixed coupon, European knock-in)."""

    method = EngineMethod.QUAD

    def __init__(
        self,
        quad_method: QuadMethod = QuadMethod.SIMPSON,
        n_points: int = 1301,
    ) -> None:
        QuadFftBase.__init__(self, quad_method=quad_method, n_points=n_points)
        self._barrier_out: np.ndarray | None = None
        self._barrier_in: np.ndarray | None = None
        self._barrier_yield: np.ndarray | None = None
        self._coupon: np.ndarray | None = None

    def calc_present_value(
        self,
        product: Product,
        env: MarketEnv,
        t: float | None = None,
        spot: float | None = None,
    ) -> float:
        if not isinstance(product, FCN):
            raise TypeError(f"QuadFcnEngine supports FCN, got {type(product)}")

        spot = spot if spot is not None else env.spot(product.underlying_id)
        maturity = product.maturity
        val_date = env.valuation_date

        r = env.rate(maturity)
        q = env.div_yield(product.underlying_id)
        vol = env.vol(product.underlying_id, maturity)
        self.set_quad_params(r, q, vol)

        obs_frac = self._obs_fractions(val_date, product)
        obs_frac = obs_frac[obs_frac >= 0]
        if obs_frac.size == 0:
            obs_frac = np.array([maturity])

        self._barrier_out = product._barrier_out[-len(obs_frac) :].copy()
        self._barrier_in = product._barrier_in[-len(obs_frac) :].copy()
        self._barrier_yield = product._barrier_yield[-len(obs_frac) :].copy()
        self._coupon = product._coupon[-len(obs_frac) :].copy()

        maturity_bdays = maturity
        if maturity_bdays <= 0:
            return float(self._terminal_payoff(product, np.array([spot]))[0])

        if obs_frac[0] == 0:
            if spot >= self._barrier_out[0]:
                return float((product.margin_lvl + self._coupon[0]) * product.s0)
            s0_dt = float(obs_frac[1]) if obs_frac.size > 1 else maturity_bdays
            dt_vec = np.diff(obs_frac)[1:] if obs_frac.size > 2 else np.array([])
        else:
            s0_dt = float(obs_frac[0])
            dt_vec = np.diff(obs_frac)

        backward_steps = dt_vec.size
        if backward_steps == 0:
            s_vec = np.array([spot])
            return float(self._terminal_payoff(product, s_vec)[0])

        self.init_grid(spot, vol, maturity_bdays)
        assert self.ln_s_vec is not None
        s_vec = np.exp(self.ln_s_vec)
        v_grid = np.zeros((self.n_points, backward_steps + 2))

        barrier_out_idx = np.searchsorted(s_vec, self._barrier_out, side="right")
        barrier_yield_idx = np.searchsorted(s_vec, self._barrier_yield, side="right")

        for step in range(backward_steps + 1, 0, -1):
            if step == backward_steps + 1:
                v_grid[:, -1] = self._terminal_payoff(product, s_vec)
            else:
                v_grid[:, step] = self.fft_step_backward(
                    self.ln_s_vec, self.ln_s_vec, v_grid[:, step + 1], dt_vec[step - 1]
                )
                bo = barrier_out_idx[step - 1]
                by = barrier_yield_idx[step - 1]
                v_grid[bo:, step] = (product.margin_lvl + self._coupon[step - 1]) * product.s0
                v_grid[by:bo, step] += self._coupon[step - 1] * product.s0

        x = np.array([np.log(spot)])
        value = float(self.fft_step_backward(x, self.ln_s_vec, v_grid[:, 1], s0_dt)[0])
        if obs_frac[0] == 0 and self._barrier_yield[0] < spot < self._barrier_out[0]:
            value += self._coupon[0] * product.s0
        return value

    def _obs_fractions(self, val_date: date, product: FCN) -> np.ndarray:
        fracs: list[float] = []
        for obs in product.obs_dates:
            days = (obs - val_date).days
            fracs.append(days / product.annual_days)
        if not fracs:
            return np.array([product.maturity])
        return np.array(fracs, dtype=float)

    def _terminal_payoff(self, prod: FCN, s_vec: np.ndarray) -> np.ndarray:
        assert self._barrier_yield is not None and self._barrier_in is not None and self._coupon is not None
        return (
            prod.margin_lvl * prod.s0
            + np.where(s_vec > self._barrier_yield[-1], self._coupon[-1] * prod.s0, 0)
            + np.where(
                s_vec > self._barrier_in[-1],
                0,
                prod.parti_in
                * (-prod.strike_upper + np.where(s_vec > prod.strike_lower, s_vec, prod.strike_lower)),
            )
        )
