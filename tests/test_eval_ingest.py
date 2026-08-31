from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.eval_ingest import build_ingestion, extract_raw_metrics, write_report


class EvalIngestTests(unittest.TestCase):
    def test_extracts_unique_urls_and_duplicate_data_rows(self) -> None:
        text = """# Result

See [one](https://example.test/a) and https://example.test/a.

| Name | Score |
| --- | ---: |
| Alpha | 10 |
| Beta | 8 |
| Alpha | 10 |
"""
        result = extract_raw_metrics(text)
        self.assertEqual(result["automatic_metrics"]["source_count"], 1)
        self.assertGreater(result["automatic_metrics"]["output_word_count"], 0)
        self.assertEqual(
            result["automatic_checks"]["duplicate_table_row_count"], 1,
        )
        self.assertEqual(
            result["details"]["duplicate_table_rows"][0]["normalized_row"],
            ["alpha", "10"],
        )

    def test_does_not_emit_semantic_quality_judgments(self) -> None:
        result = extract_raw_metrics("A claim with https://example.test/source")
        serialized = json.dumps(result)
        for forbidden in (
            "primary_source_count",
            "citation_sample_supported",
            "unsupported_claims_in_sample",
            "supported_key_claim_count",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_ingestion_hashes_raw_and_rejects_unknown_case(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "manifest.json"
            raw = root / "raw.md"
            manifest.write_text(
                json.dumps({"cases": [{"id": "case-one"}]}), encoding="utf-8",
            )
            raw.write_text("Answer https://example.test/source", encoding="utf-8")
            report = build_ingestion(manifest, raw, "case-one")
            self.assertEqual(
                report["raw_output"]["sha256"],
                hashlib.sha256(raw.read_bytes()).hexdigest(),
            )
            with self.assertRaisesRegex(ValueError, "not declared"):
                build_ingestion(manifest, raw, "case-two")

    def test_report_writer_does_not_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "report.json"
            write_report(output, {"schema_version": 1})
            with self.assertRaises(FileExistsError):
                write_report(output, {"schema_version": 1})


if __name__ == "__main__":
    unittest.main()
