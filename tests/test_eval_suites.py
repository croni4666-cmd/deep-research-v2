from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.eval_suites import validate_suites

ROOT = Path(__file__).parents[1]
CATALOG = json.loads((ROOT / "evals" / "cases.json").read_text(encoding="utf-8"))
SUITES = json.loads((ROOT / "evals" / "suites.json").read_text(encoding="utf-8"))


class EvalSuiteTests(unittest.TestCase):
    def test_repository_suites_pass(self) -> None:
        result = validate_suites(SUITES, CATALOG)
        self.assertEqual(result["verdict"], "PASS", result["issues"])
        self.assertGreaterEqual(result["summary"]["offline_suite_count"], 1)

    def test_unknown_case_fails(self) -> None:
        data = copy.deepcopy(SUITES)
        data["suites"][0]["case_ids"].append("not-a-catalog-case")
        result = validate_suites(data, CATALOG)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("suite.unknown_case", {item["code"] for item in result["issues"]})

    def test_offline_trigger_requires_fixture(self) -> None:
        data = copy.deepcopy(SUITES)
        suite = next(item for item in data["suites"] if item["id"] == "routing-smoke-v1")
        suite["case_ids"].append("technical-library-current")
        result = validate_suites(data, CATALOG)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn(
            "suite.offline_trigger_without_fixture",
            {item["code"] for item in result["issues"]},
        )

    def test_repeated_case_uses_repeats_field(self) -> None:
        data = copy.deepcopy(SUITES)
        data["suites"][0]["case_ids"].append(data["suites"][0]["case_ids"][0])
        result = validate_suites(data, CATALOG)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("suite.duplicate_case", {item["code"] for item in result["issues"]})


if __name__ == "__main__":
    unittest.main()
