"""Materialize reviewed matrix artifacts into validated schema-v2 case results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

if __package__:
    from .eval_compare import compare_results
    from .eval_ingest import sha256_file
    from .eval_results import AUTOMATIC_METRIC_FIELDS, METRIC_FIELDS, validate_results
    from .eval_status import inspect_matrix
else:
    from eval_compare import compare_results
    from eval_ingest import sha256_file
    from eval_results import AUTOMATIC_METRIC_FIELDS, METRIC_FIELDS, validate_results
    from eval_status import inspect_matrix

DATE_LABELS = ("Publication date", "Snapshot date", "Registry updated")
UNIDENTIFIED_MODEL_PATTERN = re.compile(
    r"\b(unavailable|unknown|unspecified|unidentified)\b", re.IGNORECASE,
)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _artifact(path: Path) -> dict[str, str]:
    return {"path": path.resolve().as_posix(), "sha256": sha256_file(path)}


def _field(lines: list[str], labels: tuple[str, ...]) -> str | None:
    for line in lines:
        cleaned = line.replace("**", "").replace("`", "").strip()
        for label in labels:
            prefix = f"{label}:"
            if cleaned.lower().startswith(prefix.lower()):
                value = cleaned[len(prefix):].strip()
                if value:
                    return value
    return None


def _source_record(path: Path, fallback_date: str) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    title = next((line[2:].strip() for line in lines if line.startswith("# ")), None)
    publisher = _field(lines, ("Publisher",))
    source_date = _field(lines, DATE_LABELS) or fallback_date
    url = _field(lines, ("Source URL",))
    if not all((title, publisher, source_date, url)):
        raise ValueError(f"Candidate source metadata is incomplete: {path}")
    return {
        "title": title,
        "publisher": publisher,
        "date": source_date,
        "url": url,
    }


def _candidate_sources(
    root: Path, manifest_case: dict[str, Any], fallback_date: str,
) -> dict[str, dict[str, str]]:
    records: dict[str, dict[str, str]] = {}
    for item in manifest_case.get("candidate_files", []):
        path = root / item["path"]
        if sha256_file(path) != item.get("sha256"):
            raise ValueError(f"Candidate source hash mismatch: {path}")
        record = _source_record(path, fallback_date)
        if record["url"] in records:
            raise ValueError(f"Duplicate candidate source URL: {record['url']}")
        records[record["url"]] = record
    return records


def build_case_result(
    *, root: Path, manifest_path: Path, manifest: dict[str, Any],
    manifest_case: dict[str, Any], case_dir: Path, catalog_case: dict[str, Any],
) -> dict[str, Any]:
    case_id = manifest_case["id"]
    metrics_path = case_dir / "metrics.json"
    final_path = case_dir / "final-review.json"
    raw_path = case_dir / "raw.md"
    metrics = _load(metrics_path)
    final = _load(final_path)
    reviewed = final["cases"]
    if len(reviewed) != 1 or reviewed[0].get("id") != case_id:
        raise ValueError(f"Final review scope differs from case {case_id}: {final_path}")
    reviewed_case = reviewed[0]
    automatic = metrics["case"]["automatic_metrics"]
    human = reviewed_case["human_metrics"]
    combined_metrics = {**automatic, **human}
    if set(combined_metrics) != METRIC_FIELDS:
        raise ValueError(f"Metric fields are incomplete for {case_id}")
    run = manifest["run"]
    run_date = run["created_at"][:10]
    available = _candidate_sources(root, manifest_case, run_date)
    reported_urls = metrics["case"].get("details", {}).get("unique_urls", [])
    missing_urls = [url for url in reported_urls if url not in available]
    if missing_urls:
        raise ValueError(f"Reported URLs are outside retained candidate sources: {missing_urls}")
    sources = list(available.values())
    result = {
        "schema_version": 2,
        "run": {
            "id": f"{run['id']}-{case_id}",
            "date": run_date,
            "mode": run["mode"],
            "model": run["model"],
            "prompt_revision": run["prompt_revision"],
            "tools": run["tools"],
            "source_access": run["source_access"],
            "suite_id": run["suite_id"],
            "repeat": run["repeat"],
        },
        "artifacts": {
            "bundle_manifest": _artifact(manifest_path),
            "raw_output": _artifact(raw_path),
            "metric_extraction": _artifact(metrics_path),
        },
        "cases": [{
            "id": case_id,
            "status": "completed",
            "expected_trigger": catalog_case["should_trigger"],
            "actual_trigger": reviewed_case["actual_trigger"],
            "expected_behavior_results": reviewed_case["expected_behavior_results"],
            "forbidden_behavior_results": reviewed_case["forbidden_behavior_results"],
            "sources": sources,
            "metrics": combined_metrics,
            "metric_provenance": {
                field: "automatic" if field in AUTOMATIC_METRIC_FIELDS else "human"
                for field in sorted(METRIC_FIELDS)
            },
            "automatic_checks": metrics["case"]["automatic_checks"],
            "elapsed_seconds": None,
            "cost": None,
            "notes": reviewed_case["notes"],
        }],
        "scope_note": (
            "Materialized from hash-linked automatic metrics and an adjudicated final "
            "review. Source dates fall back to the retained run date when a fixture "
            "records no publication or snapshot date."
        ),
    }
    return result


def _aggregate(results: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    cases = [result["cases"][0] for result in results if result["run"]["mode"] == mode]
    expected = [item for case in cases for item in case["expected_behavior_results"]]
    forbidden = [item for case in cases for item in case["forbidden_behavior_results"]]
    totals = {field: sum(case["metrics"][field] for case in cases) for field in METRIC_FIELDS}
    return {
        "mode": mode,
        "case_run_count": len(cases),
        "expected_behaviors": {
            "passed": sum(item["observed"] is True for item in expected),
            "total": len(expected),
        },
        "forbidden_behaviors": {
            "avoided": sum(item["observed"] is False for item in forbidden),
            "total": len(forbidden),
        },
        **totals,
        "duplicate_table_row_count": sum(
            case["automatic_checks"]["duplicate_table_row_count"] for case in cases
        ),
    }


def materialize_matrix(
    matrix_dir: Path, root: Path, catalog: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    status = inspect_matrix(matrix_dir, root, catalog, require_stage="reviewed")
    if status["verdict"] != "PASS":
        raise ValueError(f"Matrix reviewed gate failed: {status['issues']}")
    matrix = _load(matrix_dir / "matrix.json")
    catalog_by_id = {case["id"]: case for case in catalog["cases"]}
    results: dict[str, dict[str, Any]] = {}
    groups: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for bundle in matrix["bundles"]:
        manifest_path = matrix_dir / bundle["path"] / "manifest.json"
        manifest = _load(manifest_path)
        for manifest_case in manifest["cases"]:
            case_id = manifest_case["id"]
            case_dir = matrix_dir / "blind-artifacts" / bundle["blind_id"] / case_id
            result = build_case_result(
                root=root, manifest_path=manifest_path, manifest=manifest,
                manifest_case=manifest_case, case_dir=case_dir,
                catalog_case=catalog_by_id[case_id],
            )
            validation = validate_results(result, catalog, allow_partial=True)
            if validation["verdict"] != "PASS":
                raise ValueError(
                    f"Generated result is invalid for {case_id}: {validation['issues']}"
                )
            name = f"{bundle['mode']}-r{bundle['repeat']}-{case_id}.json"
            results[name] = result
            groups[(bundle["repeat"], case_id)].append(result)
    comparisons: dict[str, dict[str, Any]] = {}
    for (repeat, case_id), grouped in sorted(groups.items()):
        report = compare_results(grouped, catalog)
        if report["verdict"] != "PASS":
            raise ValueError(
                f"Comparison failed for repeat {repeat}, {case_id}: {report['issues']}"
            )
        comparisons[f"r{repeat}-{case_id}.json"] = report
    model_identifiable = not UNIDENTIFIED_MODEL_PATTERN.search(matrix["model"])
    summary = {
        "schema_version": 1,
        "suite_id": matrix["suite_id"],
        "model": matrix["model"],
        "result_count": len(results),
        "comparison_count": len(comparisons),
        "modes": [_aggregate(list(results.values()), mode) for mode in matrix["modes"]],
        "release_claim_ready": model_identifiable,
        "release_blockers": [] if model_identifiable else ["model_identifier_unavailable"],
        "scope_note": (
            "Descriptive aggregation of retained reviewed artifacts. A comparative "
            "benchmark claim remains blocked unless release_claim_ready is true."
        ),
    }
    return summary, results, comparisons


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate validated schema-v2 case results from a reviewed matrix.",
    )
    parser.add_argument("matrix", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--catalog", type=Path, default=Path("evals/cases.json"))
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        print(f"ERROR: output already exists: {output}", file=sys.stderr)
        return 2
    try:
        catalog = _load(args.catalog.resolve())
        summary, results, comparisons = materialize_matrix(
            args.matrix.resolve(), args.root.resolve(), catalog,
        )
        for name, result in results.items():
            _write(output / "individual" / name, result)
        for name, report in comparisons.items():
            _write(output / "comparisons" / name, report)
        _write(output / "summary.json", summary)
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        f"PASS: results={summary['result_count']}, "
        f"comparisons={summary['comparison_count']}, "
        f"release_claim_ready={str(summary['release_claim_ready']).lower()}"
    )
    for blocker in summary["release_blockers"]:
        print(f"- BLOCKED {blocker}")
    print(summary["scope_note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
