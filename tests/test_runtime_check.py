from __future__ import annotations

import unittest

from scripts.runtime_check import BOOLEAN_FIELDS, classify_runtime


def manifest(**overrides: bool | str) -> dict:
    data = {
        "schema_version": 2,
        "runtime": "test-runtime",
        "model_identifier": "m1",
        "skill_load_status": "verified",
        "loaded_from": "C:/skills/evidence-deep-research/SKILL.md",
    }
    data.update({field: False for field in BOOLEAN_FIELDS})
    data.update(overrides)
    return data


class RuntimeCheckTests(unittest.TestCase):
    def test_search_and_open_is_native(self) -> None:
        result = classify_runtime(manifest(search=True, open_url=True))
        self.assertEqual(result["profile"], "native")
        self.assertFalse(result["parallel_research_candidate"])

    def test_real_subagent_capability_marks_parallel_candidate(self) -> None:
        result = classify_runtime(manifest(
            search=True, open_url=True, subagents=True,
        ))
        self.assertTrue(result["parallel_research_candidate"])
        self.assertIn("confirm", result["parallel_research_note"])

    def test_loaded_offline_skill_is_compatible(self) -> None:
        result = classify_runtime(manifest(read_local_files=True))
        self.assertEqual(result["profile"], "compatible")
        self.assertIn("Offline", result["limitation"])

    def test_unloaded_skill_is_protocol_only(self) -> None:
        result = classify_runtime(manifest(
            skill_load_status="false", search=True, open_url=True,
        ))
        self.assertEqual(result["profile"], "protocol-only")

    def test_missing_boolean_fails(self) -> None:
        data = manifest()
        data.pop("open_url")
        result = classify_runtime(data)
        self.assertEqual(result["verdict"], "FAIL")

    def test_optional_fields_default_false(self) -> None:
        data = {
            "schema_version": 2,
            "runtime": "minimal-runtime",
            "skill_load_status": "verified",
            "loaded_from": "C:/skills/evidence-deep-research/SKILL.md",
            "search": True,
            "open_url": True,
            "read_local_files": False,
        }
        result = classify_runtime(data)
        self.assertEqual(result["profile"], "native")
        self.assertFalse(result["capabilities"]["mcp"])
        self.assertFalse(result["capabilities"]["subagents"])
        self.assertIn("no runtime capability probing", result["classification_basis"])

    def test_invalid_optional_field_fails(self) -> None:
        data = manifest()
        data["mcp"] = "unknown"
        result = classify_runtime(data)
        self.assertEqual(result["verdict"], "FAIL")

    def test_partial_load_is_protocol_only(self) -> None:
        result = classify_runtime(manifest(
            skill_load_status="partial", search=True, open_url=True,
        ))
        self.assertEqual(result["profile"], "protocol-only")
        self.assertIn("protocol-assisted", result["limitation"])

    def test_schema_two_rejects_legacy_skill_loaded(self) -> None:
        data = manifest()
        data["skill_loaded"] = True
        result = classify_runtime(data)
        self.assertEqual(result["verdict"], "FAIL")

    def test_verified_load_accepts_content_hash(self) -> None:
        result = classify_runtime(manifest(
            skill_content_hash="sha256:" + "a" * 64,
        ))
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["skill_load_status"], "verified")

    def test_partial_load_cannot_claim_content_hash(self) -> None:
        result = classify_runtime(manifest(
            skill_load_status="partial", skill_content_hash="sha256:" + "a" * 64,
        ))
        self.assertEqual(result["verdict"], "FAIL")

    def test_schema_one_remains_accepted_with_warning(self) -> None:
        data = {
            "schema_version": 1,
            "runtime": "legacy-runtime",
            "skill_loaded": True,
            "search": True,
            "open_url": True,
            "read_local_files": False,
        }
        result = classify_runtime(data)
        self.assertEqual(result["profile"], "protocol-only")
        self.assertEqual(result["skill_load_status"], "partial")
        self.assertTrue(result["warnings"])

    def test_verified_load_requires_provenance(self) -> None:
        data = manifest()
        data.pop("loaded_from")
        result = classify_runtime(data)
        self.assertEqual(result["verdict"], "FAIL")


if __name__ == "__main__":
    unittest.main()
