from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from scripts.eval_bundle import create_matrix
from scripts.eval_ingest import build_ingestion, sha256_file, write_report
from scripts.eval_matrix_results import materialize_matrix
from scripts.eval_results import validate_results
from scripts.eval_review import (
    HUMAN_METRIC_FIELDS,
    compare_reviews,
    finalize_adjudication,
    prepare_review,
)

ROOT = Path(__file__).parents[1]
CATALOG = json.loads((ROOT / "evals" / "cases.json").read_text(encoding="utf-8"))


def _review(raw: Path, case_id: str, reviewer_id: str) -> dict:
    review = prepare_review(
        catalog=CATALOG, raw_path=raw, reviewer_id=reviewer_id,
        case_ids=[case_id], reviewed_on="2026-08-31",
    )
    catalog_case = next(case for case in CATALOG["cases"] if case["id"] == case_id)
    case = review["cases"][0]
    case["actual_trigger"] = catalog_case["should_trigger"]
    for item in case["expected_behavior_results"]:
        item.update({"observed": True, "note": "Observed."})
    for item in case["forbidden_behavior_results"]:
        item.update({"observed": False, "note": "Not observed."})
    case["human_metrics"] = {field: 0 for field in HUMAN_METRIC_FIELDS}
    case["human_metrics"].update({
        "primary_source_count": 1,
        "key_claim_count": 1,
        "supported_key_claim_count": 1,
    })
    case["notes"] = "Reviewed fixture answer."
    return review


def _complete_case(matrix_dir: Path, bundle: dict, manifest: dict, case_id: str) -> None:
    case_dir = matrix_dir / "blind-artifacts" / bundle["blind_id"] / case_id
    case_dir.mkdir(parents=True)
    raw = case_dir / "raw.md"
    raw.write_text("Reviewed fixture answer.", encoding="utf-8")
    manifest_path = matrix_dir / bundle["path"] / "manifest.json"
    write_report(case_dir / "metrics.json", build_ingestion(manifest_path, raw, case_id))
    left = _review(raw, case_id, "reviewer-a")
    right = _review(raw, case_id, "reviewer-b")
    left_path = case_dir / "review-a.json"
    right_path = case_dir / "review-b.json"
    write_report(left_path, left)
    write_report(right_path, right)
    artifacts = [
        {
            "reviewer_id": review["review"]["reviewer_id"],
            "path": path.as_posix(),
            "sha256": sha256_file(path),
        }
        for review, path in ((left, left_path), (right, right_path))
    ]
    adjudication = compare_reviews(left, right, CATALOG, artifacts)
    adjudication["adjudication"].update({
        "adjudicator_id": "reviewer-c",
        "adjudicated_on": "2026-08-31",
    })
    write_report(case_dir / "adjudication.json", adjudication)
    write_report(
        case_dir / "final-review.json",
        finalize_adjudication(adjudication, left, right, CATALOG),
    )


class EvalMatrixResultsTests(unittest.TestCase):
    def test_reviewed_matrix_materializes_valid_case_results_and_comparisons(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_dir, matrix = create_matrix(
                root=ROOT,
                suites_path=ROOT / "evals" / "suites.json",
                catalog_path=ROOT / "evals" / "cases.json",
                suite_id="offline-regression-v1",
                model="test model identifier unavailable",
                output_parent=Path(temporary),
                now=datetime(2026, 8, 31, 3, 4, 5, tzinfo=UTC),
            )
            for bundle in matrix["bundles"]:
                manifest_path = matrix_dir / bundle["path"] / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                for case in manifest["cases"]:
                    _complete_case(matrix_dir, bundle, manifest, case["id"])

            summary, results, comparisons = materialize_matrix(matrix_dir, ROOT, CATALOG)
            self.assertEqual(len(results), 27)
            self.assertEqual(len(comparisons), 9)
            self.assertFalse(summary["release_claim_ready"])
            self.assertEqual(summary["release_blockers"], ["model_identifier_unavailable"])
            for result in results.values():
                validation = validate_results(result, CATALOG, allow_partial=True)
                self.assertEqual(validation["verdict"], "PASS", validation["issues"])


if __name__ == "__main__":
    unittest.main()
