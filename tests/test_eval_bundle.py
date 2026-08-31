from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from scripts.eval_bundle import (
    create_bundle,
    create_matrix,
    validate_bundle,
    validate_matrix,
)

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

    def test_offline_regression_bundle_exposes_only_candidate_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle, manifest = create_bundle(
                root=ROOT,
                suites_path=ROOT / "evals" / "suites.json",
                catalog_path=ROOT / "evals" / "cases.json",
                suite_id="offline-regression-v1",
                mode="evidence",
                model="test-model",
                output_parent=Path(temporary),
            )
            self.assertEqual(len(manifest["cases"]), 3)
            candidate_paths = [
                item["path"]
                for case in manifest["cases"]
                for item in case["candidate_files"]
            ]
            self.assertGreaterEqual(len(candidate_paths), 7)
            self.assertTrue(all("/sources/" in path for path in candidate_paths))
            self.assertFalse(any("ground-truth" in path for path in candidate_paths))
            self.assertEqual(validate_bundle(bundle, ROOT)["verdict"], "PASS")

    def test_matrix_prepares_every_mode_and_repeat_and_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_dir, matrix = create_matrix(
                root=ROOT,
                suites_path=ROOT / "evals" / "suites.json",
                catalog_path=ROOT / "evals" / "cases.json",
                suite_id="offline-regression-v1",
                model="test-model",
                output_parent=Path(temporary),
                now=datetime(2026, 8, 31, 2, 3, 4, tzinfo=UTC),
            )
            self.assertEqual(matrix["expected_run_count"], 9)
            self.assertEqual(
                {(item["mode"], item["repeat"]) for item in matrix["bundles"]},
                {
                    (mode, repeat)
                    for mode in ("builtin", "evidence", "combined")
                    for repeat in (1, 2, 3)
                },
            )
            validation = validate_matrix(matrix_dir, ROOT)
            self.assertEqual(validation["verdict"], "PASS", validation["issues"])
            manifest = matrix_dir / matrix["bundles"][0]["path"] / "manifest.json"
            manifest.write_text(manifest.read_text(encoding="utf-8") + " ", encoding="utf-8")
            validation = validate_matrix(matrix_dir, ROOT)
            self.assertEqual(validation["verdict"], "FAIL")
            self.assertIn(
                "matrix.manifest_hash_mismatch",
                {item["code"] for item in validation["issues"]},
            )


if __name__ == "__main__":
    unittest.main()
