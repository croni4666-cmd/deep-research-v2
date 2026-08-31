"""Extract reproducible, non-semantic metrics from a raw evaluation answer."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

URL_PATTERN = re.compile(r'https?://[^\s<>\]}"\']+')
WORD_PATTERN = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*|[\u3400-\u9fff]")
TABLE_SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unique_urls(text: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for match in URL_PATTERN.finditer(text):
        url = match.group(0).rstrip(".,;:!?)]}'\"")
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _table_cells(line: str) -> tuple[str, ...] | None:
    stripped = line.strip()
    if "|" not in stripped:
        return None
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    cells = tuple(" ".join(cell.strip().casefold().split()) for cell in stripped.split("|"))
    return cells if len(cells) >= 2 and all(cells) else None


def _is_separator(cells: tuple[str, ...] | None) -> bool:
    return bool(cells) and all(TABLE_SEPARATOR_CELL.fullmatch(cell) for cell in cells)


def duplicate_table_rows(text: str) -> list[dict[str, Any]]:
    parsed = [_table_cells(line) for line in text.splitlines()]
    rows: list[tuple[str, ...]] = []
    for index, cells in enumerate(parsed):
        if cells is None or _is_separator(cells):
            continue
        next_cells = parsed[index + 1] if index + 1 < len(parsed) else None
        if _is_separator(next_cells):
            continue
        rows.append(cells)
    counts = Counter(rows)
    return [
        {"normalized_row": list(row), "occurrences": count}
        for row, count in sorted(counts.items())
        if count > 1
    ]


def extract_raw_metrics(text: str) -> dict[str, Any]:
    urls = _unique_urls(text)
    duplicate_rows = duplicate_table_rows(text)
    text_without_urls = URL_PATTERN.sub("", text)
    return {
        "automatic_metrics": {
            "output_word_count": len(WORD_PATTERN.findall(text_without_urls)),
            "source_count": len(urls),
        },
        "automatic_checks": {
            "duplicate_table_row_count": sum(
                item["occurrences"] - 1 for item in duplicate_rows
            ),
        },
        "details": {
            "unique_urls": urls,
            "duplicate_table_rows": duplicate_rows,
        },
    }


def build_ingestion(manifest_path: Path, raw_path: Path, case_id: str) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = manifest.get("cases") if isinstance(manifest, dict) else None
    if not isinstance(cases, list) or case_id not in {
        case.get("id") for case in cases if isinstance(case, dict)
    }:
        raise ValueError(f"Case {case_id!r} is not declared by the bundle manifest.")
    text = raw_path.read_text(encoding="utf-8")
    extracted = extract_raw_metrics(text)
    return {
        "schema_version": 1,
        "bundle_manifest": {
            "path": manifest_path.as_posix(),
            "sha256": sha256_file(manifest_path),
        },
        "raw_output": {
            "path": raw_path.as_posix(),
            "sha256": sha256_file(raw_path),
        },
        "case": {"id": case_id, **extracted},
        "scope_note": (
            "Automatic extraction counts lexical words, unique reported HTTP(S) URLs, and "
            "duplicate normalized Markdown table rows. It does not judge source primacy, "
            "citation entailment, claim support, or truth."
        ),
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"Output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    if temporary.exists():
        raise FileExistsError(f"Temporary output already exists: {temporary}")
    temporary.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("raw", type=Path)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_ingestion(args.manifest, args.raw, args.case_id)
        write_report(args.output, report)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: could not ingest raw output: {exc}", file=sys.stderr)
        return 2
    print(f"Created {args.output}")
    print(report["scope_note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
