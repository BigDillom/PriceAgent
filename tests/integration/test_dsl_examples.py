"""DSL example YAML smoke tests (W6)."""

from __future__ import annotations

from pathlib import Path

import pytest

import derivkit as dk
from derivkit.dsl.loader import load_spec

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "src" / "derivkit" / "dsl" / "examples"

SNOWBALL_EXAMPLES = ["snowball_standard.yaml", "snowball_standard_fdm.yaml"]
BARRIER_EXAMPLES = ["barrier_up_and_out.yaml", "barrier_down_and_in.yaml"]


@pytest.mark.integration
@pytest.mark.parametrize("yaml_name", SNOWBALL_EXAMPLES)
def test_snowball_dsl_examples(yaml_name: str):
    path = EXAMPLES_DIR / yaml_name
    spec = load_spec(path)
    assert spec.product.type == "snowball.standard"
    result = dk.price(spec)
    assert 85.0 < result.pv < 105.0


@pytest.mark.integration
@pytest.mark.parametrize("yaml_name,barrier_type", [
    ("barrier_up_and_out.yaml", "barrier.up_and_out"),
    ("barrier_down_and_in.yaml", "barrier.down_and_in"),
])
def test_barrier_dsl_examples(yaml_name: str, barrier_type: str):
    path = EXAMPLES_DIR / yaml_name
    spec = load_spec(path)
    assert spec.product.type == barrier_type
    result = dk.price(spec)
    assert result.pv > 0
