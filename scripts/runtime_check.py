"""Classify a declared agent runtime for portable Skill execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REQUIRED_BOOLEAN_FIELDS = ("skill_loaded", "search", "open_url", "read_local_files")
OPTIONAL_BOOLEAN_FIELDS = ("write_local_files", "shell", "mcp", "subagents")
BOOLEAN_FIELDS = REQUIRED_BOOLEAN_FIELDS + OPTIONAL_BOOLEAN_FIELDS


def classify_runtime(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return {"verdict": "FAIL", "profile": "invalid", "errors": [
            "manifest must be a JSON object"
        ]}
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not isinstance(data.get("runtime"), str) or not data["runtime"].strip():
        errors.append("runtime must be a non-empty string")
    for field in REQUIRED_BOOLEAN_FIELDS:
        if not isinstance(data.get(field), bool):
            errors.append(f"{field} must be a boolean")
    for field in OPTIONAL_BOOLEAN_FIELDS:
        if field in data and not isinstance(data[field], bool):
            errors.append(f"{field} must be a boolean when provided")
    if errors:
        return {"verdict": "FAIL", "profile": "invalid", "errors": errors}

    capabilities = {field: data.get(field, False) for field in BOOLEAN_FIELDS}

    if capabilities["skill_loaded"] and capabilities["search"] and capabilities["open_url"]:
        profile = "native"
        limitation = None
    elif capabilities["skill_loaded"] and capabilities["open_url"]:
        profile = "compatible"
        limitation = "Source discovery is constrained; use supplied or known sources."
    elif capabilities["skill_loaded"] and capabilities["read_local_files"]:
        profile = "compatible"
        limitation = "Offline sources only; do not claim live-web coverage."
    else:
        profile = "protocol-only"
        limitation = "Label output as a simulation, not a versioned Skill run."
    parallel_candidate = profile != "protocol-only" and capabilities["subagents"]
    return {
        "verdict": "PASS",
        "profile": profile,
        "runtime": data["runtime"].strip(),
        "model_identifier": data.get("model_identifier"),
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
        for error in result["errors"]:
            print(f"- ERROR: {error}")
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
