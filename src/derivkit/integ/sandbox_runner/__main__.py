"""CLI entry: python -m derivkit.integ.sandbox_runner <task.yaml> [output_dir]."""

from __future__ import annotations

import sys

from derivkit.integ.sandbox_runner import run_sandbox


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("Usage: python -m derivkit.integ.sandbox_runner <task.yaml> [output_dir]")
        return 1
    spec_path = args[0]
    output_dir = args[1] if len(args) > 1 else "/app/output"
    run_sandbox(spec_path, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
