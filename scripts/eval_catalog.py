"""Validate the forward-evaluation catalog without running model evaluations."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ALLOWED_CATEGORIES = {
    "academic", "adversarial", "market", "medical", "policy", "routing",
    "technical",
}
ALLOWED_RISKS = {"low", "medium", "high"}
REQUIRED_CATEGORIES = ALLOWED_CATEGORIES
REQUIRED_TAGS = {
    "authorization",
    "conflicting-sources",
    "current",
    "duplicate-evidence",
    "insufficient-evidence",
    "non-trigger",
    "primary-sources",
    "prompt-injection",
    "transfer-limits",
    "unavailable-source",
}
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _add(issues: list[dict[str, str]], severity: str, code: str,
         path: str, message: str) -> None:
    issues.append({
        "severity": severity,
        "code": code,
        "path": path,
        "message": message,
    })


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _text_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_text(item) for item in value)


def validate_catalog(data: Any, *, strict: bool = False) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not isinstance(data, dict):
        _add(issues, "error", "catalog.not_object", "$",
             "The catalog must be a JSON object.")
        return _finish(issues, [], strict)

    if data.get("schema_version") != 1:
        _add(issues, "error", "catalog.schema_version", "$.schema_version",
             "schema_version must be 1.")

    minimum = data.get("minimum_cases", 15)
    if not isinstance(minimum, int) or minimum < 15:
        _add(issues, "error", "catalog.minimum_cases", "$.minimum_cases",
             "minimum_cases must be an integer of at least 15.")
        minimum = 15

    cases = data.get("cases")
    if not isinstance(cases, list):
        _add(issues, "error", "cases.not_array", "$.cases",
             "cases must be an array.")
        cases = []
    if len(cases) < minimum:
        _add(issues, "error", "cases.too_few", "$.cases",
             f"Expected at least {minimum} cases; found {len(cases)}.")

    ids: set[str] = set()
    prompts: set[str] = set()
    categories: set[str] = set()
    tags: set[str] = set()
    trigger_count = 0
    non_trigger_count = 0
    adversarial_count = 0
    high_risk_count = 0

    for index, case in enumerate(cases):
        path = f"$.cases[{index}]"
        if not isinstance(case, dict):
            _add(issues, "error", "case.not_object", path,
                 "Each case must be an object.")
            continue

        case_id = case.get("id")
        if not _text(case_id) or not ID_PATTERN.fullmatch(case_id):
            _add(issues, "error", "case.invalid_id", f"{path}.id",
                 "id must be lowercase kebab-case.")
        elif case_id in ids:
            _add(issues, "error", "case.duplicate_id", f"{path}.id",
                 f"Duplicate case id: {case_id}")
        else:
            ids.add(case_id)

        if not _text(case.get("title")):
            _add(issues, "error", "case.missing_title", f"{path}.title",
                 "title is required.")
        prompt = case.get("prompt")
        if not _text(prompt):
            _add(issues, "error", "case.missing_prompt", f"{path}.prompt",
                 "prompt is required.")
        else:
            normalized = " ".join(prompt.split()).casefold()
            if normalized in prompts:
                _add(issues, "error", "case.duplicate_prompt", f"{path}.prompt",
                     "Prompts must be unique.")
            prompts.add(normalized)

        category = case.get("category")
        if category not in ALLOWED_CATEGORIES:
            _add(issues, "error", "case.invalid_category", f"{path}.category",
                 f"category must be one of {sorted(ALLOWED_CATEGORIES)}.")
        else:
            categories.add(category)
            if category == "adversarial":
                adversarial_count += 1

        risk = case.get("risk")
        if risk not in ALLOWED_RISKS:
            _add(issues, "error", "case.invalid_risk", f"{path}.risk",
                 "risk must be low, medium, or high.")
        elif risk == "high":
            high_risk_count += 1

        should_trigger = case.get("should_trigger")
        if not isinstance(should_trigger, bool):
            _add(issues, "error", "case.invalid_trigger", f"{path}.should_trigger",
                 "should_trigger must be boolean.")
        elif should_trigger:
            trigger_count += 1
        else:
            non_trigger_count += 1
            if category != "routing":
                _add(issues, "warning", "case.non_trigger_category", path,
                     "Non-trigger cases should normally use the routing category.")

        for field in ("expected_behaviors", "forbidden_behaviors", "tags"):
            if not _text_list(case.get(field)):
                _add(issues, "error", f"case.invalid_{field}", f"{path}.{field}",
                     f"{field} must be a non-empty array of non-empty strings.")
        if isinstance(case.get("tags"), list):
            tags.update(tag for tag in case["tags"] if _text(tag))

    missing_categories = sorted(REQUIRED_CATEGORIES - categories)
    if missing_categories:
        _add(issues, "error", "coverage.categories", "$.cases",
             f"Missing required categories: {missing_categories}")
    missing_tags = sorted(REQUIRED_TAGS - tags)
    if missing_tags:
        _add(issues, "error", "coverage.tags", "$.cases",
             f"Missing required evaluation tags: {missing_tags}")
    if non_trigger_count < 3:
        _add(issues, "error", "coverage.non_trigger", "$.cases",
             "At least three non-trigger routing cases are required.")
    if adversarial_count < 5:
        _add(issues, "error", "coverage.adversarial", "$.cases",
             "At least five adversarial cases are required.")
    if high_risk_count < 5:
        _add(issues, "error", "coverage.high_risk", "$.cases",
             "At least five high-risk cases are required.")

    summary = {
        "case_count": len(cases),
        "trigger_count": trigger_count,
        "non_trigger_count": non_trigger_count,
        "adversarial_count": adversarial_count,
        "high_risk_count": high_risk_count,
        "categories": sorted(categories),
        "tags": sorted(tags),
    }
    return _finish(issues, cases, strict, summary)


def _finish(issues: list[dict[str, str]], cases: list[Any], strict: bool,
            summary: dict[str, Any] | None = None) -> dict[str, Any]:
    errors = sum(item["severity"] == "error" for item in issues)
    warnings = sum(item["severity"] == "warning" for item in issues)
    passed = errors == 0 and (warnings == 0 or not strict)
    return {
        "verdict": "PASS" if passed else "FAIL",
        "strict": strict,
        "error_count": errors,
        "warning_count": warnings,
        "summary": summary or {"case_count": len(cases)},
        "issues": issues,
        "scope_note": "Catalog validation only; no model evaluation was run.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the Evidence Deep Research evaluation catalog."
    )
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings as validation failures")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args(argv)

    if not args.catalog.is_file():
        print(f"ERROR: catalog not found: {args.catalog}", file=sys.stderr)
        return 2
    try:
        with args.catalog.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: could not read catalog: {exc}", file=sys.stderr)
        return 2

    result = validate_catalog(data, strict=args.strict)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        summary = result["summary"]
        print(
            f"{result['verdict']}: {summary['case_count']} cases, "
            f"{result['error_count']} errors, {result['warning_count']} warnings"
        )
        for issue in result["issues"]:
            print(
                f"- {issue['severity'].upper()} {issue['code']} "
                f"{issue['path']}: {issue['message']}"
            )
        print(result["scope_note"])
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
