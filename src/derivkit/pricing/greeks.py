"""Unified greeks calculation utilities."""

from __future__ import annotations

from derivkit.core.interfaces import PricingEngine, Product
from derivkit.data.market_env import MarketEnv


def calc_greeks(
    engine: PricingEngine,
    product: Product,
    env: MarketEnv,
    which: list[str] | None = None,
) -> dict[str, float]:
    """Calculate greeks using engine's finite-difference implementation."""
    return engine.calc_greeks(product, env, which)
