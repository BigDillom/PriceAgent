"""QFbench task instance grading (W6)."""

from __future__ import annotations

from pathlib import Path

import pytest

import derivkit as dk
from derivkit.integ.grading import grade_result, load_expected
from derivkit.integ.tasks import list_task_dirs

TASKS = list_task_dirs()
TASK_IDS = [p.name for p in TASKS]


@pytest.mark.integration
@pytest.mark.parametrize("task_dir", TASKS, ids=TASK_IDS)
def test_task_grading(task_dir: Path):
    """Price each QFbench task and assert within expected tolerances."""
    task_yaml = task_dir / "task.yaml"
    expected_path = task_dir / "expected.json"

    result = dk.price(task_yaml)
    expected = load_expected(expected_path)
    report = grade_result(result, expected)
    report.assert_passed()


@pytest.mark.integration
@pytest.mark.parametrize("task_dir", TASKS, ids=TASK_IDS)
def test_task_yaml_loads(task_dir: Path):
    """Task YAML must parse and produce positive PV."""
    from derivkit.dsl.loader import load_spec

    spec = load_spec(task_dir / "task.yaml")
    assert spec.task == "price"
    result = dk.price(spec)
    assert result.pv > 0
