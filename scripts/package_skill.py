"""Build a minimal portable Evidence Deep Research Skill directory."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

TARGETS = {"codex", "minimax"}
FILES = ("SKILL.md", "LICENSE")
DIRECTORIES = ("steps", "references")
HELPERS = ("plan_preview.py", "plan_record.py", "evidence_audit.py", "runtime_check.py")


def package_skill(root: Path, output: Path, target: str) -> Path:
    if target not in TARGETS:
        raise ValueError(f"unsupported target: {target}")
    destination = output / "evidence-deep-research"
    if destination.exists():
        raise FileExistsError(f"destination already exists: {destination}")
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(r"(?m)^\s*version:\s*([^\s]+)\s*$", text)
    if not match:
        raise ValueError("SKILL.md has no metadata version")
    destination.mkdir(parents=True)
    for name in FILES:
        shutil.copy2(root / name, destination / name)
    for name in DIRECTORIES:
        shutil.copytree(root / name, destination / name)
    scripts = destination / "scripts"
    scripts.mkdir()
    for name in HELPERS:
        shutil.copy2(root / "scripts" / name, scripts / name)
    manifest = {
        "schema_version": 1,
        "name": "evidence-deep-research",
        "version": match.group(1),
        "target": target,
        "portable_core": True,
        "includes_evaluation_data": False,
    }
    (destination / "PACKAGE.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", choices=sorted(TARGETS), required=True)
    args = parser.parse_args(argv)
    try:
        destination = package_skill(args.root.resolve(), args.output.resolve(), args.target)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
