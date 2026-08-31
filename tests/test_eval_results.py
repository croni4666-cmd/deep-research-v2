from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.eval_results import validate_results

ROOT = Path(__file__).parents[1]
CATALOG = json.loads((ROOT / "evals" / "cases.json").read_text(encoding="utf-8"))


def sample_result() -> dict:
    case = next(item for item in CATALOG["cases"] if item["id"] == "routing-simple-capital")
    return {
        "schema_version": 1,
        "run": {
            "id": "pilot-builtin-20260830",
            "date": "2026-08-30",
            "mode": "builtin",
            "model": "test-model",
            "prompt_revision": "catalog-v1",
            "tools": [],
            "source_access": "none required",
        },
        "cases": [{
            "id": case["id"],
            "status": "completed",
            "expected_trigger": False,
            "actual_trigger": False,
            "expected_behavior_results": [{
                "behavior": case["expected_behaviors"][0],
                "observed": True,
                "note": "Direct answer.",
            }],
            "forbidden_behavior_results": [
                {"behavior": behavior, "observed": False, "note": "Not observed."}
                for behavior in case["forbidden_behaviors"]
            ],
            "sources": [],
            "metrics": {
                "output_word_count": 1,
                "source_count": 0,
                "primary_source_count": 0,
                "citation_sample_size": 0,
                "citation_sample_supported": 0,
                "unsupported_claims_in_sample": 0,
                "key_claim_count": 1,
                "supported_key_claim_count": 1,
                "unresolved_key_claim_count": 0,
            },
            "elapsed_seconds": None,
            "cost": None,
            "notes": "Routing behavior reviewed manually.",
        }],
    }


def sample_result_v2() -> dict:
    data = sample_result()
    data["schema_version"] = 2
    data["run"].update({"suite_id": "routing-smoke-v1", "repeat": 1})
    artifact = {"path": "artifact.json", "sha256": "a" * 64}
    data["artifacts"] = {
        "bundle_manifest": dict(artifact),
        "raw_output": dict(artifact),
        "metric_extraction": dict(artifact),
    }
    data["cases"][0]["metric_provenance"] = {
        field: "automatic" if field in {"output_word_count", "source_count"} else "human"
        for field in data["cases"][0]["metrics"]
    }
    data["cases"][0]["automatic_checks"] = {"duplicate_table_row_count": 0}
    return data


class EvalResultTests(unittest.TestCase):
    def test_valid_partial_result_passes(self) -> None:
        result = validate_results(sample_result(), CATALOG, allow_partial=True)
        self.assertEqual(result["verdict"], "PASS", result["issues"])

    def test_valid_v2_partial_result_passes(self) -> None:
        result = validate_results(sample_result_v2(), CATALOG, allow_partial=True)
        self.assertEqual(result["verdict"], "PASS", result["issues"])

    def test_v1_remains_backward_compatible(self) -> None:
        data = sample_result()
        self.assertNotIn("artifacts", data)
        result = validate_results(data, CATALOG, allow_partial=True)
        self.assertEqual(result["verdict"], "PASS", result["issues"])

    def test_v2_requires_bundle_linkage(self) -> None:
        data = sample_result_v2()
        del data["artifacts"]["bundle_manifest"]
        result = validate_results(data, CATALOG, allow_partial=True)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("result.missing_artifact", {item["code"] for item in result["issues"]})

    def test_v2_requires_automatic_metric_provenance(self) -> None:
        data = sample_result_v2()
        data["cases"][0]["metric_provenance"]["source_count"] = "human"
        result = validate_results(data, CATALOG, allow_partial=True)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn(
            "case.automatic_metric_not_marked",
            {item["code"] for item in result["issues"]},
        )

    def test_partial_result_fails_without_opt_in(self) -> None:
        result = validate_results(sample_result(), CATALOG)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("cases.partial_run", {item["code"] for item in result["issues"]})

    def test_behavior_text_must_match_catalog(self) -> None:
        data = sample_result()
        data["cases"][0]["expected_behavior_results"][0]["behavior"] = "A made-up criterion"
        result = validate_results(data, CATALOG, allow_partial=True)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("case.behavior_mismatch", {item["code"] for item in result["issues"]})

    def test_completed_behavior_cannot_be_unscored(self) -> None:
        data = sample_result()
        data["cases"][0]["expected_behavior_results"][0]["observed"] = None
        result = validate_results(data, CATALOG, allow_partial=True)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn(
            "case.completed_behavior_unscored",
            {item["code"] for item in result["issues"]},
        )

    def test_completed_behavior_requires_review_note(self) -> None:
        data = sample_result()
        data["cases"][0]["expected_behavior_results"][0]["note"] = ""
        result = validate_results(data, CATALOG, allow_partial=True)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn(
            "case.completed_behavior_missing_note",
            {item["code"] for item in result["issues"]},
        )

    def test_completed_trigger_case_requires_sources(self) -> None:
        data = sample_result()
        case = next(
            item for item in CATALOG["cases"]
            if item["id"] == "adversarial-mirrored-evidence"
        )
        data["cases"] = [{
            "id": case["id"],
            "status": "completed",
            "expected_trigger": True,
            "actual_trigger": True,
            "expected_behavior_results": [
                {"behavior": behavior, "observed": True, "note": "Observed."}
                for behavior in case["expected_behaviors"]
            ],
            "forbidden_behavior_results": [
                {"behavior": behavior, "observed": False, "note": "Not observed."}
                for behavior in case["forbidden_behaviors"]
            ],
            "sources": [],
            "notes": "Deliberately incomplete fixture result.",
        }]
        result = validate_results(data, CATALOG, allow_partial=True)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn(
            "case.completed_research_without_sources",
            {item["code"] for item in result["issues"]},
        )

    def test_completed_case_requires_metrics(self) -> None:
        data = sample_result()
        del data["cases"][0]["metrics"]
        result = validate_results(data, CATALOG, allow_partial=True)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn(
            "case.completed_metrics_missing",
            {item["code"] for item in result["issues"]},
        )

    def test_metric_relationships_are_validated(self) -> None:
        data = sample_result()
        data["cases"][0]["metrics"]["citation_sample_supported"] = 2
        data["cases"][0]["metrics"]["citation_sample_size"] = 1
        result = validate_results(data, CATALOG, allow_partial=True)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn(
            "case.citation_sample_inconsistent",
            {item["code"] for item in result["issues"]},
        )


if __name__ == "__main__":
    unittest.main()
