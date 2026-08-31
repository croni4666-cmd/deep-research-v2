from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.evidence_audit import audit_ledger

ROOT = Path(__file__).parents[1]


def evidence(source_id: str, group: str, url: str) -> dict:
    return {
        "source_id": source_id,
        "url": url,
        "title": f"Source {source_id}",
        "publisher": "Example publisher",
        "published_at": "2026-08-01",
        "accessed_at": "2026-08-30",
        "access": "full_text",
        "location": "Section 2",
        "excerpt": "The relevant inspected evidence.",
        "stance": "supports",
        "independence_group": group,
    }


def valid_ledger() -> dict:
    return {
        "schema_version": 2,
        "research_questions": [
            {"id": "RQ1", "question": "What is supported?", "status": "resolved"}
        ],
        "claims": [
            {
                "id": "C1",
                "claim": "A bounded key claim.",
                "importance": "key",
                "status": "verified",
                "evidence": [
                    evidence("S1", "dataset:one", "https://a.example/source"),
                    evidence("S2", "record:two", "https://b.example/source"),
                ],
                "limitations": [],
                "notes": "",
            }
        ],
    }


class EvidenceAuditTests(unittest.TestCase):
    def test_valid_ledger_passes(self) -> None:
        result = audit_ledger(valid_ledger())
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["error_count"], 0)
        self.assertEqual(result["audit_scope"], "structural")
        self.assertEqual(result["inspectable_evidence_count"], 2)

    def test_empty_claims_fail_closed(self) -> None:
        ledger = valid_ledger()
        ledger["claims"] = []
        result = audit_ledger(ledger)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("claims.empty", {item["code"] for item in result["issues"]})

    def test_arbitrary_urls_are_not_a_ledger(self) -> None:
        result = audit_ledger("https://a.example https://b.example https://c.example")
        self.assertEqual(result["verdict"], "FAIL")

    def test_different_hosts_same_underlying_evidence_fail(self) -> None:
        ledger = valid_ledger()
        ledger["claims"][0]["evidence"][1]["independence_group"] = "dataset:one"
        result = audit_ledger(ledger)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn(
            "claim.insufficient_independence",
            {item["code"] for item in result["issues"]},
        )

    def test_unresolved_claim_can_have_no_evidence(self) -> None:
        ledger = valid_ledger()
        claim = ledger["claims"][0]
        claim["status"] = "unresolved"
        claim["evidence"] = []
        result = audit_ledger(ledger)
        self.assertEqual(result["verdict"], "PASS")

    def test_warning_fails_in_strict_mode(self) -> None:
        ledger = valid_ledger()
        ledger["research_questions"] = []
        advisory = audit_ledger(ledger, strict=False)
        strict = audit_ledger(ledger, strict=True)
        self.assertEqual(advisory["verdict"], "PASS")
        self.assertEqual(strict["verdict"], "FAIL")

    def test_missing_location_fails(self) -> None:
        ledger = copy.deepcopy(valid_ledger())
        ledger["claims"][0]["evidence"][0]["location"] = ""
        result = audit_ledger(ledger)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn(
            "evidence.missing_location", {item["code"] for item in result["issues"]}
        )

    def test_invalid_url_fails(self) -> None:
        ledger = copy.deepcopy(valid_ledger())
        ledger["claims"][0]["evidence"][0]["url"] = "not-a-url"
        result = audit_ledger(ledger)
        self.assertEqual(result["verdict"], "FAIL")

    def test_metadata_only_material_cannot_support_claim(self) -> None:
        ledger = copy.deepcopy(valid_ledger())
        item = ledger["claims"][0]["evidence"][0]
        item["access"] = "metadata_only"
        item["access_note"] = "Only a registry record was inspectable."
        result = audit_ledger(ledger)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn(
            "evidence.uninspectable_support", {issue["code"] for issue in result["issues"]}
        )

    def test_schema_one_remains_backward_compatible(self) -> None:
        ledger = copy.deepcopy(valid_ledger())
        ledger["schema_version"] = 1
        for item in ledger["claims"][0]["evidence"]:
            item.pop("access")
        result = audit_ledger(ledger)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["legacy_unspecified_access_count"], 2)

    def test_complete_access_state_example_passes_strict(self) -> None:
        path = ROOT / "references" / "evidence-ledger-example.json"
        ledger = json.loads(path.read_text(encoding="utf-8"))
        result = audit_ledger(ledger, strict=True)
        self.assertEqual(result["verdict"], "PASS", result["issues"])
        self.assertEqual(
            result["access_counts"],
            {
                "blocked": 1,
                "full_text": 1,
                "metadata_only": 1,
                "partial_text": 1,
                "secondary_substitute": 1,
            },
        )

    def test_every_access_state_is_accepted_when_used_legally(self) -> None:
        for access in (
            "full_text", "partial_text", "metadata_only", "blocked",
            "secondary_substitute",
        ):
            with self.subTest(access=access):
                ledger = copy.deepcopy(valid_ledger())
                item = ledger["claims"][0]["evidence"][0]
                item["access"] = access
                if access in {"metadata_only", "blocked"}:
                    item["stance"] = "context"
                    item["access_note"] = "Content was not inspectable."
                result = audit_ledger(ledger)
                self.assertNotIn(
                    "evidence.invalid_access", {issue["code"] for issue in result["issues"]}
                )

    def test_invalid_optional_source_role_fails(self) -> None:
        ledger = copy.deepcopy(valid_ledger())
        ledger["claims"][0]["evidence"][0]["source_role"] = "local_language"
        result = audit_ledger(ledger)
        self.assertIn(
            "evidence.invalid_source_role", {issue["code"] for issue in result["issues"]}
        )

    def test_transfer_assessment_requires_adaptation_for_pilot(self) -> None:
        ledger = copy.deepcopy(valid_ledger())
        ledger["claims"][0]["transfer_assessment"] = {
            "source_context": "Region A",
            "target_context": "Region B",
            "level": "pilot_only",
            "rationale": "Local effects remain uncertain.",
            "adaptations": [],
        }
        result = audit_ledger(ledger)
        self.assertIn(
            "transfer.missing_adaptations", {issue["code"] for issue in result["issues"]}
        )

    def test_valid_transfer_assessment_passes(self) -> None:
        ledger = copy.deepcopy(valid_ledger())
        ledger["claims"][0]["transfer_assessment"] = {
            "source_context": "Region A",
            "target_context": "Region B",
            "level": "adaptation_required",
            "rationale": "The legal implementation mechanism differs.",
            "adaptations": ["Use the target jurisdiction's enforcement process."],
        }
        result = audit_ledger(ledger)
        self.assertEqual(result["verdict"], "PASS", result["issues"])


if __name__ == "__main__":
    unittest.main()
