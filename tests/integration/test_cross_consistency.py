"""Cross-method consistency tests (oracle)."""

import pytest

from derivkit.core.enums import EngineMethod
from derivkit.core.rng import set_seed
from derivkit.data.market_env import MarketEnv
from derivkit.engine_orchestrator import build_product
from derivkit.pricing.engines import create_engine
from derivkit.verify.oracle import cross_check


@pytest.mark.integration
@pytest.mark.parametrize("method", ["analytic", "tree", "fdm", "mc", "quad"])
def test_vanilla_cross_consistency(method, vanilla_spec, tol):
    set_seed(42)
    env = MarketEnv.from_spec(vanilla_spec.to_dict())
    product = build_product(vanilla_spec, env)

    params: dict = {}
    if method == "mc":
        params = {"n_paths": 50_000, "seed": 42}
    elif method == "tree":
        params = {"n_steps": 300}
    elif method == "fdm":
        params = {"n_s": 300}

    engine = create_engine(method, **params)
    pv = engine.calc_present_value(product, env)

    ref_engine = create_engine(EngineMethod.ANALYTIC)
    ref_pv = ref_engine.calc_present_value(product, env)

    assert abs(pv - ref_pv) <= tol[method] + abs(ref_pv) * tol[method]


@pytest.mark.integration
def test_oracle_full(vanilla_spec):
    set_seed(42)
    result = cross_check(vanilla_spec, seed=42)
    assert result["passed"] is True
    assert "analytic" in result["results"]
