"""Create and verify an auditable research plan and approval receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from .plan_preview import build_plan
except ImportError:  # Direct execution from a packaged Skill.
    from plan_preview import build_plan


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def compute_plan_hash(document: dict[str, Any]) -> str:
    payload = dict(document)
    payload.pop("plan_hash", None)
    return "sha256:" + hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def build_plan_document(
    topic: str,
    region: str = "Global",
    depth: int = 3,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema_version": 1,
        "artifact_type": "research_plan",
        "created_at": created_at or _timestamp(),
        "approval_status": "pending",
        "plan": asdict(build_plan(topic, region, depth)),
    }
    document["plan_hash"] = compute_plan_hash(document)
    return document


def default_approval_path(plan_path: Path) -> Path:
    return plan_path.with_name(f"{plan_path.stem}.approval.json")


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _write_new(path: Path, value: dict[str, Any], force: bool) -> None:
    if path.exists() and not force:
        raise ValueError(f"output already exists: {path}; use --force to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def validate_plan(document: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if document.get("schema_version") != 1:
        issues.append("plan schema_version must be 1")
    if document.get("artifact_type") != "research_plan":
        issues.append("artifact_type must be research_plan")
    if document.get("approval_status") != "pending":
        issues.append("plan approval_status must remain pending; approval lives in a receipt")
    if not isinstance(document.get("plan"), dict):
        issues.append("plan must be an object")
    stored_hash = document.get("plan_hash")
    if not isinstance(stored_hash, str) or stored_hash != compute_plan_hash(document):
        issues.append("stored plan_hash does not match current plan content")
    return issues


def build_approval_receipt(
    plan_path: Path,
    document: dict[str, Any],
    approval_reference: str,
    *,
    approved_at: str | None = None,
) -> dict[str, Any]:
    reference = approval_reference.strip()
    if not reference:
        raise ValueError("approval_reference must describe the actual user approval")
    issues = validate_plan(document)
    if issues:
        raise ValueError("invalid plan: " + "; ".join(issues))
    return {
        "schema_version": 1,
        "artifact_type": "research_plan_approval",
        "status": "approved",
        "approved_at": approved_at or _timestamp(),
        "plan_file": plan_path.name,
        "plan_hash": document["plan_hash"],
        "approval_reference": reference,
        "attestation": (
            "Recorded after explicit user approval; this receipt is not independent "
            "proof that approval occurred."
        ),
    }


def verify_approval(
    document: dict[str, Any], receipt: dict[str, Any] | None
) -> tuple[bool, list[str]]:
    issues = validate_plan(document)
    if receipt is None:
        issues.append("no approval receipt supplied")
        return False, issues
    if receipt.get("schema_version") != 1:
        issues.append("approval schema_version must be 1")
    if receipt.get("artifact_type") != "research_plan_approval":
        issues.append("approval artifact_type must be research_plan_approval")
    if receipt.get("status") != "approved":
        issues.append("approval status must be approved")
    if not str(receipt.get("approval_reference", "")).strip():
        issues.append("approval_reference is missing")
    if receipt.get("plan_hash") != document.get("plan_hash"):
        issues.append("approval receipt does not match the current plan hash")
    return not issues, issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="Create an unapproved plan record")
    create.add_argument("--topic", required=True)
    create.add_argument("--region", default="Global")
    create.add_argument("--depth", type=int, choices=range(1, 6), default=3)
    create.add_argument("--out", type=Path, required=True)
    create.add_argument("--force", action="store_true")

    approve = commands.add_parser(
        "approve", help="Record approval already given by the user"
    )
    approve.add_argument("plan", type=Path)
    approve.add_argument("--approval-reference", required=True)
    approve.add_argument("--out", type=Path)
    approve.add_argument("--force", action="store_true")

    verify = commands.add_parser("verify", help="Check plan integrity and approval")
    verify.add_argument("plan", type=Path)
    verify.add_argument("--approval", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            document = build_plan_document(args.topic, args.region, args.depth)
            _write_new(args.out, document, args.force)
            print(f"PLAN_PENDING: {args.out} ({document['plan_hash']})")
            return 0

        document = _read_object(args.plan)
        if args.command == "approve":
            output = args.out or default_approval_path(args.plan)
            receipt = build_approval_receipt(
                args.plan, document, args.approval_reference
            )
            _write_new(output, receipt, args.force)
            print(f"APPROVAL_RECORDED: {output} ({receipt['plan_hash']})")
            return 0

        approval_path = args.approval or default_approval_path(args.plan)
        receipt = _read_object(approval_path) if approval_path.exists() else None
        valid, issues = verify_approval(document, receipt)
        if valid:
            print(f"APPROVED_CURRENT: {document['plan_hash']}")
            return 0
        print("NOT_APPROVED_CURRENT")
        for issue in issues:
            print(f"- {issue}")
        return 1
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
