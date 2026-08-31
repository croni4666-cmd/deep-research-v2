"""Check release-version consistency without publishing a release."""

from __future__ import annotations

import argparse
import re
import tomllib
from datetime import date
from pathlib import Path
from typing import Any

VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def check_release(root: Path, expected_version: str | None = None) -> dict[str, Any]:
    issues: list[dict[str, str]] = []

    def issue(code: str, path: str, message: str) -> None:
        issues.append({"code": code, "path": path, "message": message})

    try:
        project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        skill = (root / "SKILL.md").read_text(encoding="utf-8")
        changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
        readme = (root / "README.md").read_text(encoding="utf-8")
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        issue("release.unreadable", "$", str(exc))
        return _finish(issues, {})
    project_version = project.get("project", {}).get("version")
    skill_match = re.search(r"(?m)^\s*version:\s*([^\s]+)\s*$", skill)
    skill_version = skill_match.group(1) if skill_match else None
    version = expected_version or project_version
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        issue("release.invalid_version", "$.version", "Expected semantic version X.Y.Z.")
        return _finish(issues, {})
    if project_version != version:
        issue("release.project_version", "pyproject.toml",
              f"Project version is {project_version!r}; expected {version!r}.")
    if skill_version != version:
        issue("release.skill_version", "SKILL.md",
              f"Skill version is {skill_version!r}; expected {version!r}.")
    heading = re.search(
        rf"(?m)^##\s+{re.escape(version)}\s+-\s+([^\r\n]+)\s*$", changelog,
    )
    if not heading:
        issue("release.missing_changelog", "CHANGELOG.md",
              f"Missing changelog heading for {version}.")
    else:
        release_date = heading.group(1).strip()
        try:
            date.fromisoformat(release_date)
        except ValueError:
            issue("release.invalid_date", "CHANGELOG.md",
                  "Release changelog heading must use an exact YYYY-MM-DD date.")
    if f"## What changed in {version}" not in readme:
        issue("release.stale_readme", "README.md",
              f"README must summarize what changed in {version}.")
    return _finish(issues, {"version": version})


def _finish(issues: list[dict[str, str]], summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "verdict": "PASS" if not issues else "FAIL",
        "error_count": len(issues),
        "summary": summary,
        "issues": issues,
        "scope_note": (
            "This check verifies release metadata only. It does not publish a tag, "
            "run evaluations, or support comparative benchmark claims."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--expected-version")
    args = parser.parse_args(argv)
    result = check_release(args.root.resolve(), args.expected_version)
    print(f"{result['verdict']}: version={result['summary'].get('version', 'unknown')}, "
          f"{result['error_count']} errors")
    for item in result["issues"]:
        print(f"- ERROR {item['code']} {item['path']}: {item['message']}")
    print(result["scope_note"])
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
