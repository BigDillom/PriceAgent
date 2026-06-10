"""Integration tests for high-level API."""

import pytest

import derivkit as dk
from derivkit.dsl.loader import load_spec


def test_price_from_dict(vanilla_spec_dict):
    result = dk.price(vanilla_spec_dict)
    assert 10.0 < result.pv < 11.0
    assert "engine" in result.meta


def test_price_from_yaml(tmp_path, vanilla_spec_dict):
    import yaml

    path = tmp_path / "task.yaml"
    path.write_text(yaml.dump(vanilla_spec_dict))
    result = dk.price(path)
    assert result.pv > 0


def test_dsl_validation_error():
    from derivkit.api.errors import DslValidationError

    with pytest.raises(DslValidationError):
        load_spec({"task": "invalid", "market": {}, "product": {}})
