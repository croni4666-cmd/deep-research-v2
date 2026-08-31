from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.eval_catalog import validate_catalog

CATALOG_PATH = Path(__file__).parents[1] / "evals" / "cases.json"


def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


class EvalCatalogTests(unittest.TestCase):
    def test_repository_catalog_passes_strict_validation(self) -> None:
        result = validate_catalog(load_catalog(), strict=True)
        self.assertEqual(result["verdict"], "PASS", result["issues"])
        self.assertGreaterEqual(result["summary"]["case_count"], 15)

    def test_portable_depth_cases_are_retained(self) -> None:
        case_ids = {case["id"] for case in load_catalog()["cases"]}
        self.assertTrue({
            "policy-cross-context-transfer",
            "market-local-language-routing",
            "technical-parallel-decomposition",
        } <= case_ids)

    def test_duplicate_case_id_fails(self) -> None:
        catalog = load_catalog()
        duplicate = copy.deepcopy(catalog["cases"][0])
        duplicate["prompt"] += " Duplicate prompt variant."
        catalog["cases"].append(duplicate)
        result = validate_catalog(catalog)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("case.duplicate_id", {item["code"] for item in result["issues"]})

    def test_missing_adversarial_coverage_fails(self) -> None:
        catalog = load_catalog()
        catalog["cases"] = [
            case for case in catalog["cases"] if case["category"] != "adversarial"
        ]
        result = validate_catalog(catalog)
        self.assertEqual(result["verdict"], "FAIL")
        codes = {item["code"] for item in result["issues"]}
        self.assertIn("coverage.adversarial", codes)
        self.assertIn("coverage.categories", codes)

    def test_three_non_trigger_cases_are_required(self) -> None:
        catalog = load_catalog()
        kept_one = False
        for case in catalog["cases"]:
            if not case["should_trigger"]:
                if kept_one:
                    case["should_trigger"] = True
                kept_one = True
        result = validate_catalog(catalog)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("coverage.non_trigger", {item["code"] for item in result["issues"]})

    def test_fixture_path_must_be_repository_relative(self) -> None:
        catalog = load_catalog()
        catalog["cases"][0]["fixture"] = "../outside"
        result = validate_catalog(catalog)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("case.unsafe_fixture", {item["code"] for item in result["issues"]})


if __name__ == "__main__":
    unittest.main()
