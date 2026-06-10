"""Multi-method oracle cross-consistency checks."""

from __future__ import annotations

import logging
from typing import Any

from derivkit.core.enums import EngineMethod
from derivkit.core.rng import set_seed
from derivkit.data.market_env import MarketEnv
from derivkit.dsl.schema import PricingSpec
from derivkit.engine_orchestrator import build_product

logger = logging.getLogger(__name__)

# Default absolute+relative tolerance per (product_type, engine_method).
# Value is max(abs_tol, rel_tol * |reference_pv|).
TOLERANCE_MATRIX: dict[str, dict[str, float]] = {
    "vanilla.european": {
        "analytic": 0.0,
        "tree": 0.05,
        "fdm": 0.05,
        "mc": 0.15,
        "quad": 0.05,
    },
    "vanilla": {
        "analytic": 0.0,
        "tree": 0.05,
        "fdm": 0.05,
        "mc": 0.15,
        "quad": 0.05,
    },
    "snowball.standard": {
        "mc": 0.15,
        "fdm": 0.02,
        "quad": 0.02,
    },
    "snowball": {
        "mc": 0.15,
        "fdm": 0.02,
        "quad": 0.02,
    },
    "phoenix": {
        "mc": 0.15,
    },
    "fcn": {
        "mc": 0.15,
        "quad": 0.05,
    },
    "barrier": {
        "analytic": 0.02,
        "mc": 0.15,
    },
    "digital": {
        "analytic": 0.02,
        "mc": 0.15,
    },
    "asian": {
        "analytic": 0.05,
        "mc": 0.15,
    },
}

DEFAULT_TOLERANCES: dict[str, float] = TOLERANCE_MATRIX["vanilla.european"]


def default_tolerances(product_type: str | None = None) -> dict[str, float]:
    """Return tolerance map for a product type, falling back to vanilla defaults."""
    if product_type is None:
        return dict(DEFAULT_TOLERANCES)
    return dict(TOLERANCE_MATRIX.get(product_type, DEFAULT_TOLERANCES))


def tolerance_for(product_type: str, method: str, ref_pv: float = 0.0) -> float:
    """Absolute tolerance band for a product/engine pair."""
    tol_map = default_tolerances(product_type)
    t = tol_map.get(method, 0.1)
    return t + abs(ref_pv) * t


def cross_check(
    spec: PricingSpec,
    methods: list[EngineMethod] | None = None,
    reference: EngineMethod = EngineMethod.ANALYTIC,
    tolerances: dict[str, float] | None = None,
    seed: int = 0,
) -> dict[str, Any]:
    """Run multiple engines and compare against reference.

    Returns:
        Dict with reference_pv, results per method, and pass/fail status.
    """
    if spec.product is None:
        raise ValueError("product section is required")
    product_type = spec.product.type
    tol = tolerances or default_tolerances(product_type)

    if methods is None:
        methods = _default_methods_for_product(product_type, reference)

    set_seed(seed)

    env = MarketEnv.from_spec(spec.to_dict())
    product = build_product(spec, env)

    results: dict[str, float] = {}
    for method in methods:
        params: dict[str, Any] = _engine_params(method, seed, product_type)
        engine = _create_engine_for_cross_check(spec, product, method, params)
        results[method.value] = engine.calc_present_value(product, env)

    ref_key = reference.value
    if ref_key not in results:
        reference = methods[0]
        ref_key = reference.value

    ref_pv = results[ref_key]
    checks: dict[str, bool] = {}
    for method_key, pv in results.items():
        if method_key == ref_key:
            checks[method_key] = True
            continue
        t = tol.get(method_key, 0.1)
        checks[method_key] = abs(pv - ref_pv) <= t + abs(ref_pv) * t

    return {
        "reference": ref_key,
        "reference_pv": ref_pv,
        "results": results,
        "checks": checks,
        "passed": all(checks.values()),
        "product_type": product_type,
        "tolerances": tol,
    }


def _default_methods_for_product(product_type: str, reference: EngineMethod) -> list[EngineMethod]:
    tol = default_tolerances(product_type)
    methods = [EngineMethod(m) for m in tol if EngineMethod(m) != reference]
    if reference in [EngineMethod(m) for m in tol]:
        methods.insert(0, reference)
    elif not methods:
        methods = [reference]
    return methods


def _engine_params(method: EngineMethod, seed: int, product_type: str) -> dict[str, Any]:
    if method == EngineMethod.MC:
        n_paths = 80_000 if product_type.startswith(("snowball", "phoenix", "fcn")) else 50_000
        return {"n_paths": n_paths, "seed": seed}
    if method == EngineMethod.TREE:
        return {"n_steps": 200}
    if method == EngineMethod.FDM:
        if product_type.startswith("snowball"):
            return {"s_step": 200}
        return {"n_s": 200}
    if method == EngineMethod.QUAD:
        if product_type.startswith("snowball"):
            return {"n_points": 901}
        return {"n": 4096}
    return {}


def _create_engine_for_cross_check(spec, product, method: EngineMethod, params: dict):
    """Route to product-specific engines when generic factory is insufficient."""
    from derivkit.engine_orchestrator import _create_engine_for_product

    cross_spec = spec.model_copy(deep=True)
    cross_spec.engine.method = method
    cross_spec.engine.params = params
    return _create_engine_for_product(cross_spec, product, params)
