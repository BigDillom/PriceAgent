"""Load and validate DSL from YAML/JSON files or dicts."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from derivkit.api.errors import DslValidationError
from derivkit.dsl.schema import PricingSpec

logger = logging.getLogger(__name__)


def _resolve_csv_path(cfg: dict[str, Any], base_dir: Path, key: str = "path") -> None:
    path = cfg.get(key)
    if path and not Path(path).is_absolute():
        cfg[key] = str((base_dir / path).resolve())


def _resolve_spot_paths(raw: dict[str, Any], base_dir: Path) -> None:
    """Resolve relative CSV paths in market underlyings against YAML directory."""
    market = raw.get("market", {})
    for u in market.get("underlyings", []):
        spot = u.get("spot")
        if isinstance(spot, dict) and spot.get("source") == "csv":
            _resolve_csv_path(spot, base_dir)

    calibration = raw.get("calibration")
    if isinstance(calibration, dict):
        data = calibration.get("data")
        if isinstance(data, dict) and data.get("source") == "csv":
            _resolve_csv_path(data, base_dir)


def load_spec(source: str | Path | dict[str, Any]) -> PricingSpec:
    """Load and validate a pricing specification.

    Args:
        source: Path to YAML/JSON file or dict specification.

    Returns:
        Validated PricingSpec.

    Raises:
        DslValidationError: On schema validation failure with field paths.
    """
    if isinstance(source, dict):
        raw = source
    else:
        path = Path(source)
        text = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            raw = yaml.safe_load(text)
        elif path.suffix == ".json":
            raw = json.loads(text)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")
        _resolve_spot_paths(raw, path.parent)

    try:
        return PricingSpec.model_validate(raw)
    except ValidationError as exc:
        errors = [
            {"field": ".".join(str(loc) for loc in e["loc"]), "message": e["msg"]}
            for e in exc.errors()
        ]
        raise DslValidationError(errors) from exc
