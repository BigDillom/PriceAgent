"""QFbench task instance registry."""

from __future__ import annotations

from pathlib import Path

TASKS_ROOT = Path(__file__).parent


def list_task_dirs() -> list[Path]:
    """Return directories containing task.yaml and expected.json."""
    tasks: list[Path] = []
    for path in sorted(TASKS_ROOT.iterdir()):
        if not path.is_dir():
            continue
        if (path / "task.yaml").is_file() and (path / "expected.json").is_file():
            tasks.append(path)
    return tasks
