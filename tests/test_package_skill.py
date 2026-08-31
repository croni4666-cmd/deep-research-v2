from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.package_skill import package_skill

ROOT = Path(__file__).parents[1]


class PackageSkillTests(unittest.TestCase):
    def test_minimax_package_is_minimal_and_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = package_skill(ROOT, Path(temporary), "minimax")
            manifest = json.loads((destination / "PACKAGE.json").read_text())
            self.assertEqual(manifest["target"], "minimax")
            self.assertEqual(manifest["version"], "2.6.1")
            self.assertTrue((destination / "SKILL.md").is_file())
            self.assertTrue((destination / "references" / "source-access.md").is_file())
            self.assertTrue((destination / "scripts" / "runtime_check.py").is_file())
            self.assertFalse((destination / "evals").exists())

    def test_existing_destination_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            package_skill(ROOT, output, "codex")
            with self.assertRaises(FileExistsError):
                package_skill(ROOT, output, "codex")

    def test_packaged_minimax_helpers_execute_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            destination = package_skill(ROOT, output, "minimax")
            runtime_manifest = output / "runtime.json"
            runtime_manifest.write_text(
                json.dumps({
                    "schema_version": 1,
                    "runtime": "minimax-conformance-test",
                    "skill_loaded": True,
                    "search": True,
                    "open_url": True,
                    "read_local_files": True,
                }),
                encoding="utf-8",
            )
            runtime = subprocess.run(
                [sys.executable, str(destination / "scripts" / "runtime_check.py"),
                 str(runtime_manifest), "--json"],
                cwd=destination,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(runtime.returncode, 0, runtime.stderr)
            self.assertEqual(json.loads(runtime.stdout)["profile"], "native")

            audit = subprocess.run(
                [sys.executable, str(destination / "scripts" / "evidence_audit.py"),
                 str(destination / "references" / "evidence-ledger-example.json"),
                 "--strict"],
                cwd=destination,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(audit.returncode, 0, audit.stderr)
            self.assertIn("STRUCTURAL_PASS", audit.stdout)


if __name__ == "__main__":
    unittest.main()
