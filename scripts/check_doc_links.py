#!/usr/bin/env python3
"""Validate relative markdown links in docs/ and README."""

from __future__ import annotations

import re
import sys
from pathlib import Path

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
SKIP_PREFIXES = ("http://", "https://", "mailto:", "#")


def check_file(md_path: Path, repo_root: Path) -> list[str]:
    errors: list[str] = []
    text = md_path.read_text(encoding="utf-8")
    for _label, target in LINK_RE.findall(text):
        if target.startswith(SKIP_PREFIXES):
            continue
        target = target.split("#", 1)[0].strip()
        if not target:
            continue
        resolved = (md_path.parent / target).resolve()
        if not resolved.exists():
            errors.append(f"{md_path.relative_to(repo_root)}: broken link -> {target}")
    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    md_files = [repo_root / "README.md", *sorted((repo_root / "docs").glob("*.md"))]
    all_errors: list[str] = []
    for path in md_files:
        if path.exists():
            all_errors.extend(check_file(path, repo_root))
    if all_errors:
        print("Documentation link check FAILED:")
        for err in all_errors:
            print(f"  - {err}")
        return 1
    print(f"Documentation link check OK ({len(md_files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
