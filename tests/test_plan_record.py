from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from scripts.plan_record import (
    build_approval_receipt,
    build_plan_document,
    compute_plan_hash,
    compute_receipt_hash,
    default_approval_path,
    main,
    verify_approval,
)


class PlanRecordTests(unittest.TestCase):
    def test_new_plan_is_pending_and_self_consistent(self) -> None:
        plan = build_plan_document(
            "A research topic", "CN", 3, created_at="2026-09-01T00:00:00Z"
        )
        self.assertEqual(plan["approval_status"], "pending")
        self.assertEqual(plan["plan_hash"], compute_plan_hash(plan))
        valid, issues = verify_approval(plan, None)
        self.assertFalse(valid)
        self.assertIn("no approval receipt supplied", issues)

    def test_receipt_matches_exact_plan_hash(self) -> None:
        path = Path("research-plan.json")
        plan = build_plan_document(
            "A research topic", created_at="2026-09-01T00:00:00Z"
        )
        receipt = build_approval_receipt(
            path,
            plan,
            "conversation turn 42",
            approved_at="2026-09-01T00:01:00Z",
        )
        valid, issues = verify_approval(plan, receipt)
        self.assertTrue(valid, issues)
        self.assertEqual(receipt["plan_hash"], plan["plan_hash"])
        self.assertEqual(receipt["receipt_hash"], compute_receipt_hash(receipt))

    def test_plan_drift_invalidates_old_receipt(self) -> None:
        path = Path("research-plan.json")
        plan = build_plan_document(
            "Original topic", created_at="2026-09-01T00:00:00Z"
        )
        receipt = build_approval_receipt(path, plan, "user approval message")
        plan["plan"]["topic"] = "Changed topic"
        plan["plan_hash"] = compute_plan_hash(plan)
        valid, issues = verify_approval(plan, receipt)
        self.assertFalse(valid)
        self.assertIn("approval receipt does not match the current plan hash", issues)

    def test_tampering_without_rehashing_is_detected(self) -> None:
        plan = build_plan_document(
            "Original topic", created_at="2026-09-01T00:00:00Z"
        )
        receipt = build_approval_receipt(Path("plan.json"), plan, "turn 7")
        plan["plan"]["region"] = "Changed region"
        valid, issues = verify_approval(plan, receipt)
        self.assertFalse(valid)
        self.assertIn("stored plan_hash does not match current plan content", issues)

    def test_receipt_tampering_without_rehashing_is_detected(self) -> None:
        plan = build_plan_document(
            "Original topic", created_at="2026-09-01T00:00:00Z"
        )
        receipt = build_approval_receipt(Path("plan.json"), plan, "turn 7")
        receipt["approval_reference"] = "changed reference"
        valid, issues = verify_approval(plan, receipt)
        self.assertFalse(valid)
        self.assertIn(
            "stored receipt_hash does not match current receipt content", issues
        )

    def test_legacy_receipt_requires_re_recording(self) -> None:
        plan = build_plan_document("topic")
        receipt = build_approval_receipt(Path("plan.json"), plan, "turn 7")
        receipt["schema_version"] = 1
        receipt.pop("receipt_hash")
        valid, issues = verify_approval(plan, receipt)
        self.assertFalse(valid)
        self.assertIn(
            "legacy approval schema 1 has no receipt integrity hash; re-record approval",
            issues,
        )

    def test_cli_create_approve_verify_and_collision_safety(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plan_path = Path(temporary) / "research-plan.json"
            with redirect_stdout(StringIO()):
                self.assertEqual(
                    main(["create", "--topic", "topic", "--out", str(plan_path)]),
                    0,
                )
            with redirect_stderr(StringIO()):
                self.assertEqual(
                    main(["create", "--topic", "other", "--out", str(plan_path)]),
                    2,
                )
            self.assertEqual(json.loads(plan_path.read_text())["plan"]["topic"], "topic")

            with redirect_stdout(StringIO()):
                self.assertEqual(
                    main([
                        "approve",
                        str(plan_path),
                        "--approval-reference",
                        "conversation turn 9",
                    ]),
                    0,
                )
                self.assertEqual(main(["verify", str(plan_path)]), 0)
            self.assertTrue(default_approval_path(plan_path).is_file())

    def test_empty_approval_reference_is_rejected(self) -> None:
        plan = build_plan_document("topic")
        with self.assertRaises(ValueError):
            build_approval_receipt(Path("plan.json"), plan, "   ")


if __name__ == "__main__":
    unittest.main()
