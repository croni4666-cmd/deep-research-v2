from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.eval_results import validate_results

ROOT = Path(__file__).parents[1]


class ArchivedResultTests(unittest.TestCase):
    def test_all_archived_json_results_still_validate(self) -> None:
        catalog = json.loads((ROOT / "evals" / "cases.json").read_text(encoding="utf-8"))
        paths = sorted((ROOT / "evals" / "results").glob("*.json"))
        self.assertTrue(paths)
        failures = {}
        for path in paths:
            data = json.loads(path.read_text(encoding="utf-8"))
            result = validate_results(data, catalog, allow_partial=True)
            if result["verdict"] != "PASS":
                failures[path.name] = result["issues"]
        self.assertEqual(failures, {})


if __name__ == "__main__":
    unittest.main()
