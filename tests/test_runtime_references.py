from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
RUNTIME_MARKDOWN = [ROOT / "SKILL.md", *sorted((ROOT / "steps").glob("*.md")),
                    *sorted((ROOT / "references").glob("*.md"))]
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


class RuntimeReferenceTests(unittest.TestCase):
    def test_all_relative_runtime_links_resolve(self) -> None:
        missing: list[str] = []
        for document in RUNTIME_MARKDOWN:
            text = document.read_text(encoding="utf-8")
            for target in LINK_PATTERN.findall(text):
                if "://" in target or target.startswith("#"):
                    continue
                resolved = (document.parent / target.split("#", 1)[0]).resolve()
                if not resolved.is_file():
                    missing.append(f"{document.relative_to(ROOT)} -> {target}")
        self.assertEqual(missing, [])

    def test_portable_depth_references_are_runtime_files(self) -> None:
        expected = {
            "region-source-routing.md", "transferability.md", "parallel-research.md",
        }
        actual = {path.name for path in (ROOT / "references").glob("*.md")}
        self.assertTrue(expected <= actual)


if __name__ == "__main__":
    unittest.main()
