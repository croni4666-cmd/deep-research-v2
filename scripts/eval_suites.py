"""Validate versioned deep-research evaluation suite manifests."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ALLOWED_MODES = {"builtin", "combined", "evidence"}
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _issue(issues: list[dict[str, str]], code: str, path: str, message: str) -> None:
    issues.append({"code": code, "path": path, "message": message})


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _catalog_cases(catalog: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(catalog, dict) or not isinstance(catalog.get("cases"), list):
        return {}
    return {
        case["id"]: case
        for case in catalog["cases"]
        if isinstance(case, dict) and _text(case.get("id"))
    }


def validate_suites(data: Any, catalog: Any) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    cases = _catalog_cases(catalog)
    if not isinstance(data, dict):
        _issue(issues, "suites.not_object", "$", "Suite manifest must be an object.")
        return _finish(issues, {})
    if data.get("schema_version") != 1:
        _issue(issues, "suites.schema_version", "$.schema_version",
               "schema_version must be 1.")
    suites = data.get("suites")
    if not isinstance(suites, list) or not suites:
        _issue(issues, "suites.not_array", "$.suites", "suites must be a non-empty array.")
        suites = []

    seen: set[str] = set()
    live_count = 0
    offline_count = 0
    referenced_cases: set[str] = set()
    for index, suite in enumerate(suites):
        path = f"$.suites[{index}]"
        if not isinstance(suite, dict):
            _issue(issues, "suite.not_object", path, "Suite must be an object.")
            continue
        suite_id = suite.get("id")
        if not _text(suite_id) or not ID_RE.fullmatch(suite_id):
            _issue(issues, "suite.invalid_id", f"{path}.id",
                   "id must be a lowercase hyphenated identifier.")
        elif suite_id in seen:
            _issue(issues, "suite.duplicate_id", f"{path}.id", f"Duplicate suite: {suite_id}")
        else:
            seen.add(suite_id)
        for field in ("title", "purpose", "source_access"):
            if not _text(suite.get(field)):
                _issue(issues, f"suite.missing_{field}", f"{path}.{field}",
                       f"{field} is required.")

        case_ids = suite.get("case_ids")
        if not isinstance(case_ids, list) or not case_ids or not all(_text(x) for x in case_ids):
            _issue(issues, "suite.invalid_cases", f"{path}.case_ids",
                   "case_ids must be a non-empty string array.")
            case_ids = []
        if len(case_ids) != len(set(case_ids)):
            _issue(issues, "suite.duplicate_case", f"{path}.case_ids",
                   "A suite cannot repeat a case ID; use repeats for repeated runs.")
        unknown = sorted(set(case_ids) - set(cases))
        if unknown:
            _issue(issues, "suite.unknown_case", f"{path}.case_ids",
                   f"Unknown catalog cases: {unknown}")
        referenced_cases.update(set(case_ids) & set(cases))

        modes = suite.get("modes")
        if not isinstance(modes, list) or not modes or not all(_text(x) for x in modes):
            _issue(issues, "suite.invalid_modes", f"{path}.modes",
                   "modes must be a non-empty string array.")
            modes = []
        if len(modes) != len(set(modes)):
            _issue(issues, "suite.duplicate_mode", f"{path}.modes",
                   "modes must not contain duplicates.")
        invalid_modes = sorted(set(modes) - ALLOWED_MODES)
        if invalid_modes:
            _issue(issues, "suite.unknown_mode", f"{path}.modes",
                   f"Unknown modes: {invalid_modes}")

        repeats = suite.get("repeats")
        if not isinstance(repeats, int) or isinstance(repeats, bool) or not 1 <= repeats <= 10:
            _issue(issues, "suite.invalid_repeats", f"{path}.repeats",
                   "repeats must be an integer from 1 to 10.")
        live_web = suite.get("live_web")
        if not isinstance(live_web, bool):
            _issue(issues, "suite.invalid_live_web", f"{path}.live_web",
                   "live_web must be true or false.")
        elif live_web:
            live_count += 1
        else:
            offline_count += 1
            missing_fixtures = sorted(
                case_id for case_id in case_ids
                if case_id in cases
                and cases[case_id].get("should_trigger")
                and not _text(cases[case_id].get("fixture"))
            )
            if missing_fixtures:
                _issue(issues, "suite.offline_trigger_without_fixture", f"{path}.case_ids",
                       f"Offline trigger cases require fixtures: {missing_fixtures}")

    summary = {
        "suite_count": len(suites),
        "live_suite_count": live_count,
        "offline_suite_count": offline_count,
        "referenced_case_count": len(referenced_cases),
    }
    return _finish(issues, summary)


def _finish(issues: list[dict[str, str]], summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "verdict": "PASS" if not issues else "FAIL",
        "error_count": len(issues),
        "summary": summary,
        "issues": issues,
        "scope_note": (
            "Suite validation checks structure and declared isolation only; "
            "it does not run models."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate evaluation suite manifests.")
    parser.add_argument("suites", type=Path, nargs="?", default=Path("evals/suites.json"))
    parser.add_argument("--catalog", type=Path, default=Path("evals/cases.json"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.suites.read_text(encoding="utf-8"))
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: could not read input: {exc}", file=sys.stderr)
        return 2
    result = validate_suites(data, catalog)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"{result['verdict']}: {result['summary'].get('suite_count', 0)} suites, "
              f"{result['error_count']} errors")
        for issue in result["issues"]:
            print(f"- ERROR {issue['code']} {issue['path']}: {issue['message']}")
        print(result["scope_note"])
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
