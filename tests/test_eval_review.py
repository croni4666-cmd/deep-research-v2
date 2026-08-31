from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.eval_review import (
    HUMAN_METRIC_FIELDS,
    compare_reviews,
    finalize_adjudication,
    prepare_review,
    validate_adjudication,
    validate_review,
)

ROOT = Path(__file__).parents[1]
CATALOG = json.loads((ROOT / "evals" / "cases.json").read_text(encoding="utf-8"))


def completed_review(reviewer_id: str = "reviewer-a") -> dict:
    review = prepare_review(
        catalog=CATALOG,
        raw_path=ROOT / "evals" / "raw" / "pilot-2026-08-30-routing.md",
        reviewer_id=reviewer_id,
        case_ids=["routing-simple-capital"],
        reviewed_on="2026-08-31",
    )
    case = review["cases"][0]
    case["actual_trigger"] = False
    for item in case["expected_behavior_results"]:
        item.update({"observed": True, "note": "Observed in the raw answer."})
    for item in case["forbidden_behavior_results"]:
        item.update({"observed": False, "note": "Not observed in the raw answer."})
    case["human_metrics"] = {field: 0 for field in HUMAN_METRIC_FIELDS}
    case["human_metrics"].update({
        "key_claim_count": 1,
        "supported_key_claim_count": 1,
    })
    case["notes"] = "Independent review completed."
    return review


def artifact_refs() -> list[dict[str, str]]:
    return [
        {"reviewer_id": "reviewer-a", "path": "review-a.json", "sha256": "a" * 64},
        {"reviewer_id": "reviewer-b", "path": "review-b.json", "sha256": "b" * 64},
    ]


class EvalReviewTests(unittest.TestCase):
    def test_prepared_review_is_valid_but_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            raw = Path(temporary) / "raw.md"
            raw.write_text("Paris.", encoding="utf-8")
            review = prepare_review(
                catalog=CATALOG, raw_path=raw, reviewer_id="reviewer-a",
                case_ids=["routing-simple-capital"], reviewed_on="2026-08-31",
            )
            self.assertEqual(validate_review(review, CATALOG)["verdict"], "PASS")
            complete = validate_review(review, CATALOG, require_complete=True)
            self.assertEqual(complete["verdict"], "FAIL")
            self.assertIn("review.unscored_trigger", {x["code"] for x in complete["issues"]})

    def test_mode_revealing_raw_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            raw = Path(temporary) / "candidate-builtin.md"
            raw.write_text("Paris.", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "reveals the candidate mode"):
                prepare_review(
                    catalog=CATALOG, raw_path=raw, reviewer_id="reviewer-a",
                    case_ids=["routing-simple-capital"], reviewed_on="2026-08-31",
                )

    def test_two_agreeing_independent_reviews_need_no_resolutions(self) -> None:
        left = completed_review("reviewer-a")
        right = completed_review("reviewer-b")
        report = compare_reviews(left, right, CATALOG, artifact_refs())
        self.assertEqual(report["comparison_verdict"], "PASS", report["issues"])
        self.assertEqual(report["adjudication"]["disagreement_count"], 0)
        report["adjudication"]["adjudicator_id"] = "adjudicator"
        report["adjudication"]["adjudicated_on"] = "2026-08-31"
        self.assertEqual(validate_adjudication(report)["verdict"], "PASS")

    def test_disagreements_are_explicit_and_require_rationale(self) -> None:
        left = completed_review("reviewer-a")
        right = completed_review("reviewer-b")
        right["cases"][0]["actual_trigger"] = True
        right["cases"][0]["human_metrics"]["key_claim_count"] = 2
        report = compare_reviews(left, right, CATALOG, artifact_refs())
        self.assertEqual(len(report["disagreements"]), 2)
        report["adjudication"]["adjudicator_id"] = "adjudicator"
        report["adjudication"]["adjudicated_on"] = "2026-08-31"
        invalid = validate_adjudication(report)
        self.assertEqual(invalid["verdict"], "FAIL")
        for disagreement in report["disagreements"]:
            disagreement["final"] = disagreement["left"]
            disagreement["rationale"] = "Selected after inspecting the frozen raw answer."
        self.assertEqual(validate_adjudication(report)["verdict"], "PASS")
        final_review = finalize_adjudication(report, left, right, CATALOG)
        self.assertEqual(
            validate_review(final_review, CATALOG, require_complete=True)["verdict"],
            "PASS",
        )
        self.assertEqual(
            final_review["review"]["source_reviewer_ids"],
            ["reviewer-a", "reviewer-b"],
        )
        self.assertIn("Adjudicated actual_trigger", final_review["cases"][0]["notes"])

    def test_same_reviewer_or_different_raw_output_fails(self) -> None:
        left = completed_review("reviewer-a")
        right = copy.deepcopy(left)
        report = compare_reviews(left, right, CATALOG)
        self.assertEqual(report["comparison_verdict"], "FAIL")
        self.assertIn("comparison.same_reviewer", {x["code"] for x in report["issues"]})
        right["review"]["reviewer_id"] = "reviewer-b"
        right["review"]["raw_output"]["sha256"] = "b" * 64
        report = compare_reviews(left, right, CATALOG)
        self.assertIn("comparison.raw_hash_mismatch", {x["code"] for x in report["issues"]})


if __name__ == "__main__":
    unittest.main()
