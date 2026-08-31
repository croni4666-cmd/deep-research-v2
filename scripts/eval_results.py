"""Validate and summarize case-level deep-research evaluation results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ALLOWED_MODES = {"builtin", "combined", "evidence"}
ALLOWED_STATUSES = {"blocked", "completed", "not_evaluated"}
METRIC_FIELDS = {
    "output_word_count",
    "source_count",
    "primary_source_count",
    "citation_sample_size",
    "citation_sample_supported",
    "unsupported_claims_in_sample",
    "key_claim_count",
    "supported_key_claim_count",
    "unresolved_key_claim_count",
}
AUTOMATIC_METRIC_FIELDS = {"output_word_count", "source_count"}
ALLOWED_METRIC_PROVENANCE = {"automatic", "human"}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _issue(issues: list[dict[str, str]], code: str, path: str, message: str) -> None:
    issues.append({"code": code, "path": path, "message": message})


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _http_url(value: Any) -> bool:
    if not _text(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _load_catalog_cases(catalog: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(catalog, dict) or not isinstance(catalog.get("cases"), list):
        return {}
    return {
        case["id"]: case
        for case in catalog["cases"]
        if isinstance(case, dict) and _text(case.get("id"))
    }


def _validate_artifact_record(
    value: Any, path: str, issues: list[dict[str, str]],
) -> None:
    if not isinstance(value, dict):
        _issue(issues, "result.missing_artifact", path, "Artifact metadata is required.")
        return
    if not _text(value.get("path")):
        _issue(issues, "result.invalid_artifact_path", f"{path}.path",
               "Artifact path is required.")
    if not isinstance(value.get("sha256"), str) or not SHA256_PATTERN.fullmatch(
        value["sha256"]
    ):
        _issue(issues, "result.invalid_artifact_hash", f"{path}.sha256",
               "Artifact sha256 must be 64 lowercase hexadecimal characters.")


def _validate_metric_provenance(
    value: Any, path: str, issues: list[dict[str, str]],
) -> None:
    if not isinstance(value, dict):
        _issue(issues, "case.missing_metric_provenance", path,
               "Schema v2 cases require metric provenance.")
        return
    missing = sorted(METRIC_FIELDS - set(value))
    extra = sorted(set(value) - METRIC_FIELDS)
    if missing or extra:
        _issue(issues, "case.metric_provenance_mismatch", path,
               f"Metric provenance differs from metrics; missing={missing}, extra={extra}.")
    for field, source in value.items():
        if field in METRIC_FIELDS and source not in ALLOWED_METRIC_PROVENANCE:
            _issue(issues, "case.invalid_metric_provenance", f"{path}.{field}",
                   f"Provenance must be one of {sorted(ALLOWED_METRIC_PROVENANCE)}.")
    for field in AUTOMATIC_METRIC_FIELDS:
        if value.get(field) != "automatic":
            _issue(issues, "case.automatic_metric_not_marked", f"{path}.{field}",
                   f"{field} must be marked automatic in schema v2.")


def _validate_behavior_results(
    results: Any,
    expected: list[str],
    path: str,
    completed: bool,
    issues: list[dict[str, str]],
) -> tuple[int, int]:
    if not isinstance(results, list):
        _issue(issues, "case.behaviors_not_array", path, "Behavior results must be an array.")
        return 0, 0
    observed_by_behavior: dict[str, Any] = {}
    for index, item in enumerate(results):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict) or not _text(item.get("behavior")):
            _issue(issues, "case.invalid_behavior", item_path, "behavior is required.")
            continue
        behavior = item["behavior"]
        if behavior in observed_by_behavior:
            _issue(issues, "case.duplicate_behavior", item_path, f"Duplicate: {behavior}")
        observed = item.get("observed")
        if observed is not None and not isinstance(observed, bool):
            _issue(issues, "case.invalid_observed", f"{item_path}.observed",
                   "observed must be true, false, or null.")
        if completed and not isinstance(observed, bool):
            _issue(issues, "case.completed_behavior_unscored", f"{item_path}.observed",
                   "Completed cases must score every behavior.")
        if completed and not _text(item.get("note")):
            _issue(issues, "case.completed_behavior_missing_note", f"{item_path}.note",
                   "Completed behavior judgments require a reviewer note.")
        observed_by_behavior[behavior] = observed
    if set(observed_by_behavior) != set(expected):
        missing = sorted(set(expected) - set(observed_by_behavior))
        extra = sorted(set(observed_by_behavior) - set(expected))
        _issue(issues, "case.behavior_mismatch", path,
               f"Behavior set differs from catalog; missing={missing}, extra={extra}.")
    scored = sum(isinstance(value, bool) for value in observed_by_behavior.values())
    passed = sum(value is True for value in observed_by_behavior.values())
    return scored, passed


def _validate_metrics(
    metrics: Any,
    path: str,
    completed: bool,
    source_count: int | None,
    issues: list[dict[str, str]],
) -> dict[str, int]:
    if not isinstance(metrics, dict):
        if completed:
            _issue(issues, "case.completed_metrics_missing", path,
                   "Completed cases require comparable output and review metrics.")
        return {}
    values: dict[str, int] = {}
    for field in sorted(METRIC_FIELDS):
        value = metrics.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            _issue(issues, "case.invalid_metric", f"{path}.{field}",
                   f"{field} must be a non-negative integer.")
            continue
        values[field] = value
    extra = sorted(set(metrics) - METRIC_FIELDS)
    if extra:
        _issue(issues, "case.unknown_metric", path, f"Unknown metrics: {extra}")
    if completed and values.get("output_word_count", 0) == 0:
        _issue(issues, "case.empty_output_metric", f"{path}.output_word_count",
               "Completed cases must record a non-empty final answer.")
    if source_count is not None and values.get("source_count", 0) < source_count:
        _issue(issues, "case.source_count_mismatch", f"{path}.source_count",
               "source_count cannot be smaller than the retained sources array length.")
    if values.get("primary_source_count", 0) > values.get("source_count", 0):
        _issue(issues, "case.primary_source_count_exceeds_sources", path,
               "primary_source_count cannot exceed source_count.")
    if values.get("citation_sample_supported", 0) > values.get("citation_sample_size", 0):
        _issue(issues, "case.citation_sample_inconsistent", path,
               "citation_sample_supported cannot exceed citation_sample_size.")
    classified_claims = (
        values.get("supported_key_claim_count", 0)
        + values.get("unresolved_key_claim_count", 0)
    )
    if classified_claims > values.get("key_claim_count", 0):
        _issue(issues, "case.key_claim_counts_inconsistent", path,
               "Supported plus unresolved key claims cannot exceed key_claim_count.")
    return values


def validate_results(data: Any, catalog: Any, *, allow_partial: bool = False) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    catalog_cases = _load_catalog_cases(catalog)
    if not isinstance(data, dict):
        _issue(issues, "result.not_object", "$", "Result must be a JSON object.")
        return _finish(issues, {})
    schema_version = data.get("schema_version")
    if schema_version not in {1, 2}:
        _issue(issues, "result.schema_version", "$.schema_version",
               "schema_version must be 1 or 2.")

    run = data.get("run")
    if not isinstance(run, dict):
        _issue(issues, "run.not_object", "$.run", "run metadata is required.")
        run = {}
    for field in ("id", "date", "model", "prompt_revision", "source_access"):
        if not _text(run.get(field)):
            _issue(issues, f"run.missing_{field}", f"$.run.{field}", f"{field} is required.")
    try:
        date.fromisoformat(run.get("date", ""))
    except (TypeError, ValueError):
        _issue(issues, "run.invalid_date", "$.run.date", "date must use YYYY-MM-DD.")
    if run.get("mode") not in ALLOWED_MODES:
        _issue(issues, "run.invalid_mode", "$.run.mode",
               f"mode must be one of {sorted(ALLOWED_MODES)}.")
    if not isinstance(run.get("tools"), list) or not all(_text(x) for x in run.get("tools", [])):
        _issue(issues, "run.invalid_tools", "$.run.tools", "tools must be a string array.")
    if schema_version == 2:
        if not _text(run.get("suite_id")):
            _issue(issues, "run.missing_suite_id", "$.run.suite_id",
                   "Schema v2 runs require suite_id.")
        repeat = run.get("repeat")
        if not isinstance(repeat, int) or isinstance(repeat, bool) or repeat < 1:
            _issue(issues, "run.invalid_repeat", "$.run.repeat",
                   "Schema v2 repeat must be a positive integer.")
        artifacts = data.get("artifacts")
        if not isinstance(artifacts, dict):
            _issue(issues, "result.missing_artifacts", "$.artifacts",
                   "Schema v2 artifact metadata is required.")
            artifacts = {}
        for name in ("bundle_manifest", "raw_output", "metric_extraction"):
            _validate_artifact_record(artifacts.get(name), f"$.artifacts.{name}", issues)

    cases = data.get("cases")
    if not isinstance(cases, list):
        _issue(issues, "cases.not_array", "$.cases", "cases must be an array.")
        cases = []
    seen: set[str] = set()
    completed = 0
    blocked = 0
    behavior_scored = 0
    expected_passed = 0
    forbidden_avoided = 0
    output_words = 0
    reported_sources = 0
    citation_sample_size = 0
    citation_sample_supported = 0
    for index, result in enumerate(cases):
        path = f"$.cases[{index}]"
        if not isinstance(result, dict) or result.get("id") not in catalog_cases:
            _issue(issues, "case.unknown_id", f"{path}.id", "Case id must exist in the catalog.")
            continue
        case_id = result["id"]
        if case_id in seen:
            _issue(issues, "case.duplicate_id", f"{path}.id", f"Duplicate case: {case_id}")
        seen.add(case_id)
        case = catalog_cases[case_id]
        status = result.get("status")
        if status not in ALLOWED_STATUSES:
            _issue(issues, "case.invalid_status", f"{path}.status",
                   f"status must be one of {sorted(ALLOWED_STATUSES)}.")
        is_completed = status == "completed"
        completed += is_completed
        blocked += status == "blocked"
        if result.get("expected_trigger") is not case.get("should_trigger"):
            _issue(issues, "case.trigger_mismatch", f"{path}.expected_trigger",
                   "expected_trigger must match the catalog.")
        actual_trigger = result.get("actual_trigger")
        if actual_trigger is not None and not isinstance(actual_trigger, bool):
            _issue(issues, "case.invalid_actual_trigger", f"{path}.actual_trigger",
                   "actual_trigger must be true, false, or null.")
        if is_completed and not isinstance(actual_trigger, bool):
            _issue(issues, "case.completed_trigger_unscored", f"{path}.actual_trigger",
                   "Completed cases must score routing.")

        scored, passed = _validate_behavior_results(
            result.get("expected_behavior_results"), case["expected_behaviors"],
            f"{path}.expected_behavior_results", is_completed, issues,
        )
        behavior_scored += scored
        expected_passed += passed
        scored, observed = _validate_behavior_results(
            result.get("forbidden_behavior_results"), case["forbidden_behaviors"],
            f"{path}.forbidden_behavior_results", is_completed, issues,
        )
        behavior_scored += scored
        forbidden_avoided += scored - observed

        sources = result.get("sources")
        case_source_count: int | None = len(sources) if isinstance(sources, list) else None
        if not isinstance(sources, list):
            _issue(issues, "case.sources_not_array", f"{path}.sources", "sources must be an array.")
        elif is_completed:
            if case.get("should_trigger") and not sources:
                _issue(issues, "case.completed_research_without_sources", f"{path}.sources",
                       "Completed trigger cases must retain their inspected sources.")
            for source_index, source in enumerate(sources):
                source_path = f"{path}.sources[{source_index}]"
                if not isinstance(source, dict) or not all(
                    _text(source.get(field)) for field in ("title", "publisher", "date", "url")
                ):
                    _issue(issues, "case.invalid_source", source_path,
                           "Each source needs title, publisher, date, and url.")
                    continue
                try:
                    date.fromisoformat(source["date"])
                except ValueError:
                    _issue(issues, "case.invalid_source_date", f"{source_path}.date",
                           "Source dates must use YYYY-MM-DD.")
                if not _http_url(source["url"]):
                    _issue(issues, "case.invalid_source_url", f"{source_path}.url",
                           "Source URLs must be absolute http or https URLs.")
        metrics = _validate_metrics(
            result.get("metrics"), f"{path}.metrics", is_completed,
            case_source_count, issues,
        )
        if schema_version == 2:
            _validate_metric_provenance(
                result.get("metric_provenance"), f"{path}.metric_provenance", issues,
            )
            checks = result.get("automatic_checks")
            duplicate_count = checks.get("duplicate_table_row_count") \
                if isinstance(checks, dict) else None
            if not isinstance(duplicate_count, int) or isinstance(duplicate_count, bool) \
                    or duplicate_count < 0:
                _issue(issues, "case.invalid_automatic_checks", f"{path}.automatic_checks",
                       "Schema v2 requires a non-negative duplicate_table_row_count.")
        output_words += metrics.get("output_word_count", 0)
        reported_sources += metrics.get("source_count", 0)
        citation_sample_size += metrics.get("citation_sample_size", 0)
        citation_sample_supported += metrics.get("citation_sample_supported", 0)
        if not _text(result.get("notes")):
            _issue(issues, "case.missing_notes", f"{path}.notes", "Reviewer notes are required.")

    if not allow_partial and set(catalog_cases) != seen:
        missing = sorted(set(catalog_cases) - seen)
        _issue(issues, "cases.partial_run", "$.cases", f"Missing catalog cases: {missing}")
    summary = {
        "case_count": len(cases),
        "completed_count": completed,
        "blocked_count": blocked,
        "behavior_scores_recorded": behavior_scored,
        "expected_behaviors_observed": expected_passed,
        "forbidden_behaviors_avoided": forbidden_avoided,
        "output_words": output_words,
        "reported_sources": reported_sources,
        "citation_sample_size": citation_sample_size,
        "citation_sample_supported": citation_sample_supported,
        "partial": set(catalog_cases) != seen,
    }
    return _finish(issues, summary)


def _finish(issues: list[dict[str, str]], summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "verdict": "PASS" if not issues else "FAIL",
        "error_count": len(issues),
        "summary": summary,
        "issues": issues,
        "scope_note": (
            "Structural and catalog-consistency validation only; scores remain "
            "human judgments."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an evaluation result file.")
    parser.add_argument("result", type=Path)
    parser.add_argument("--catalog", type=Path, default=Path("evals/cases.json"))
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.result.read_text(encoding="utf-8"))
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: could not read input: {exc}", file=sys.stderr)
        return 2
    result = validate_results(data, catalog, allow_partial=args.allow_partial)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"{result['verdict']}: {result['summary'].get('case_count', 0)} cases, "
              f"{result['error_count']} errors")
        for issue in result["issues"]:
            print(f"- ERROR {issue['code']} {issue['path']}: {issue['message']}")
        print(result["scope_note"])
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
