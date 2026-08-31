"""Inspect a repeated evaluation matrix without claiming missing runs are complete."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__:
    from .eval_bundle import validate_matrix
    from .eval_ingest import sha256_file
    from .eval_review import finalize_adjudication, validate_review
else:
    from eval_bundle import validate_matrix
    from eval_ingest import sha256_file
    from eval_review import finalize_adjudication, validate_review

CASE_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
STAGES = ("prepared", "raw", "metrics", "reviewed")


def _issue(issues: list[dict[str, str]], code: str, path: str, message: str) -> None:
    issues.append({"code": code, "path": path, "message": message})


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_ingestion(
    report: Any, *, manifest_path: Path, raw_path: Path, case_id: str,
    issues: list[dict[str, str]], path: str,
) -> bool:
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        _issue(issues, "status.invalid_metrics", path,
               "Metric extraction must use schema_version 1.")
        return False
    manifest = report.get("bundle_manifest")
    raw = report.get("raw_output")
    case = report.get("case")
    valid = True
    if not isinstance(manifest, dict) or manifest.get("sha256") != sha256_file(manifest_path):
        _issue(issues, "status.manifest_hash_mismatch", f"{path}.bundle_manifest",
               "Metric extraction does not match the bundle manifest.")
        valid = False
    if not isinstance(raw, dict) or raw.get("sha256") != sha256_file(raw_path):
        _issue(issues, "status.raw_hash_mismatch", f"{path}.raw_output",
               "Metric extraction does not match the frozen raw answer.")
        valid = False
    if not isinstance(case, dict) or case.get("id") != case_id:
        _issue(issues, "status.metric_case_mismatch", f"{path}.case.id",
               "Metric extraction case id differs from the bundle case.")
        return False
    automatic = case.get("automatic_metrics")
    checks = case.get("automatic_checks")
    for field in ("output_word_count", "source_count"):
        value = automatic.get(field) if isinstance(automatic, dict) else None
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            _issue(issues, "status.invalid_automatic_metric",
                   f"{path}.case.automatic_metrics.{field}",
                   "Automatic metric must be a non-negative integer.")
            valid = False
    duplicate_count = checks.get("duplicate_table_row_count") \
        if isinstance(checks, dict) else None
    if not isinstance(duplicate_count, int) or isinstance(duplicate_count, bool) \
            or duplicate_count < 0:
        _issue(issues, "status.invalid_automatic_check", f"{path}.case.automatic_checks",
               "duplicate_table_row_count must be a non-negative integer.")
        valid = False
    return valid


def _artifact_hashes_match(
    report: dict[str, Any], reviews: list[tuple[Path, dict[str, Any]]],
) -> bool:
    records = report.get("adjudication", {}).get("review_artifacts", [])
    if not isinstance(records, list):
        return False
    by_reviewer = {
        item.get("reviewer_id"): item
        for item in records
        if isinstance(item, dict) and isinstance(item.get("reviewer_id"), str)
    }
    for review_path, review in reviews:
        reviewer_id = review.get("review", {}).get("reviewer_id")
        if by_reviewer.get(reviewer_id, {}).get("sha256") != sha256_file(review_path):
            return False
    return True


def _normalized_final_review(value: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(value)
    metadata = normalized.get("review")
    if isinstance(metadata, dict):
        metadata.pop("adjudication_artifact", None)
    return normalized


def _valid_review_set(
    *, case_dir: Path, raw_path: Path, case_id: str, catalog: Any,
    issues: list[dict[str, str]], path: str,
) -> bool:
    review_paths = [case_dir / "review-a.json", case_dir / "review-b.json"]
    required = review_paths + [case_dir / "adjudication.json", case_dir / "final-review.json"]
    if not all(item.is_file() for item in required):
        return False
    reviews: list[tuple[Path, dict[str, Any]]] = []
    raw_hash = sha256_file(raw_path)
    for index, review_path in enumerate(review_paths):
        try:
            review = _load(review_path)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            _issue(issues, "status.unreadable_review", f"{path}.reviews[{index}]", str(exc))
            return False
        validation = validate_review(review, catalog, require_complete=True)
        if validation["verdict"] != "PASS":
            _issue(issues, "status.invalid_review", f"{path}.reviews[{index}]",
                   f"Review validation failed: {validation['issues']}")
            return False
        ids = [item.get("id") for item in review.get("cases", [])]
        if ids != [case_id] or review["review"]["raw_output"]["sha256"] != raw_hash:
            _issue(issues, "status.review_scope_mismatch", f"{path}.reviews[{index}]",
                   "Review must score only this case and the same frozen raw answer.")
            return False
        reviews.append((review_path, review))
    try:
        adjudication = _load(case_dir / "adjudication.json")
        final_review = _load(case_dir / "final-review.json")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _issue(issues, "status.unreadable_adjudication", f"{path}.adjudication", str(exc))
        return False
    if not _artifact_hashes_match(adjudication, reviews):
        _issue(issues, "status.review_hash_mismatch", f"{path}.adjudication",
               "Adjudication does not match both frozen review files.")
        return False
    try:
        expected = finalize_adjudication(
            adjudication, reviews[0][1], reviews[1][1], catalog,
        )
    except ValueError as exc:
        _issue(issues, "status.invalid_adjudication", f"{path}.adjudication", str(exc))
        return False
    final_validation = validate_review(final_review, catalog, require_complete=True)
    if final_validation["verdict"] != "PASS":
        _issue(issues, "status.invalid_final_review", f"{path}.final_review",
               f"Final review validation failed: {final_validation['issues']}")
        return False
    if _normalized_final_review(final_review) != _normalized_final_review(expected):
        _issue(issues, "status.final_review_mismatch", f"{path}.final_review",
               "Final review differs from the validated adjudication reconstruction.")
        return False
    return True


def inspect_matrix(
    matrix_dir: Path, root: Path, catalog: Any, *, require_stage: str = "prepared",
) -> dict[str, Any]:
    if require_stage not in STAGES:
        raise ValueError(f"require_stage must be one of {STAGES}.")
    issues: list[dict[str, str]] = []
    matrix_validation = validate_matrix(matrix_dir, root)
    if matrix_validation["verdict"] != "PASS":
        _issue(issues, "status.invalid_matrix", "$.matrix",
               f"Matrix validation failed: {matrix_validation['issues']}")
        return _finish(issues, {}, require_stage)
    matrix = _load(matrix_dir / "matrix.json")
    total_cases = 0
    raw_complete = 0
    metrics_complete = 0
    reviewed_complete = 0
    runs: list[dict[str, Any]] = []
    for bundle_index, bundle in enumerate(matrix["bundles"]):
        manifest_path = matrix_dir / bundle["path"] / "manifest.json"
        manifest = _load(manifest_path)
        run_counts = {"case_count": 0, "raw": 0, "metrics": 0, "reviewed": 0}
        for case_index, case in enumerate(manifest["cases"]):
            case_id = case.get("id")
            item_path = f"$.bundles[{bundle_index}].cases[{case_index}]"
            if not isinstance(case_id, str) or not CASE_ID_PATTERN.fullmatch(case_id):
                _issue(issues, "status.invalid_case_id", f"{item_path}.id",
                       "Case id must be safe lowercase kebab-case.")
                continue
            total_cases += 1
            run_counts["case_count"] += 1
            case_dir = matrix_dir / "blind-artifacts" / bundle["blind_id"] / case_id
            raw_path = case_dir / "raw.md"
            if not raw_path.is_file() or raw_path.stat().st_size == 0:
                continue
            raw_complete += 1
            run_counts["raw"] += 1
            metrics_path = case_dir / "metrics.json"
            if not metrics_path.is_file():
                continue
            try:
                metrics = _load(metrics_path)
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                _issue(issues, "status.unreadable_metrics", f"{item_path}.metrics", str(exc))
                continue
            if not _valid_ingestion(
                metrics, manifest_path=manifest_path, raw_path=raw_path, case_id=case_id,
                issues=issues, path=f"{item_path}.metrics",
            ):
                continue
            metrics_complete += 1
            run_counts["metrics"] += 1
            if _valid_review_set(
                case_dir=case_dir, raw_path=raw_path, case_id=case_id, catalog=catalog,
                issues=issues, path=item_path,
            ):
                reviewed_complete += 1
                run_counts["reviewed"] += 1
        runs.append({
            "blind_id": bundle["blind_id"],
            "mode": bundle["mode"],
            "repeat": bundle["repeat"],
            **run_counts,
        })
    summary = {
        "bundle_count": len(matrix["bundles"]),
        "case_run_count": total_cases,
        "raw_complete": raw_complete,
        "metrics_complete": metrics_complete,
        "reviewed_complete": reviewed_complete,
        "runs": runs,
    }
    required_count = {
        "prepared": total_cases,
        "raw": raw_complete,
        "metrics": metrics_complete,
        "reviewed": reviewed_complete,
    }[require_stage]
    if require_stage != "prepared" and required_count != total_cases:
        _issue(issues, "status.incomplete", "$.summary",
               f"Required stage {require_stage!r} is complete for "
               f"{required_count}/{total_cases} case runs.")
    return _finish(issues, summary, require_stage)


def _finish(
    issues: list[dict[str, str]], summary: dict[str, Any], require_stage: str,
) -> dict[str, Any]:
    return {
        "verdict": "PASS" if not issues else "FAIL",
        "error_count": len(issues),
        "required_stage": require_stage,
        "summary": summary,
        "issues": issues,
        "scope_note": (
            "Status is based on retained, hash-linked artifacts. Prepared bundles are not "
            "completed model runs, and missing artifacts are never inferred or fabricated."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("matrix", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--catalog", type=Path, default=Path("evals/cases.json"))
    parser.add_argument("--require-stage", choices=STAGES, default="prepared")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = inspect_matrix(
            args.matrix.resolve(), args.root.resolve(), _load(args.catalog),
            require_stage=args.require_stage,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        summary = result["summary"]
        print(f"{result['verdict']}: required={result['required_stage']}, "
              f"case-runs={summary.get('case_run_count', 0)}, "
              f"raw={summary.get('raw_complete', 0)}, "
              f"metrics={summary.get('metrics_complete', 0)}, "
              f"reviewed={summary.get('reviewed_complete', 0)}")
        for item in result["issues"]:
            print(f"- ERROR {item['code']} {item['path']}: {item['message']}")
        print(result["scope_note"])
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
