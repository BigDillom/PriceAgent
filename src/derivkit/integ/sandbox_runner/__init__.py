"""Sandbox runner for QFbench task execution."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import derivkit as dk

logger = logging.getLogger(__name__)


def run_sandbox(
    spec_path: str | Path,
    output_dir: str | Path = "/app/output",
) -> dict[str, Any]:
    """Run pricing in sandbox: read spec → price → write output.

    Args:
        spec_path: Path to task YAML/JSON specification.
        output_dir: Directory to write results (default QFbench /app/output).

    Returns:
        Result dict written to output.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    result = dk.price(spec_path)
    output = result.to_dict()

    out_file = output_path / "result.json"
    out_file.write_text(json.dumps(output, indent=2), encoding="utf-8")
    logger.info("Wrote sandbox output to %s", out_file)
    return output
