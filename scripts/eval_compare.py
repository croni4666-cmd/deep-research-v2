"""Compare structurally valid, compatible deep-research evaluation runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__:
    from .eval_results import validate_results
else:
    from eval_results import validate_results

FINGERPRINT_FIELDS = ("model", "prompt_revision", "source_access")


def _issue(issues: list[dict[str, str]], code: str, path: str, message: str) -> None:
    issues.append({"code": code, "path": path, "message": message})


def _completed_cases(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [case for case in data.get("cases", []) if case.get("status") == "completed"]


def _aggregate(data: dict[str, Any]) -> dict[str, Any]:
    completed = _completed_cases(data)
    expected_total = 0
    expected_passed = 0
    forbidden_total = 0
    forbidden_avoided = 0
    metric_totals = {
        "output_word_count": 0,
        "source_count": 0,
        "citation_sample_size": 0,
        "citation_sample_supported": 0,
        "unsupported_claims_in_sample": 0,
        "key_claim_count": 0,
        "supported_key_claim_count": 0,
        "unresolved_key_claim_count": 0,
    }
    for case in completed:
        expected = case.get("expected_behavior_results", [])
        forbidden = case.get("forbidden_behavior_results", [])
        expected_total += len(expected)
        expected_passed += sum(item.get("observed") is True for item in expected)
        forbidden_total += len(forbidden)
        forbidden_avoided += sum(item.get("observed") is False for item in forbidden)
        metrics = case.get("metrics", {})
        for field in metric_totals:
            metric_totals[field] += metrics.get(field, 0)
    sample_size = metric_totals["citation_sample_size"]
    sample_supported = metric_totals["citation_sample_supported"]
    return {
        "run_id": data["run"]["id"],
        "mode": data["run"]["mode"],
        "completed_case_count": len(completed),
        "expected_behaviors": {"passed": expected_passed, "total": expected_total},
        "forbidden_behaviors": {"avoided": forbidden_avoided, "total": forbidden_total},
        "desired_behaviors": {
            "passed": expected_passed + forbidden_avoided,
            "total": expected_total + forbidden_total,
        },
        **metric_totals,
        "citation_sample_support_rate": (
            sample_supported / sample_size if sample_size else None
        ),
    }


def compare_results(runs: list[Any], catalog: Any) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if len(runs) < 2:
        _issue(issues, "compare.too_few_runs", "$.runs",
               "At least two result files are required.")
    valid_runs: list[dict[str, Any]] = []
    for index, run in enumerate(runs):
        validation = validate_results(run, catalog, allow_partial=True)
        if validation["verdict"] != "PASS":
            _issue(issues, "compare.invalid_result", f"$.runs[{index}]",
                   f"Result validation failed: {validation['issues']}")
        elif isinstance(run, dict):
            valid_runs.append(run)

    if valid_runs:
        modes = [run["run"]["mode"] for run in valid_runs]
        if len(modes) != len(set(modes)):
            _issue(issues, "compare.duplicate_mode", "$.runs",
                   "Paired comparisons require one result per mode.")
        baseline = valid_runs[0]["run"]
        for index, run in enumerate(valid_runs[1:], start=1):
            for field in FINGERPRINT_FIELDS:
                if run["run"].get(field) != baseline.get(field):
                    _issue(
                        issues,
                        "compare.fingerprint_mismatch",
                        f"$.runs[{index}].run.{field}",
                        f"{field} differs from the first run.",
                    )
        baseline_cases = {case["id"] for case in _completed_cases(valid_runs[0])}
        if not baseline_cases:
            _issue(issues, "compare.no_completed_cases", "$.runs[0].cases",
                   "The first result has no completed cases.")
        for index, run in enumerate(valid_runs[1:], start=1):
            case_ids = {case["id"] for case in _completed_cases(run)}
            if case_ids != baseline_cases:
                _issue(
                    issues,
                    "compare.case_set_mismatch",
                    f"$.runs[{index}].cases",
                    f"Completed case set differs; expected={sorted(baseline_cases)}, "
                    f"observed={sorted(case_ids)}.",
                )

    summaries = [_aggregate(run) for run in valid_runs]
    fingerprint = {
        field: valid_runs[0]["run"].get(field) if valid_runs else None
        for field in FINGERPRINT_FIELDS
    }
    return {
        "verdict": "PASS" if not issues else "FAIL",
        "error_count": len(issues),
        "compatible": not issues,
        "fingerprint": fingerprint,
        "case_ids": (
            sorted(case["id"] for case in _completed_cases(valid_runs[0]))
            if valid_runs else []
        ),
        "runs": summaries,
        "issues": issues,
        "scope_note": (
            "This report aggregates recorded reviewer judgments and metrics. "
            "It does not prove truth, citation entailment, or a single winning mode."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare compatible evaluation results.")
    parser.add_argument("results", type=Path, nargs="+")
    parser.add_argument("--catalog", type=Path, default=Path("evals/cases.json"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        runs = [json.loads(path.read_text(encoding="utf-8")) for path in args.results]
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: could not read input: {exc}", file=sys.stderr)
        return 2
    result = compare_results(runs, catalog)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"{result['verdict']}: {len(result['runs'])} runs, "
              f"{result['error_count']} compatibility errors")
        for run in result["runs"]:
            desired = run["desired_behaviors"]
            print(
                f"- {run['mode']}: desired={desired['passed']}/{desired['total']}, "
                f"words={run['output_word_count']}, sources={run['source_count']}, "
                f"citation_sample={run['citation_sample_supported']}/"
                f"{run['citation_sample_size']}"
            )
        for issue in result["issues"]:
            print(f"- ERROR {issue['code']} {issue['path']}: {issue['message']}")
        print(result["scope_note"])
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
