"""Canonicalize DSL product.type aliases (LLM-friendly names → supported types)."""

from __future__ import annotations

from typing import Any

# canonical product.type -> default params to merge into product.params
PRODUCT_TYPE_ALIASES: dict[str, tuple[str, dict[str, Any]]] = {
    # --- Vanilla (canonical type is always vanilla.european; exercise distinguishes style) ---
    "vanilla": ("vanilla.european", {}),
    "vanilla_european": ("vanilla.european", {"exercise": "european"}),
    "european": ("vanilla.european", {"exercise": "european"}),
    "european_call": ("vanilla.european", {"exercise": "european", "call_put": "call"}),
    "european_put": ("vanilla.european", {"exercise": "european", "call_put": "put"}),
    "vanilla_call": ("vanilla.european", {"call_put": "call"}),
    "vanilla_put": ("vanilla.european", {"call_put": "put"}),
    "call": ("vanilla.european", {"call_put": "call"}),
    "put": ("vanilla.european", {"call_put": "put"}),
    "american": ("vanilla.european", {"exercise": "american"}),
    "american_call": ("vanilla.european", {"exercise": "american", "call_put": "call"}),
    "american_put": ("vanilla.european", {"exercise": "american", "call_put": "put"}),
    "vanilla_american": ("vanilla.european", {"exercise": "american"}),
    "vanilla_american_call": ("vanilla.european", {"exercise": "american", "call_put": "call"}),
    "vanilla_american_put": ("vanilla.european", {"exercise": "american", "call_put": "put"}),
    "option": ("vanilla.european", {}),
    "option_call": ("vanilla.european", {"call_put": "call"}),
    "option_put": ("vanilla.european", {"call_put": "put"}),
    # --- Snowball ---
    "snowball": ("snowball.standard", {}),
    "snowball_standard": ("snowball.standard", {}),
    # --- Phoenix ---
    "phoenix": ("phoenix.standard", {}),
    "phoenix_standard": ("phoenix.standard", {}),
    # --- FCN ---
    "fcn": ("fcn.standard", {}),
    "fcn_standard": ("fcn.standard", {}),
    # --- Barrier ---
    "barrier": ("barrier.single", {}),
    "barrier_single": ("barrier.single", {}),
    "barrier_up_and_out": ("barrier.up_and_out", {}),
    "barrier_up_out": ("barrier.up_and_out", {}),
    "up_and_out": ("barrier.up_and_out", {}),
    "barrier_down_and_in": ("barrier.down_and_in", {}),
    "barrier_down_in": ("barrier.down_and_in", {}),
    "down_and_in": ("barrier.down_and_in", {}),
    # --- Digital ---
    "digital": ("digital.cash", {}),
    "digital_cash": ("digital.cash", {}),
    "digital_cash_or_nothing": ("digital.cash_or_nothing", {}),
    "cash_or_nothing": ("digital.cash_or_nothing", {}),
    # --- Asian ---
    "asian": ("asian.geometric", {}),
    "asian_geometric": ("asian.geometric", {"ave_method": "geometric"}),
    "geometric_asian": ("asian.geometric", {"ave_method": "geometric"}),
    "asian_arithmetic": ("asian.arithmetic", {"ave_method": "arithmetic"}),
    "arithmetic_asian": ("asian.arithmetic", {"ave_method": "arithmetic"}),
}

_PARAM_KEYS = frozenset(
    {
        "strike",
        "maturity",
        "call_put",
        "exercise",
        "s0",
        "barrier_out",
        "barrier_in",
        "coupon_out",
        "coupon",
        "barrier_yield",
        "lock_term",
        "margin_lvl",
        "parti_in",
        "barrier",
        "barrier_type",
        "rebate",
        "participation",
        "payment_type",
        "discrete_obs_interval",
        "ave_method",
        "substitute",
        "obs_start_frac",
        "obs_end_frac",
        "s_average",
        "enhanced",
        "limited_price",
        "t_step_per_year",
    }
)


def normalize_product_type_key(ptype: str) -> str:
    """Normalize a product.type string for alias lookup."""
    return ptype.lower().strip().replace("-", "_").replace(" ", "_").replace(".", "_")


def resolve_product_alias(ptype: str) -> tuple[str, dict[str, Any]]:
    """Map alias to (canonical_type, default_params). Unknown types pass through."""
    key = normalize_product_type_key(ptype)
    if key in PRODUCT_TYPE_ALIASES:
        canonical, defaults = PRODUCT_TYPE_ALIASES[key]
        return canonical, dict(defaults)
    return ptype.lower().strip(), {}


def canonicalize_product(product: dict[str, Any]) -> dict[str, Any]:
    """Coerce product.type aliases and hoist param fields from product root."""
    out = dict(product)
    params = dict(out.get("params") or {})

    for key in _PARAM_KEYS:
        if key in out and key not in params:
            params[key] = out.pop(key)

    ptype = str(out.get("type", "vanilla.european"))
    canonical, defaults = resolve_product_alias(ptype)
    out["type"] = canonical
    for key, value in defaults.items():
        params.setdefault(key, value)

    out["params"] = params
    return out
