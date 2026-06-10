"""Sandbox runner end-to-end smoke tests (W6)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from derivkit.integ.grading import grade_result, load_expected
from derivkit.integ.sandbox_runner import run_sandbox
from derivkit.integ.tasks import list_task_dirs

TASKS = list_task_dirs()


@pytest.mark.integration
@pytest.mark.parametrize("task_dir", TASKS, ids=[p.name for p in TASKS])
def test_run_sandbox_writes_result(task_dir: Path, tmp_path: Path):
    """run_sandbox produces result.json graded against expected."""
    output_dir = tmp_path / task_dir.name
    output = run_sandbox(task_dir / "task.yaml", output_dir)

    result_file = output_dir / "result.json"
    assert result_file.is_file()
    on_disk = json.loads(result_file.read_text(encoding="utf-8"))
    assert on_disk["pv"] == output["pv"]

    expected = load_expected(task_dir / "expected.json")
    report = grade_result(on_disk, expected)
    report.assert_passed()


@pytest.mark.integration
def test_sandbox_runner_cli(tmp_path: Path):
    """python -m derivkit.integ.sandbox_runner works end-to-end."""
    task_dir = TASKS[0]
    output_dir = tmp_path / "cli_output"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "derivkit.integ.sandbox_runner",
            str(task_dir / "task.yaml"),
            str(output_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert (output_dir / "result.json").is_file()
