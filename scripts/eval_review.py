"""Prepare, compare, and adjudicate blinded human evaluation reviews."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

if __package__:
    from .eval_ingest import sha256_file, write_report
else:
    from eval_ingest import sha256_file, write_report

HUMAN_METRIC_FIELDS = {
    "primary_source_count",
    "citation_sample_size",
    "citation_sample_supported",
    "unsupported_claims_in_sample",
    "key_claim_count",
    "supported_key_claim_count",
    "unresolved_key_claim_count",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
MODE_PATH_PATTERN = re.compile(
    r"(?:^|[/_.-])(builtin|evidence|combined)(?:$|[/_.-])", re.IGNORECASE,
)


def _mode_revealing_path(path: str | Path, case_ids: list[str] | tuple[str, ...]) -> bool:
    """Ignore exact case-id path segments while still rejecting candidate mode labels."""
    known_cases = {case_id.lower() for case_id in case_ids}
    parts = re.split(r"[/\\]+", str(path))
    anonymized = [
        "case-id" if part.lower() in known_cases else part
        for part in parts
    ]
    return MODE_PATH_PATTERN.search("/".join(anonymized)) is not None


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _issue(issues: list[dict[str, str]], code: str, path: str, message: str) -> None:
    issues.append({"code": code, "path": path, "message": message})


def _catalog_cases(catalog: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(catalog, dict) or not isinstance(catalog.get("cases"), list):
        return {}
    return {
        case["id"]: case
        for case in catalog["cases"]
        if isinstance(case, dict) and _text(case.get("id"))
    }


def prepare_review(
    *, catalog: Any, raw_path: Path, reviewer_id: str, case_ids: list[str],
    reviewed_on: str,
) -> dict[str, Any]:
    cases = _catalog_cases(catalog)
    if not _text(reviewer_id):
        raise ValueError("reviewer_id is required.")
    if _mode_revealing_path(raw_path, case_ids):
        raise ValueError("Raw review artifact path reveals the candidate mode; anonymize it first.")
    try:
        date.fromisoformat(reviewed_on)
    except ValueError as exc:
        raise ValueError("reviewed_on must use YYYY-MM-DD.") from exc
    if not case_ids or len(case_ids) != len(set(case_ids)):
        raise ValueError("case_ids must be a non-empty unique list.")
    unknown = sorted(set(case_ids) - set(cases))
    if unknown:
        raise ValueError(f"Unknown case IDs: {unknown}")
    review_cases = []
    for case_id in case_ids:
        case = cases[case_id]
        review_cases.append({
            "id": case_id,
            "actual_trigger": None,
            "expected_behavior_results": [
                {"behavior": behavior, "observed": None, "note": ""}
                for behavior in case["expected_behaviors"]
            ],
            "forbidden_behavior_results": [
                {"behavior": behavior, "observed": None, "note": ""}
                for behavior in case["forbidden_behaviors"]
            ],
            "human_metrics": {field: None for field in sorted(HUMAN_METRIC_FIELDS)},
            "notes": "",
        })
    return {
        "schema_version": 1,
        "review": {
            "reviewer_id": reviewer_id,
            "reviewed_on": reviewed_on,
            "blinded_to_mode": True,
            "raw_output": {"path": raw_path.as_posix(), "sha256": sha256_file(raw_path)},
        },
        "cases": review_cases,
        "scope_note": (
            "Complete this review independently without viewing another reviewer's scores. "
            "Automatic metrics are intentionally excluded."
        ),
    }


def _validate_behavior_results(
    value: Any, expected: list[str], path: str, complete: bool,
    issues: list[dict[str, str]],
) -> None:
    if not isinstance(value, list):
        _issue(issues, "review.behaviors_not_array", path, "Behavior results must be an array.")
        return
    observed: dict[str, Any] = {}
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict) or not _text(item.get("behavior")):
            _issue(issues, "review.invalid_behavior", item_path, "behavior is required.")
            continue
        behavior = item["behavior"]
        if behavior in observed:
            _issue(issues, "review.duplicate_behavior", item_path, f"Duplicate: {behavior}")
        judgment = item.get("observed")
        if judgment is not None and not isinstance(judgment, bool):
            _issue(issues, "review.invalid_observed", f"{item_path}.observed",
                   "observed must be true, false, or null.")
        if complete and not isinstance(judgment, bool):
            _issue(issues, "review.unscored_behavior", f"{item_path}.observed",
                   "A completed review must score every behavior.")
        if complete and not _text(item.get("note")):
            _issue(issues, "review.missing_behavior_note", f"{item_path}.note",
                   "A completed judgment requires a note.")
        observed[behavior] = judgment
    if set(observed) != set(expected):
        _issue(issues, "review.behavior_mismatch", path,
               f"Behavior set differs; missing={sorted(set(expected) - set(observed))}, "
               f"extra={sorted(set(observed) - set(expected))}.")


def validate_review(
    data: Any, catalog: Any, *, require_complete: bool = False,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    cases_by_id = _catalog_cases(catalog)
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        _issue(issues, "review.schema_version", "$.schema_version",
               "Review schema_version must be 1.")
        return _finish(issues, {})
    metadata = data.get("review")
    if not isinstance(metadata, dict):
        _issue(issues, "review.missing_metadata", "$.review", "Review metadata is required.")
        metadata = {}
    if not _text(metadata.get("reviewer_id")):
        _issue(issues, "review.missing_reviewer", "$.review.reviewer_id",
               "reviewer_id is required.")
    try:
        date.fromisoformat(metadata.get("reviewed_on", ""))
    except (TypeError, ValueError):
        _issue(issues, "review.invalid_date", "$.review.reviewed_on",
               "reviewed_on must use YYYY-MM-DD.")
    if metadata.get("blinded_to_mode") is not True:
        _issue(issues, "review.not_blinded", "$.review.blinded_to_mode",
               "Independent review requires blinded_to_mode=true.")
    raw = metadata.get("raw_output")
    if not isinstance(raw, dict) or not _text(raw.get("path")) or not isinstance(
        raw.get("sha256"), str
    ) or not SHA256_PATTERN.fullmatch(raw["sha256"]):
        _issue(issues, "review.invalid_raw_artifact", "$.review.raw_output",
               "Raw output requires path and a 64-character sha256.")
    elif _mode_revealing_path(
        raw["path"],
        [
            item.get("id", "")
            for item in data.get("cases", [])
            if isinstance(item, dict) and _text(item.get("id"))
        ],
    ):
        _issue(issues, "review.mode_leaking_path", "$.review.raw_output.path",
               "Raw review artifact path must not reveal builtin, evidence, or combined mode.")

    review_cases = data.get("cases")
    if not isinstance(review_cases, list) or not review_cases:
        _issue(issues, "review.invalid_cases", "$.cases", "cases must be a non-empty array.")
        review_cases = []
    seen: set[str] = set()
    for index, review_case in enumerate(review_cases):
        path = f"$.cases[{index}]"
        if not isinstance(review_case, dict) or review_case.get("id") not in cases_by_id:
            _issue(issues, "review.unknown_case", f"{path}.id",
                   "Case id must exist in the catalog.")
            continue
        case_id = review_case["id"]
        if case_id in seen:
            _issue(issues, "review.duplicate_case", f"{path}.id", f"Duplicate: {case_id}")
        seen.add(case_id)
        catalog_case = cases_by_id[case_id]
        trigger = review_case.get("actual_trigger")
        if trigger is not None and not isinstance(trigger, bool):
            _issue(issues, "review.invalid_trigger", f"{path}.actual_trigger",
                   "actual_trigger must be true, false, or null.")
        if require_complete and not isinstance(trigger, bool):
            _issue(issues, "review.unscored_trigger", f"{path}.actual_trigger",
                   "A completed review must score routing.")
        _validate_behavior_results(
            review_case.get("expected_behavior_results"),
            catalog_case["expected_behaviors"],
            f"{path}.expected_behavior_results", require_complete, issues,
        )
        _validate_behavior_results(
            review_case.get("forbidden_behavior_results"),
            catalog_case["forbidden_behaviors"],
            f"{path}.forbidden_behavior_results", require_complete, issues,
        )
        metrics = review_case.get("human_metrics")
        if not isinstance(metrics, dict) or set(metrics) != HUMAN_METRIC_FIELDS:
            _issue(issues, "review.metric_set_mismatch", f"{path}.human_metrics",
                   "human_metrics must contain exactly the semantic review fields.")
            metrics = {}
        for field in HUMAN_METRIC_FIELDS:
            value = metrics.get(field)
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                _issue(issues, "review.invalid_metric", f"{path}.human_metrics.{field}",
                       "Metric must be a non-negative integer or null.")
            if require_complete and value is None:
                _issue(issues, "review.unscored_metric", f"{path}.human_metrics.{field}",
                       "A completed review must score every human metric.")
        metrics_complete = metrics and all(
            isinstance(metrics.get(field), int) and not isinstance(metrics.get(field), bool)
            for field in HUMAN_METRIC_FIELDS
        )
        if require_complete and metrics_complete:
            if metrics["citation_sample_supported"] > metrics["citation_sample_size"]:
                _issue(issues, "review.citation_counts_inconsistent", f"{path}.human_metrics",
                       "Supported citations cannot exceed the citation sample size.")
            classified = (
                metrics["supported_key_claim_count"] + metrics["unresolved_key_claim_count"]
            )
            if classified > metrics["key_claim_count"]:
                _issue(issues, "review.claim_counts_inconsistent", f"{path}.human_metrics",
                       "Classified key claims cannot exceed key_claim_count.")
        if require_complete and not _text(review_case.get("notes")):
            _issue(issues, "review.missing_notes", f"{path}.notes",
                   "Completed case review notes are required.")
    return _finish(issues, {"case_count": len(review_cases), "complete": require_complete})


def _case_judgments(case: dict[str, Any]) -> dict[tuple[str, str], Any]:
    judgments: dict[tuple[str, str], Any] = {("actual_trigger", ""): case["actual_trigger"]}
    for group in ("expected_behavior_results", "forbidden_behavior_results"):
        for item in case[group]:
            judgments[(group, item["behavior"])] = item["observed"]
    for field, value in case["human_metrics"].items():
        judgments[("human_metrics", field)] = value
    return judgments


def compare_reviews(
    left: Any, right: Any, catalog: Any,
    review_artifacts: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    for label, review in (("left", left), ("right", right)):
        validation = validate_review(review, catalog, require_complete=True)
        if validation["verdict"] != "PASS":
            _issue(issues, "comparison.invalid_review", f"$.{label}",
                   f"Review validation failed: {validation['issues']}")
    if issues:
        return _comparison_finish(issues, [], {})
    left_meta = left["review"]
    right_meta = right["review"]
    if left_meta["reviewer_id"] == right_meta["reviewer_id"]:
        _issue(issues, "comparison.same_reviewer", "$.reviewer_ids",
               "Independent reviews require distinct reviewer IDs.")
    if left_meta["raw_output"]["sha256"] != right_meta["raw_output"]["sha256"]:
        _issue(issues, "comparison.raw_hash_mismatch", "$.raw_output.sha256",
               "Reviews must score the same frozen raw output.")
    left_cases = {case["id"]: case for case in left["cases"]}
    right_cases = {case["id"]: case for case in right["cases"]}
    if set(left_cases) != set(right_cases):
        _issue(issues, "comparison.case_set_mismatch", "$.cases",
               "Reviews must score the same case set.")
        return _comparison_finish(issues, [], {})

    disagreements: list[dict[str, Any]] = []
    agreement_count = 0
    for case_id in sorted(left_cases):
        left_values = _case_judgments(left_cases[case_id])
        right_values = _case_judgments(right_cases[case_id])
        for (group, field), left_value in sorted(left_values.items()):
            right_value = right_values[(group, field)]
            if left_value == right_value:
                agreement_count += 1
            else:
                disagreements.append({
                    "case_id": case_id,
                    "group": group,
                    "field": field,
                    "left": left_value,
                    "right": right_value,
                    "final": None,
                    "rationale": "",
                })
    metadata = {
        "raw_output": dict(left_meta["raw_output"]),
        "reviewer_ids": [left_meta["reviewer_id"], right_meta["reviewer_id"]],
        "review_artifacts": review_artifacts or [],
        "case_ids": sorted(left_cases),
        "agreement_count": agreement_count,
    }
    return _comparison_finish(issues, disagreements, metadata)


def validate_adjudication(data: Any) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        _issue(issues, "adjudication.schema_version", "$.schema_version",
               "Adjudication schema_version must be 1.")
        return _finish(issues, {})
    adjudication = data.get("adjudication")
    if not isinstance(adjudication, dict):
        _issue(issues, "adjudication.missing_metadata", "$.adjudication",
               "Adjudication metadata is required.")
        adjudication = {}
    if not _text(adjudication.get("adjudicator_id")):
        _issue(issues, "adjudication.missing_adjudicator", "$.adjudication.adjudicator_id",
               "adjudicator_id is required before final validation.")
    try:
        date.fromisoformat(adjudication.get("adjudicated_on", ""))
    except (TypeError, ValueError):
        _issue(issues, "adjudication.invalid_date", "$.adjudication.adjudicated_on",
               "adjudicated_on must use YYYY-MM-DD.")
    reviewers = adjudication.get("reviewer_ids")
    if not isinstance(reviewers, list) or len(reviewers) != 2 \
            or not all(_text(item) for item in reviewers) or reviewers[0] == reviewers[1]:
        _issue(issues, "adjudication.invalid_reviewers", "$.adjudication.reviewer_ids",
               "Exactly two distinct reviewer IDs are required.")
        reviewers = []
    artifacts = adjudication.get("review_artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 2:
        _issue(issues, "adjudication.invalid_review_artifacts",
               "$.adjudication.review_artifacts",
               "Exactly two hashed review artifacts are required.")
        artifacts = []
    artifact_reviewers: set[str] = set()
    for index, artifact in enumerate(artifacts):
        path = f"$.adjudication.review_artifacts[{index}]"
        if not isinstance(artifact, dict) or not _text(artifact.get("reviewer_id")) \
                or not _text(artifact.get("path")) or not isinstance(
                    artifact.get("sha256"), str
                ) or not SHA256_PATTERN.fullmatch(artifact["sha256"]):
            _issue(issues, "adjudication.invalid_review_artifact", path,
                   "Review artifacts require reviewer_id, path, and sha256.")
            continue
        artifact_reviewers.add(artifact["reviewer_id"])
    if reviewers and artifact_reviewers != set(reviewers):
        _issue(issues, "adjudication.review_artifact_mismatch",
               "$.adjudication.review_artifacts",
               "Review artifact identities must match reviewer_ids.")
    raw = adjudication.get("raw_output")
    if not isinstance(raw, dict) or not _text(raw.get("path")) or not isinstance(
        raw.get("sha256"), str
    ) or not SHA256_PATTERN.fullmatch(raw["sha256"]):
        _issue(issues, "adjudication.invalid_raw_artifact", "$.adjudication.raw_output",
               "Frozen raw output requires path and sha256.")
    case_ids = adjudication.get("case_ids")
    if not isinstance(case_ids, list) or not case_ids or not all(_text(x) for x in case_ids) \
            or len(case_ids) != len(set(case_ids)):
        _issue(issues, "adjudication.invalid_case_ids", "$.adjudication.case_ids",
               "case_ids must be a non-empty unique string array.")
    agreement_count = adjudication.get("agreement_count")
    if not isinstance(agreement_count, int) or isinstance(agreement_count, bool) \
            or agreement_count < 0:
        _issue(issues, "adjudication.invalid_agreement_count",
               "$.adjudication.agreement_count",
               "agreement_count must be a non-negative integer.")
    disagreements = data.get("disagreements")
    if not isinstance(disagreements, list):
        _issue(issues, "adjudication.invalid_disagreements", "$.disagreements",
               "disagreements must be an array.")
        disagreements = []
    if adjudication.get("disagreement_count") != len(disagreements):
        _issue(issues, "adjudication.disagreement_count_mismatch",
               "$.adjudication.disagreement_count",
               "disagreement_count must equal the disagreement array length.")
    disagreement_keys: set[tuple[Any, Any, Any]] = set()
    for index, item in enumerate(disagreements):
        path = f"$.disagreements[{index}]"
        if not isinstance(item, dict):
            _issue(issues, "adjudication.invalid_item", path,
                   "Each disagreement must be an object.")
            continue
        case_id = item.get("case_id")
        group = item.get("group")
        field = item.get("field")
        if not _text(case_id) or not _text(group) or not isinstance(field, str):
            _issue(issues, "adjudication.invalid_key", path,
                   "Each disagreement requires string case_id, group, and field values.")
        else:
            key = (case_id, group, field)
            if key in disagreement_keys:
                _issue(issues, "adjudication.duplicate_disagreement", path,
                       f"Duplicate disagreement: {key}")
            disagreement_keys.add(key)
        if case_id not in (case_ids if isinstance(case_ids, list) else []):
            _issue(issues, "adjudication.unknown_case", f"{path}.case_id",
                   "Disagreement case_id must be declared in adjudication.case_ids.")
        if not isinstance(group, str) or group not in {
            "actual_trigger", "expected_behavior_results",
            "forbidden_behavior_results", "human_metrics",
        }:
            _issue(issues, "adjudication.invalid_group", f"{path}.group",
                   "Unknown disagreement group.")
        final = item.get("final")
        if group == "human_metrics":
            valid_final = isinstance(final, int) and not isinstance(final, bool) and final >= 0
        else:
            valid_final = isinstance(final, bool)
        if not valid_final:
            _issue(issues, "adjudication.invalid_final", f"{path}.final",
                   "final must be a boolean judgment or non-negative metric count.")
        if not _text(item.get("rationale")):
            _issue(issues, "adjudication.missing_rationale", f"{path}.rationale",
                   "Every disagreement requires an adjudication rationale.")
    return _finish(issues, {"disagreement_count": len(disagreements)})


def finalize_adjudication(
    report: Any, left: Any, right: Any, catalog: Any,
) -> dict[str, Any]:
    validation = validate_adjudication(report)
    if validation["verdict"] != "PASS":
        raise ValueError(f"Adjudication is incomplete: {validation['issues']}")
    expected = compare_reviews(
        left, right, catalog, report["adjudication"]["review_artifacts"],
    )
    if expected["comparison_verdict"] != "PASS":
        raise ValueError(f"Source reviews are incompatible: {expected['issues']}")
    expected_items = [
        (item["case_id"], item["group"], item["field"], item["left"], item["right"])
        for item in expected["disagreements"]
    ]
    observed_items = [
        (item.get("case_id"), item.get("group"), item.get("field"),
         item.get("left"), item.get("right"))
        for item in report["disagreements"]
    ]
    if observed_items != expected_items:
        raise ValueError("Adjudication disagreements do not match the two source reviews.")

    final_review = copy.deepcopy(left)
    final_review["review"] = {
        **final_review["review"],
        "reviewer_id": f"adjudicator:{report['adjudication']['adjudicator_id']}",
        "reviewed_on": report["adjudication"]["adjudicated_on"],
        "source_reviewer_ids": report["adjudication"]["reviewer_ids"],
        "source_review_artifacts": report["adjudication"]["review_artifacts"],
    }
    cases = {case["id"]: case for case in final_review["cases"]}
    for item in report["disagreements"]:
        case = cases[item["case_id"]]
        group = item["group"]
        field = item["field"]
        if group == "actual_trigger":
            case["actual_trigger"] = item["final"]
            case["notes"] += f" Adjudicated actual_trigger: {item['rationale']}"
        elif group == "human_metrics":
            case["human_metrics"][field] = item["final"]
            case["notes"] += f" Adjudicated {field}: {item['rationale']}"
        else:
            behavior = next(entry for entry in case[group] if entry["behavior"] == field)
            behavior["observed"] = item["final"]
            behavior["note"] = f"Adjudicated: {item['rationale']}"
    final_validation = validate_review(final_review, catalog, require_complete=True)
    if final_validation["verdict"] != "PASS":
        raise ValueError(f"Final adjudicated review is inconsistent: {final_validation['issues']}")
    return final_review


def _finish(issues: list[dict[str, str]], summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "verdict": "PASS" if not issues else "FAIL",
        "error_count": len(issues),
        "summary": summary,
        "issues": issues,
    }


def _comparison_finish(
    issues: list[dict[str, str]], disagreements: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    agreement_count = metadata.pop("agreement_count", 0)
    return {
        "schema_version": 1,
        "adjudication": {
            **metadata,
            "adjudicator_id": "",
            "adjudicated_on": "",
            "agreement_count": agreement_count,
            "disagreement_count": len(disagreements),
        },
        "disagreements": disagreements,
        "comparison_verdict": "PASS" if not issues else "FAIL",
        "issues": issues,
        "scope_note": (
            "Agreement is descriptive only. Every disagreement requires an identified "
            "adjudicator, an explicit final choice, and a rationale."
        ),
    }


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("raw", type=Path)
    prepare.add_argument("--reviewer", required=True)
    prepare.add_argument("--case-id", action="append", required=True)
    prepare.add_argument("--date", required=True)
    prepare.add_argument("--catalog", type=Path, default=Path("evals/cases.json"))
    prepare.add_argument("--output", type=Path, required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("review", type=Path)
    validate.add_argument("--complete", action="store_true")
    validate.add_argument("--catalog", type=Path, default=Path("evals/cases.json"))
    compare = subparsers.add_parser("compare")
    compare.add_argument("left", type=Path)
    compare.add_argument("right", type=Path)
    compare.add_argument("--catalog", type=Path, default=Path("evals/cases.json"))
    compare.add_argument("--output", type=Path, required=True)
    adjudicate = subparsers.add_parser("validate-adjudication")
    adjudicate.add_argument("report", type=Path)
    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("report", type=Path)
    finalize.add_argument("left", type=Path)
    finalize.add_argument("right", type=Path)
    finalize.add_argument("--catalog", type=Path, default=Path("evals/cases.json"))
    finalize.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            report = prepare_review(
                catalog=_load(args.catalog), raw_path=args.raw,
                reviewer_id=args.reviewer, case_ids=args.case_id, reviewed_on=args.date,
            )
            write_report(args.output, report)
            print(f"Created {args.output}")
            return 0
        if args.command == "validate":
            result = validate_review(
                _load(args.review), _load(args.catalog), require_complete=args.complete,
            )
        elif args.command == "compare":
            left = _load(args.left)
            right = _load(args.right)
            review_artifacts = [
                {
                    "reviewer_id": review.get("review", {}).get("reviewer_id", "unavailable"),
                    "path": path.as_posix(),
                    "sha256": sha256_file(path),
                }
                for review, path in ((left, args.left), (right, args.right))
            ]
            report = compare_reviews(
                left, right, _load(args.catalog), review_artifacts=review_artifacts,
            )
            if report["comparison_verdict"] == "PASS":
                write_report(args.output, report)
                print(f"Created {args.output}")
                print(f"Disagreements requiring adjudication: {len(report['disagreements'])}")
                return 0
            result = {
                "verdict": "FAIL", "error_count": len(report["issues"]),
                "summary": {}, "issues": report["issues"],
            }
        elif args.command == "validate-adjudication":
            result = validate_adjudication(_load(args.report))
        else:
            report = _load(args.report)
            left = _load(args.left)
            right = _load(args.right)
            artifact_by_reviewer = {
                artifact["reviewer_id"]: artifact
                for artifact in report.get("adjudication", {}).get("review_artifacts", [])
                if isinstance(artifact, dict) and _text(artifact.get("reviewer_id"))
            }
            for review, path in ((left, args.left), (right, args.right)):
                reviewer_id = review.get("review", {}).get("reviewer_id")
                artifact = artifact_by_reviewer.get(reviewer_id, {})
                if artifact.get("sha256") != sha256_file(path):
                    raise ValueError(f"Review artifact hash mismatch for {reviewer_id!r}.")
            final_review = finalize_adjudication(
                report, left, right, _load(args.catalog),
            )
            final_review["review"]["adjudication_artifact"] = {
                "path": args.report.as_posix(),
                "sha256": sha256_file(args.report),
            }
            write_report(args.output, final_review)
            print(f"Created {args.output}")
            return 0
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"{result['verdict']}: {result['error_count']} errors")
    for item in result["issues"]:
        print(f"- ERROR {item['code']} {item['path']}: {item['message']}")
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
