"""Abstract base classes for processes, engines, volatility models, and products."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import numpy as np

from derivkit.core.enums import EngineMethod, VolType

if TYPE_CHECKING:
    from derivkit.data.market_env import MarketEnv


class StochProcess(ABC):
    """Stochastic process interface for evolution and PDE coefficients."""

    @abstractmethod
    def evolve(self, t: float, x: np.ndarray, dt: float, dw: np.ndarray) -> np.ndarray:
        """Evolve state forward one time step."""

    @abstractmethod
    def drift(self, t: float) -> float:
        """Instantaneous drift at time t."""

    @abstractmethod
    def diffusion(self, t: float, x: float) -> float:
        """Instantaneous diffusion coefficient at (t, x)."""

    @abstractmethod
    def pde_coef(self, t: float, x: float) -> tuple[float, float, float]:
        """Return PDE coefficients (a, b, c) for dV/dt + a d²V/dx² + b dV/dx + cV = 0."""


class VolModel(ABC):
    """Volatility model interface."""

    vol_type: VolType

    @abstractmethod
    def __call__(self, t: float, spot: float) -> float:
        """Return volatility at (t, spot)."""


class PricingEngine(ABC):
    """Pricing engine interface."""

    method: EngineMethod

    @abstractmethod
    def calc_present_value(
        self,
        product: Product,
        env: MarketEnv,
        t: float | None = None,
        spot: float | None = None,
    ) -> float:
        """Calculate present value of the product."""

    def calc_greeks(
        self,
        product: Product,
        env: MarketEnv,
        which: list[str] | None = None,
    ) -> dict[str, float]:
        """Calculate sensitivities via finite differences."""
        which = which or ["delta", "gamma", "vega", "theta", "rho"]
        greeks: dict[str, float] = {}
        base_pv = self.calc_present_value(product, env)
        spot = env.spot(product.underlying_id)
        bump_spot = spot * 0.01
        bump_vol = 0.01
        bump_rate = 0.0001
        bump_time = 1.0 / 365.0

        if "delta" in which or "gamma" in which:
            env_bump_up = env.bump_spot(product.underlying_id, bump_spot)
            env_bump_dn = env.bump_spot(product.underlying_id, -bump_spot)
            pv_up = self.calc_present_value(product, env_bump_up)
            pv_dn = self.calc_present_value(product, env_bump_dn)
            if "delta" in which:
                greeks["delta"] = (pv_up - pv_dn) / (2 * bump_spot)
            if "gamma" in which:
                greeks["gamma"] = (pv_up - 2 * base_pv + pv_dn) / (bump_spot**2)

        if "vega" in which:
            env_vol_up = env.bump_vol(product.underlying_id, bump_vol)
            env_vol_dn = env.bump_vol(product.underlying_id, -bump_vol)
            pv_vol_up = self.calc_present_value(product, env_vol_up)
            pv_vol_dn = self.calc_present_value(product, env_vol_dn)
            greeks["vega"] = (pv_vol_up - pv_vol_dn) / (2 * bump_vol) / 100.0

        if "rho" in which:
            env_rate_up = env.bump_rate(bump_rate)
            env_rate_dn = env.bump_rate(-bump_rate)
            pv_rate_up = self.calc_present_value(product, env_rate_up)
            pv_rate_dn = self.calc_present_value(product, env_rate_dn)
            greeks["rho"] = (pv_rate_up - pv_rate_dn) / (2 * bump_rate) / 100.0

        if "theta" in which:
            env_time = env.bump_time(-bump_time)
            pv_time = self.calc_present_value(product, env_time)
            greeks["theta"] = (pv_time - base_pv) / bump_time / 365.0

        return greeks


class Product(ABC):
    """Derivative product interface."""

    underlying_id: str

    @abstractmethod
    def payoff(self, path_or_spot: np.ndarray | float) -> float | np.ndarray:
        """Compute payoff given terminal spot or path."""

    @property
    @abstractmethod
    def maturity(self) -> float:
        """Time to maturity in years."""

    @property
    @abstractmethod
    def supported_engines(self) -> set[EngineMethod]:
        """Set of compatible pricing engines."""

    def price(
        self,
        engine: PricingEngine | None = None,
        env: MarketEnv | None = None,
    ) -> float:
        """Price using the given engine and market environment."""
        if engine is None or env is None:
            raise ValueError("Both engine and env are required")
        return engine.calc_present_value(self, env)
