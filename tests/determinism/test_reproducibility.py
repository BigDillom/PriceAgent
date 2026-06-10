"""Determinism tests: same input + seed → bitwise identical results."""

import derivkit as dk
from derivkit.core.rng import set_seed


def test_mc_determinism(vanilla_spec_dict):
    vanilla_spec_dict["engine"] = {"method": "mc", "params": {"n_paths": 10000}}
    vanilla_spec_dict["output"] = {"deterministic": True, "seed": 99}

    set_seed(99)
    r1 = dk.price(vanilla_spec_dict)

    set_seed(99)
    r2 = dk.price(vanilla_spec_dict)

    assert r1.pv == r2.pv


def test_analytic_determinism(vanilla_spec_dict):
    r1 = dk.price(vanilla_spec_dict)
    r2 = dk.price(vanilla_spec_dict)
    assert r1.pv == r2.pv
