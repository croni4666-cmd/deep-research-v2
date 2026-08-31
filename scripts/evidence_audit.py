"""Validate an Evidence Deep Research claim/evidence ledger.

This checker validates traceability and fail-closed process invariants. It does
not decide whether a claim is true or whether a source entails the claim.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

IMPORTANCE_VALUES = {"key", "supporting"}
CLAIM_STATUS_VALUES = {"verified", "qualified", "unresolved"}
STANCE_VALUES = {"supports", "contradicts", "context"}
QUESTION_STATUS_VALUES = {"resolved", "qualified", "unresolved", "excluded"}
ACCESS_VALUES = {
    "full_text", "partial_text", "metadata_only", "blocked", "secondary_substitute",
}
SUPPORTING_ACCESS_VALUES = {"full_text", "partial_text", "secondary_substitute"}


def _issue(issues: list[dict[str, str]], severity: str, code: str,
           path: str, message: str) -> None:
    issues.append({
        "severity": severity,
        "code": code,
        "path": path,
        "message": message,
    })


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_http_url(value: Any) -> bool:
    if not _nonempty_text(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _valid_iso_date(value: Any, *, optional: bool = False) -> bool:
    if value in {None, ""}:
        return optional
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def audit_ledger(data: Any, *, min_key_sources: int = 2,
                 strict: bool = False) -> dict[str, Any]:
    """Return a deterministic structural audit result."""
    issues: list[dict[str, str]] = []

    if not isinstance(data, dict):
        _issue(issues, "error", "ledger.not_object", "$",
               "The ledger must be a JSON object.")
        return _finish(issues, 0, 0, strict)

    schema_version = data.get("schema_version")
    if schema_version not in {1, 2}:
        _issue(issues, "error", "ledger.schema_version", "$.schema_version",
               "schema_version must be 1 or 2.")

    questions = data.get("research_questions", [])
    if not isinstance(questions, list):
        _issue(issues, "error", "questions.not_array", "$.research_questions",
               "research_questions must be an array.")
        questions = []
    elif not questions:
        _issue(issues, "warning", "questions.empty", "$.research_questions",
               "No research questions were recorded.")

    question_ids: set[str] = set()
    for index, question in enumerate(questions):
        path = f"$.research_questions[{index}]"
        if not isinstance(question, dict):
            _issue(issues, "error", "question.not_object", path,
                   "Each research question must be an object.")
            continue
        qid = question.get("id")
        if not _nonempty_text(qid):
            _issue(issues, "error", "question.missing_id", f"{path}.id",
                   "A non-empty id is required.")
        elif qid in question_ids:
            _issue(issues, "error", "question.duplicate_id", f"{path}.id",
                   f"Duplicate research question id: {qid}")
        else:
            question_ids.add(qid)
        if not _nonempty_text(question.get("question")):
            _issue(issues, "error", "question.missing_text", f"{path}.question",
                   "A non-empty question is required.")
        if question.get("status") not in QUESTION_STATUS_VALUES:
            _issue(issues, "error", "question.invalid_status", f"{path}.status",
                   "status must be resolved, qualified, unresolved, or excluded.")

    claims = data.get("claims")
    if not isinstance(claims, list):
        _issue(issues, "error", "claims.not_array", "$.claims",
               "claims must be an array.")
        claims = []
    if not claims:
        _issue(issues, "error", "claims.empty", "$.claims",
               "At least one claim is required; an empty audit cannot pass.")

    claim_ids: set[str] = set()
    evidence_count = 0
    access_counts = {value: 0 for value in sorted(ACCESS_VALUES)}
    legacy_access_count = 0
    for index, claim in enumerate(claims):
        path = f"$.claims[{index}]"
        if not isinstance(claim, dict):
            _issue(issues, "error", "claim.not_object", path,
                   "Each claim must be an object.")
            continue

        claim_id = claim.get("id")
        if not _nonempty_text(claim_id):
            _issue(issues, "error", "claim.missing_id", f"{path}.id",
                   "A non-empty id is required.")
        elif claim_id in claim_ids:
            _issue(issues, "error", "claim.duplicate_id", f"{path}.id",
                   f"Duplicate claim id: {claim_id}")
        else:
            claim_ids.add(claim_id)

        if not _nonempty_text(claim.get("claim")):
            _issue(issues, "error", "claim.missing_text", f"{path}.claim",
                   "A non-empty claim is required.")
        importance = claim.get("importance")
        if importance not in IMPORTANCE_VALUES:
            _issue(issues, "error", "claim.invalid_importance",
                   f"{path}.importance", "importance must be key or supporting.")
        status = claim.get("status")
        if status not in CLAIM_STATUS_VALUES:
            _issue(issues, "error", "claim.invalid_status", f"{path}.status",
                   "status must be verified, qualified, or unresolved.")

        evidence = claim.get("evidence", [])
        if not isinstance(evidence, list):
            _issue(issues, "error", "evidence.not_array", f"{path}.evidence",
                   "evidence must be an array.")
            evidence = []
        evidence_count += len(evidence)
        if status in {"verified", "qualified"} and not evidence:
            _issue(issues, "error", "claim.missing_evidence", f"{path}.evidence",
                   "Verified and qualified claims require evidence.")

        support_groups: set[str] = set()
        source_ids: set[str] = set()
        has_contradiction = False
        for evidence_index, item in enumerate(evidence):
            item_path = f"{path}.evidence[{evidence_index}]"
            if not isinstance(item, dict):
                _issue(issues, "error", "evidence.not_object", item_path,
                       "Each evidence item must be an object.")
                continue

            required_text = ("source_id", "title", "publisher", "independence_group")
            for field in required_text:
                if not _nonempty_text(item.get(field)):
                    _issue(issues, "error", f"evidence.missing_{field}",
                           f"{item_path}.{field}", f"{field} is required.")

            source_id = item.get("source_id")
            if _nonempty_text(source_id):
                if source_id in source_ids:
                    _issue(issues, "warning", "evidence.duplicate_source_id",
                           f"{item_path}.source_id",
                           f"source_id {source_id} is repeated within the claim.")
                source_ids.add(source_id)

            if not _valid_http_url(item.get("url")):
                _issue(issues, "error", "evidence.invalid_url", f"{item_path}.url",
                       "url must be an absolute http or https URL.")
            if not _valid_iso_date(item.get("accessed_at")):
                _issue(issues, "error", "evidence.invalid_accessed_at",
                       f"{item_path}.accessed_at",
                       "accessed_at must be an ISO date (YYYY-MM-DD).")
            if not _valid_iso_date(item.get("published_at"), optional=True):
                _issue(issues, "error", "evidence.invalid_published_at",
                       f"{item_path}.published_at",
                       "published_at must be empty or an ISO date (YYYY-MM-DD).")

            access = item.get("access")
            if schema_version == 2:
                if access not in ACCESS_VALUES:
                    _issue(issues, "error", "evidence.invalid_access",
                           f"{item_path}.access",
                           f"access must be one of {sorted(ACCESS_VALUES)}.")
                else:
                    access_counts[access] += 1
                if access in SUPPORTING_ACCESS_VALUES:
                    for field in ("location", "excerpt"):
                        if not _nonempty_text(item.get(field)):
                            _issue(issues, "error", f"evidence.missing_{field}",
                                   f"{item_path}.{field}", f"{field} is required.")
                elif access in {"metadata_only", "blocked"} and not _nonempty_text(
                        item.get("access_note")):
                    _issue(issues, "error", "evidence.missing_access_note",
                           f"{item_path}.access_note",
                           "metadata-only and blocked sources require an access_note.")
            else:
                legacy_access_count += 1
                for field in ("location", "excerpt"):
                    if not _nonempty_text(item.get(field)):
                        _issue(issues, "error", f"evidence.missing_{field}",
                               f"{item_path}.{field}", f"{field} is required.")

            stance = item.get("stance")
            if stance not in STANCE_VALUES:
                _issue(issues, "error", "evidence.invalid_stance",
                       f"{item_path}.stance",
                       "stance must be supports, contradicts, or context.")
            elif stance == "supports" and _nonempty_text(item.get("independence_group")):
                if schema_version == 2 and access not in SUPPORTING_ACCESS_VALUES:
                    _issue(issues, "error", "evidence.uninspectable_support",
                           item_path,
                           "Blocked or metadata-only material cannot support a claim.")
                else:
                    support_groups.add(item["independence_group"].strip())
            elif stance == "contradicts":
                has_contradiction = True

        if status == "verified" and importance == "key" and \
                len(support_groups) < min_key_sources:
            _issue(
                issues,
                "error",
                "claim.insufficient_independence",
                f"{path}.evidence",
                f"A verified key claim needs {min_key_sources} supporting "
                f"independence groups; found {len(support_groups)}.",
            )
        if status == "verified" and has_contradiction and not (
                claim.get("limitations") or _nonempty_text(claim.get("notes"))):
            _issue(issues, "warning", "claim.unaddressed_contradiction", path,
                   "Contradictory evidence exists but no limitation or note addresses it.")

    result = _finish(issues, len(claims), evidence_count, strict)
    result["access_counts"] = access_counts
    result["inspectable_evidence_count"] = sum(
        access_counts[value] for value in SUPPORTING_ACCESS_VALUES
    )
    result["legacy_unspecified_access_count"] = legacy_access_count
    return result


def _finish(issues: list[dict[str, str]], claim_count: int,
            evidence_count: int, strict: bool) -> dict[str, Any]:
    errors = sum(issue["severity"] == "error" for issue in issues)
    warnings = sum(issue["severity"] == "warning" for issue in issues)
    passed = errors == 0 and (warnings == 0 or not strict)
    return {
        "verdict": "PASS" if passed else "FAIL",
        "strict": strict,
        "claim_count": claim_count,
        "evidence_count": evidence_count,
        "error_count": errors,
        "warning_count": warnings,
        "issues": issues,
        "audit_scope": "structural",
        "scope_note": (
            "Structural audit only; factual correctness and citation entailment "
            "were not evaluated."
        ),
    }


def load_ledger(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a structured Evidence Deep Research ledger."
    )
    parser.add_argument("ledger", type=Path, help="Path to the ledger JSON file")
    parser.add_argument(
        "--min-key-sources", type=int, default=2, metavar="N",
        help="Minimum independent supporting evidence groups for verified key claims",
    )
    parser.add_argument(
        "--strict", action="store_true", help="Treat warnings as audit failures"
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args(argv)

    if args.min_key_sources < 1:
        parser.error("--min-key-sources must be at least 1")
    if not args.ledger.is_file():
        print(f"ERROR: ledger not found: {args.ledger}", file=sys.stderr)
        return 2
    try:
        data = load_ledger(args.ledger)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: could not read ledger: {exc}", file=sys.stderr)
        return 2

    result = audit_ledger(
        data, min_key_sources=args.min_key_sources, strict=args.strict
    )
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        label = "STRUCTURAL_PASS" if result["verdict"] == "PASS" else "STRUCTURAL_FAIL"
        print(
            f"{label}: {result['claim_count']} claims, "
            f"{result['evidence_count']} evidence items, "
            f"{result['error_count']} errors, {result['warning_count']} warnings"
        )
        for issue in result["issues"]:
            print(
                f"- {issue['severity'].upper()} {issue['code']} "
                f"{issue['path']}: {issue['message']}"
            )
        print(result["scope_note"])
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
