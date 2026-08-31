from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.release_check import check_release

ROOT = Path(__file__).parents[1]


class ReleaseCheckTests(unittest.TestCase):
    def test_repository_release_metadata_is_consistent(self) -> None:
        result = check_release(ROOT, "2.7.2")
        self.assertEqual(result["verdict"], "PASS", result["issues"])

    def test_mismatched_skill_version_and_unreleased_date_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "test"\nversion = "2.4.0"\n', encoding="utf-8",
            )
            (root / "SKILL.md").write_text(
                "---\nmetadata:\n  version: 2.3.0\n---\n", encoding="utf-8",
            )
            (root / "CHANGELOG.md").write_text(
                "## 2.4.0 - Unreleased\n", encoding="utf-8",
            )
            (root / "README.md").write_text(
                "## What changed in 2.3.0\n", encoding="utf-8",
            )
            result = check_release(root, "2.4.0")
            self.assertEqual(result["verdict"], "FAIL")
            codes = {item["code"] for item in result["issues"]}
            self.assertIn("release.skill_version", codes)
            self.assertIn("release.invalid_date", codes)
            self.assertIn("release.stale_readme", codes)


if __name__ == "__main__":
    unittest.main()
