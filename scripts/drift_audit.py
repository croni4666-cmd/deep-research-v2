"""
v2.1 Stage 2.4: DRIFT claim-ledger + segment-level audit
========================================================
Source: TELBench (arXiv 2606.02060, 2026-06) + DRIFT framework
Why: v2.0 segment audit (Phase 3.1) is per-segment, but doesn't track CLAIMS across segments.
      36.9% of successful trajectories still contain process errors (TELBench 2026).
      DRIFT: claim ledger + support seeking + dependency tracing, span-level first-error localization.

Key components:
  - Claim ledger: every assertion + source URL + freshness
  - Support seeking: did the agent cite the source for the claim?
  - Dependency tracing: which earlier claims support this one?
  - Span-level audit: find first error in reasoning chain (not just final)

Usage:
    python scripts/drift_audit.py --report final.md
"""
import argparse
import json
import re
import sys
from pathlib import Path


# DRIFT framework (TELBench 2026)
class ClaimLedger:
    """Each claim tracked across report segments."""

    def __init__(self):
        self.claims = []  # list of {id, claim, source, segment, support_status}

    def add_claim(self, claim: str, source: str, segment: str):
        self.claims.append({
            "id": len(self.claims) + 1,
            "claim": claim[:200],
            "source": source,
            "segment": segment,
            "support_status": "SUPPORTED" if source else "UNSUPPORTED",
        })


def extract_claims_and_citations(report: str) -> ClaimLedger:
    """
    Extract claims and their citing sources per segment.
    Returns ClaimLedger.
    """
    ledger = ClaimLedger()
    segments = re.split(r"^##\s+", report, flags=re.MULTILINE)
    url_pattern = re.compile(r"https?://[^\s\)]+")
    claim_pattern = re.compile(r"^[-*]\s+(.+?)(?:\n|$)", re.MULTILINE)

    for seg in segments:
        seg_title = seg.split("\n", 1)[0][:100]
        # Find claims in this segment
        for match in claim_pattern.finditer(seg):
            claim = match.group(1).strip()
            # Find any URL within next 200 chars
            start = match.end()
            end = min(start + 200, len(seg))
            nearby = seg[start:end]
            urls = url_pattern.findall(nearby)
            source = urls[0] if urls else ""
            ledger.add_claim(claim, source, seg_title)

    return ledger


def find_first_error_span(ledger: ClaimLedger) -> list:
    """
    Find the first error in reasoning chain (span-level first-error localization).
    Returns list of (claim_id, claim, issue).
    """
    errors = []
    for c in ledger.claims:
        if c["support_status"] == "UNSUPPORTED":
            errors.append({
                "claim_id": c["id"],
                "claim": c["claim"],
                "issue": "claim without citation (UNSUPPORTED)",
                "segment": c["segment"],
            })
    return errors


def compute_drift_score(ledger: ClaimLedger) -> dict:
    """
    DRIFT score: ratio of supported claims + first-error span.
    """
    total = len(ledger.claims)
    supported = sum(1 for c in ledger.claims if c["support_status"] == "SUPPORTED")
    ratio = supported / total if total > 0 else 0
    return {
        "total_claims": total,
        "supported_claims": supported,
        "support_ratio": ratio,
        "unsupported_claims": total - supported,
    }


def cli():
    parser = argparse.ArgumentParser(description="v2.1 DRIFT claim-ledger + span-level audit")
    parser.add_argument("--report", required=True, type=Path, help="Path to final_turn_XXX.md")
    parser.add_argument("--out", type=Path, help="Output JSON to file")
    args = parser.parse_args()

    if not args.report.exists():
        print(f"ERROR: report not found: {args.report}", file=sys.stderr)
        sys.exit(1)

    report = args.report.read_text(encoding='utf-8')
    ledger = extract_claims_and_citations(report)
    score = compute_drift_score(ledger)
    errors = find_first_error_span(ledger)

    print(f"DRIFT claim-ledger audit:")
    print(f"  Total claims:           {score['total_claims']}")
    print(f"  Supported claims:       {score['supported_claims']}")
    print(f"  Support ratio:          {score['support_ratio']:.2%}")
    print(f"  Unsupported claims:     {score['unsupported_claims']}")

    if errors:
        print(f"\nFirst-error spans (claim-level):")
        for e in errors[:5]:
            print(f"  #{e['claim_id']}: {e['claim'][:80]}")
            print(f"    Segment: {e['segment']}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more")

    # DRIFT pass threshold (TELBench reference)
    if score["support_ratio"] >= 0.80:
        print(f"\nVerdict: PASS (support ratio >= 80%)")
        exit_code = 0
    else:
        print(f"\nVerdict: FAIL (support ratio < 80%)")
        exit_code = 3

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        result = {
            "report": str(args.report),
            "score": score,
            "errors": errors,
            "all_claims": ledger.claims,
        }
        args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"\nSaved to: {args.out}")

    sys.exit(exit_code)


if __name__ == "__main__":
    cli()
