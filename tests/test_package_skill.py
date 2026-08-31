from __future__ import annotations

import json
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
            self.assertEqual(manifest["version"], "2.6.0")
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


if __name__ == "__main__":
    unittest.main()
