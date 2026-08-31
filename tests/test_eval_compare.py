from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.eval_compare import compare_results
from tests.test_eval_results import sample_result, sample_result_v2

ROOT = Path(__file__).parents[1]
CATALOG = json.loads((ROOT / "evals" / "cases.json").read_text(encoding="utf-8"))


class EvalCompareTests(unittest.TestCase):
    def paired_results(self) -> tuple[dict, dict]:
        builtin = sample_result()
        evidence = copy.deepcopy(builtin)
        evidence["run"]["id"] = "pilot-evidence-20260830"
        evidence["run"]["mode"] = "evidence"
        return builtin, evidence

    def test_compatible_results_are_aggregated(self) -> None:
        builtin, evidence = self.paired_results()
        result = compare_results([builtin, evidence], CATALOG)
        self.assertEqual(result["verdict"], "PASS", result["issues"])
        self.assertTrue(result["compatible"])
        self.assertEqual(len(result["runs"]), 2)
        self.assertEqual(result["runs"][0]["desired_behaviors"], {"passed": 3, "total": 3})

    def test_model_mismatch_fails_closed(self) -> None:
        builtin, evidence = self.paired_results()
        evidence["run"]["model"] = "different-model"
        result = compare_results([builtin, evidence], CATALOG)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn(
            "compare.fingerprint_mismatch",
            {item["code"] for item in result["issues"]},
        )

    def test_duplicate_mode_fails(self) -> None:
        builtin, evidence = self.paired_results()
        evidence["run"]["mode"] = "builtin"
        result = compare_results([builtin, evidence], CATALOG)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("compare.duplicate_mode", {item["code"] for item in result["issues"]})

    def test_v2_suite_or_repeat_mismatch_fails_closed(self) -> None:
        builtin = sample_result_v2()
        evidence = copy.deepcopy(builtin)
        evidence["run"]["id"] = "pilot-evidence-20260830"
        evidence["run"]["mode"] = "evidence"
        evidence["run"]["repeat"] = 2
        result = compare_results([builtin, evidence], CATALOG)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn(
            "compare.fingerprint_mismatch",
            {item["code"] for item in result["issues"]},
        )

    def test_schema_mismatch_fails_closed(self) -> None:
        builtin = sample_result()
        evidence = sample_result_v2()
        evidence["run"]["id"] = "pilot-evidence-20260830"
        evidence["run"]["mode"] = "evidence"
        result = compare_results([builtin, evidence], CATALOG)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("compare.schema_mismatch", {item["code"] for item in result["issues"]})


if __name__ == "__main__":
    unittest.main()
