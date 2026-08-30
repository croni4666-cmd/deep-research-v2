from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from scripts.plan_preview import build_plan, main, render_markdown


class PlanPreviewTests(unittest.TestCase):
    def test_plan_is_explicitly_unverified(self) -> None:
        plan = build_plan("A research topic", "CN", 3)
        self.assertEqual(plan.status, "plan_only")
        self.assertFalse(plan.verified)
        self.assertIn("no research performed", render_markdown(plan))

    def test_depth_is_bounded(self) -> None:
        with self.assertRaises(ValueError):
            build_plan("topic", depth=0)
        with self.assertRaises(ValueError):
            build_plan("topic", depth=6)

    def test_existing_output_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "plan.md"
            output.write_text("keep me", encoding="utf-8")
            with redirect_stderr(StringIO()):
                result = main(["--topic", "topic", "--out", str(output)])
            self.assertEqual(result, 2)
            self.assertEqual(output.read_text(encoding="utf-8"), "keep me")

    def test_force_replaces_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "plan.md"
            output.write_text("old", encoding="utf-8")
            with redirect_stdout(StringIO()):
                result = main(
                    ["--topic", "topic", "--out", str(output), "--force"]
                )
            self.assertEqual(result, 0)
            self.assertIn("# Research plan: topic", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
