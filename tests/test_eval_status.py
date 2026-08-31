from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.eval_bundle import create_matrix
from scripts.eval_ingest import build_ingestion, sha256_file, write_report
from scripts.eval_review import (
    HUMAN_METRIC_FIELDS,
    compare_reviews,
    finalize_adjudication,
    prepare_review,
)
from scripts.eval_status import inspect_matrix

ROOT = Path(__file__).parents[1]
CATALOG = json.loads((ROOT / "evals" / "cases.json").read_text(encoding="utf-8"))


def _complete_review(raw: Path, case_id: str, reviewer_id: str) -> dict:
    review = prepare_review(
        catalog=CATALOG,
        raw_path=raw,
        reviewer_id=reviewer_id,
        case_ids=[case_id],
        reviewed_on="2026-08-31",
    )
    case = review["cases"][0]
    catalog_case = next(item for item in CATALOG["cases"] if item["id"] == case_id)
    case["actual_trigger"] = catalog_case["should_trigger"]
    for item in case["expected_behavior_results"]:
        item.update({"observed": True, "note": "Observed in the frozen answer."})
    for item in case["forbidden_behavior_results"]:
        item.update({"observed": False, "note": "Not observed in the frozen answer."})
    case["human_metrics"] = {field: 0 for field in HUMAN_METRIC_FIELDS}
    case["human_metrics"].update({
        "key_claim_count": 1,
        "supported_key_claim_count": 1,
    })
    case["notes"] = "Independent review completed."
    return review


class EvalStatusTests(unittest.TestCase):
    def _matrix(self, temporary: str) -> tuple[Path, dict]:
        return create_matrix(
            root=ROOT,
            suites_path=ROOT / "evals" / "suites.json",
            catalog_path=ROOT / "evals" / "cases.json",
            suite_id="routing-smoke-v1",
            model="test-model",
            output_parent=Path(temporary),
        )

    def test_prepared_matrix_does_not_claim_missing_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_dir, _ = self._matrix(temporary)
            prepared = inspect_matrix(matrix_dir, ROOT, CATALOG)
            self.assertEqual(prepared["verdict"], "PASS", prepared["issues"])
            self.assertEqual(prepared["summary"]["case_run_count"], 3)
            self.assertEqual(prepared["summary"]["raw_complete"], 0)
            required = inspect_matrix(
                matrix_dir, ROOT, CATALOG, require_stage="raw",
            )
            self.assertEqual(required["verdict"], "FAIL")
            self.assertIn("status.incomplete", {x["code"] for x in required["issues"]})

    def test_hash_linked_case_progresses_through_reviewed_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_dir, matrix = self._matrix(temporary)
            bundle = matrix["bundles"][0]
            manifest = matrix_dir / bundle["path"] / "manifest.json"
            case_id = "routing-simple-capital"
            case_dir = matrix_dir / "blind-artifacts" / bundle["blind_id"] / case_id
            case_dir.mkdir(parents=True)
            raw = case_dir / "raw.md"
            raw.write_text("Paris.", encoding="utf-8")
            write_report(
                case_dir / "metrics.json",
                build_ingestion(manifest, raw, case_id),
            )
            review_a = _complete_review(raw, case_id, "reviewer-a")
            review_b = _complete_review(raw, case_id, "reviewer-b")
            review_a_path = case_dir / "review-a.json"
            review_b_path = case_dir / "review-b.json"
            write_report(review_a_path, review_a)
            write_report(review_b_path, review_b)
            artifacts = [
                {
                    "reviewer_id": review["review"]["reviewer_id"],
                    "path": path.as_posix(),
                    "sha256": sha256_file(path),
                }
                for review, path in ((review_a, review_a_path), (review_b, review_b_path))
            ]
            adjudication = compare_reviews(review_a, review_b, CATALOG, artifacts)
            adjudication["adjudication"].update({
                "adjudicator_id": "adjudicator",
                "adjudicated_on": "2026-08-31",
            })
            write_report(case_dir / "adjudication.json", adjudication)
            final_review = finalize_adjudication(
                adjudication, review_a, review_b, CATALOG,
            )
            write_report(case_dir / "final-review.json", final_review)

            status = inspect_matrix(matrix_dir, ROOT, CATALOG)
            self.assertEqual(status["verdict"], "PASS", status["issues"])
            self.assertEqual(status["summary"]["raw_complete"], 1)
            self.assertEqual(status["summary"]["metrics_complete"], 1)
            self.assertEqual(status["summary"]["reviewed_complete"], 1)

    def test_present_but_tampered_metrics_are_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_dir, matrix = self._matrix(temporary)
            bundle = matrix["bundles"][0]
            case_id = "routing-simple-capital"
            case_dir = matrix_dir / "blind-artifacts" / bundle["blind_id"] / case_id
            case_dir.mkdir(parents=True)
            raw = case_dir / "raw.md"
            raw.write_text("Paris.", encoding="utf-8")
            manifest = matrix_dir / bundle["path"] / "manifest.json"
            report = build_ingestion(manifest, raw, case_id)
            report["raw_output"]["sha256"] = "0" * 64
            write_report(case_dir / "metrics.json", report)
            status = inspect_matrix(matrix_dir, ROOT, CATALOG)
            self.assertEqual(status["verdict"], "FAIL")
            self.assertIn("status.raw_hash_mismatch", {x["code"] for x in status["issues"]})


if __name__ == "__main__":
    unittest.main()
