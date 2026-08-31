from __future__ import annotations

import unittest

from scripts.runtime_check import BOOLEAN_FIELDS, classify_runtime


def manifest(**overrides: bool) -> dict:
    data = {"schema_version": 1, "runtime": "test-runtime", "model_identifier": "m1"}
    data.update({field: False for field in BOOLEAN_FIELDS})
    data.update(overrides)
    return data


class RuntimeCheckTests(unittest.TestCase):
    def test_search_and_open_is_native(self) -> None:
        result = classify_runtime(manifest(skill_loaded=True, search=True, open_url=True))
        self.assertEqual(result["profile"], "native")

    def test_loaded_offline_skill_is_compatible(self) -> None:
        result = classify_runtime(manifest(skill_loaded=True, read_local_files=True))
        self.assertEqual(result["profile"], "compatible")
        self.assertIn("Offline", result["limitation"])

    def test_unloaded_skill_is_protocol_only(self) -> None:
        result = classify_runtime(manifest(search=True, open_url=True))
        self.assertEqual(result["profile"], "protocol-only")

    def test_missing_boolean_fails(self) -> None:
        data = manifest()
        data.pop("mcp")
        result = classify_runtime(data)
        self.assertEqual(result["verdict"], "FAIL")


if __name__ == "__main__":
    unittest.main()
