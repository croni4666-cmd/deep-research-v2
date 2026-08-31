from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from scripts.eval_bundle import create_bundle, validate_bundle

ROOT = Path(__file__).parents[1]


class EvalBundleTests(unittest.TestCase):
    def test_bundle_is_collision_safe_and_excludes_ground_truth(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            arguments = {
                "root": ROOT,
                "suites_path": ROOT / "evals" / "suites.json",
                "catalog_path": ROOT / "evals" / "cases.json",
                "suite_id": "offline-independence-v1",
                "mode": "evidence",
                "model": "test-model",
                "output_parent": output,
                "repeat": 1,
                "tools": ["local fixture reader"],
                "now": datetime(2026, 8, 31, 1, 2, 3, tzinfo=UTC),
            }
            first, first_manifest = create_bundle(**arguments)
            second, _ = create_bundle(**arguments)
            self.assertNotEqual(first, second)
            self.assertTrue((first / "manifest.json").is_file())
            loaded = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(loaded, first_manifest)
            candidate_paths = [
                item["path"]
                for case in loaded["cases"]
                for item in case["candidate_files"]
            ]
            self.assertTrue(candidate_paths)
            self.assertFalse(any("ground-truth" in path for path in candidate_paths))
            self.assertTrue(all("/sources/" in path for path in candidate_paths))
            validation = validate_bundle(first, ROOT)
            self.assertEqual(validation["verdict"], "PASS", validation["issues"])

            loaded["cases"][0]["prompt"] += " tampered"
            (first / "manifest.json").write_text(
                json.dumps(loaded, indent=2) + "\n",
                encoding="utf-8",
            )
            validation = validate_bundle(first, ROOT)
            self.assertEqual(validation["verdict"], "FAIL")
            self.assertIn(
                "bundle.prompt_hash_mismatch",
                {item["code"] for item in validation["issues"]},
            )

    def test_mode_must_be_declared_by_suite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "not declared"):
                create_bundle(
                    root=ROOT,
                    suites_path=ROOT / "evals" / "suites.json",
                    catalog_path=ROOT / "evals" / "cases.json",
                    suite_id="routing-smoke-v1",
                    mode="builtin",
                    model="test-model",
                    output_parent=Path(temporary),
                )


if __name__ == "__main__":
    unittest.main()
