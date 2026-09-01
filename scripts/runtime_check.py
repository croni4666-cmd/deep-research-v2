"""Classify a declared agent runtime for portable Skill execution."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED_BOOLEAN_FIELDS = ("search", "open_url", "read_local_files")
OPTIONAL_BOOLEAN_FIELDS = ("write_local_files", "shell", "mcp", "subagents")
BOOLEAN_FIELDS = REQUIRED_BOOLEAN_FIELDS + OPTIONAL_BOOLEAN_FIELDS
LOAD_STATUSES = {"verified", "partial", "false"}
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-fA-F]{64}$")


def classify_runtime(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return {"verdict": "FAIL", "profile": "invalid", "errors": [
            "manifest must be a JSON object"
        ]}
    schema_version = data.get("schema_version")
    if schema_version not in {1, 2}:
        errors.append("schema_version must be 1 or 2")
    if not isinstance(data.get("runtime"), str) or not data["runtime"].strip():
        errors.append("runtime must be a non-empty string")
    for field in REQUIRED_BOOLEAN_FIELDS:
        if not isinstance(data.get(field), bool):
            errors.append(f"{field} must be a boolean")
    for field in OPTIONAL_BOOLEAN_FIELDS:
        if field in data and not isinstance(data[field], bool):
            errors.append(f"{field} must be a boolean when provided")
    warnings: list[str] = []
    if schema_version == 1:
        if not isinstance(data.get("skill_loaded"), bool):
            errors.append("skill_loaded must be a boolean in schema version 1")
        load_status = "partial" if data.get("skill_loaded") is True else "false"
        warnings.append(
            "Legacy skill_loaded boolean cannot distinguish full loading from partial access; "
            "use schema version 2."
        )
    else:
        load_status = data.get("skill_load_status")
        if load_status not in LOAD_STATUSES:
            errors.append(f"skill_load_status must be one of {sorted(LOAD_STATUSES)}")
        if "skill_loaded" in data:
            errors.append("skill_loaded is not valid in schema version 2; use skill_load_status")
        loaded_from = data.get("loaded_from")
        if loaded_from is not None and (
            not isinstance(loaded_from, str) or not loaded_from.strip()
        ):
            errors.append("loaded_from must be a non-empty string when provided")
        content_hash = data.get("skill_content_hash")
        if content_hash is not None and (
            not isinstance(content_hash, str) or not SHA256_PATTERN.fullmatch(content_hash)
        ):
            errors.append("skill_content_hash must use sha256:<64 hex characters>")
        if load_status == "verified" and not loaded_from:
            errors.append("verified loading requires loaded_from provenance")
        if load_status != "verified" and content_hash is not None:
            errors.append("skill_content_hash is allowed only when skill_load_status is verified")
    if errors:
        return {"verdict": "FAIL", "profile": "invalid", "errors": errors}

    capabilities = {field: data.get(field, False) for field in BOOLEAN_FIELDS}

    if load_status == "verified" and capabilities["search"] and capabilities["open_url"]:
        profile = "native"
        limitation = None
    elif load_status == "verified" and capabilities["open_url"]:
        profile = "compatible"
        limitation = "Source discovery is constrained; use supplied or known sources."
    elif load_status == "verified" and capabilities["read_local_files"]:
        profile = "compatible"
        limitation = "Offline sources only; do not claim live-web coverage."
    elif load_status == "partial":
        profile = "protocol-only"
        limitation = (
            "Only partial Skill access was declared; label the output protocol-assisted, "
            "not a complete versioned Skill run."
        )
    else:
        profile = "protocol-only"
        limitation = "Label output as a simulation, not a versioned Skill run."
    parallel_candidate = profile != "protocol-only" and capabilities["subagents"]
    return {
        "verdict": "PASS",
        "profile": profile,
        "runtime": data["runtime"].strip(),
        "model_identifier": data.get("model_identifier"),
        "skill_load_status": load_status,
        "loaded_from": data.get("loaded_from"),
        "skill_content_hash": data.get("skill_content_hash"),
        "classification_basis": (
            "Declared manifest values only; no runtime capability probing was performed."
        ),
        "capabilities": capabilities,
        "limitation": limitation,
        "optional_helpers_available": capabilities["read_local_files"] and capabilities["shell"],
        "parallel_research_candidate": parallel_candidate,
        "parallel_research_note": (
            "Candidate only; confirm that workers inherit the required source tools."
            if parallel_candidate else
            "Use serial research unless real worker capability is declared and available."
        ),
        "warnings": warnings,
        "errors": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: could not read manifest: {exc}", file=sys.stderr)
        return 2
    result = classify_runtime(data)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"{result['verdict']}: profile={result['profile']}")
        if result.get("limitation"):
            print(result["limitation"])
        for warning in result.get("warnings", []):
            print(f"- WARNING: {warning}")
        for error in result["errors"]:
            print(f"- ERROR: {error}")
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
