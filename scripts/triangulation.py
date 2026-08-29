"""
v2.1 Step 1.2: Triangulation (>=3 independent sources + Cohen kappa)
========================================================================
Source: Triangulation in social science (mixed methods, 1960s+)
Why: v2.0 had v1.9.2 citation URL (>=1 source) but NO triangulation
      Real research needs >=3 independent sources per key claim + Cohen kappa >= 0.67

Usage:
    python scripts/triangulation.py --report final.md [--compute-kappa]
"""
import argparse
import json
import re
import sys
from pathlib import Path


# Cohen (1960) kappa interpretation
COHEN_KAPPA_INTERPRETATION = {
    (0.0, 0.20): "slight agreement",
    (0.21, 0.40): "fair agreement",
    (0.41, 0.60): "moderate agreement",
    (0.61, 0.80): "substantial agreement",
    (0.81, 1.00): "almost perfect agreement",
    (-1.0, 0.0): "less than chance agreement",
}

KAPPA_THRESHOLD = 0.67  # v2.1.0 quality control threshold (substantial+)


def extract_claims_with_sources(report: str) -> dict:
    """
    Extract claims and their citing sources.
    Returns: {claim_text: [source_urls]}
    """
    # Simple heuristic: each "key fact" line, find URLs in nearby lines
    # Real version: parse structured claim table or LLM-extract
    claim_pattern = re.compile(r"^[-*]\s+(.+?)(?:\n|$)", re.MULTILINE)
    url_pattern = re.compile(r"https?://[^\s\)]+")

    claims = {}
    for match in claim_pattern.finditer(report):
        claim_text = match.group(1).strip()
        # Find URLs within 200 chars after the claim
        start = match.end()
        end = min(start + 200, len(report))
        nearby = report[start:end]
        urls = url_pattern.findall(nearby)
        if urls:
            claims[claim_text] = urls

    return claims


def check_triangulation(claims: dict, min_sources: int = 3) -> dict:
    """
    Check each claim has >= min_sources independent sources.
    Independent = different domains (heuristic: different TLDs or hosts).
    """
    results = {"pass": [], "fail": []}
    for claim, urls in claims.items():
        # Extract unique hosts
        hosts = set()
        for url in urls:
            m = re.search(r"https?://([^/]+)/?", url)
            if m:
                hosts.add(m.group(1))
        if len(hosts) >= min_sources:
            results["pass"].append({"claim": claim, "urls": urls, "hosts": list(hosts)})
        else:
            results["fail"].append({
                "claim": claim,
                "urls": urls,
                "hosts": list(hosts),
                "n_sources": len(hosts),
                "n_needed": min_sources,
            })
    return results


def compute_cohen_kappa(claims_pass: int, claims_fail: int, total_n: int) -> float:
    """
    Compute Cohen's kappa coefficient (rough approximation).
    kappa = (po - pe) / (1 - pe)
    where po = observed agreement, pe = expected agreement by chance
    Simplified: we treat the report's claims as one rater, and the
    triangulation rule (>=3 sources) as a second rater.
    """
    if total_n == 0:
        return 0.0
    po = (claims_pass + 0) / total_n  # observed agreement (pass = agreement)
    # Expected agreement: marginal probabilities
    p_pass_observed = (claims_pass + 0.5) / total_n  # Laplace smoothing
    pe = p_pass_observed ** 2 + (1 - p_pass_observed) ** 2
    if pe == 1:
        return 1.0
    return (po - pe) / (1 - pe)


def interpret_kappa(kappa: float) -> str:
    """Return human-readable kappa interpretation."""
    for (lo, hi), label in COHEN_KAPPA_INTERPRETATION.items():
        if lo <= kappa <= hi:
            return f"{label} (kappa={kappa:.3f})"
    return f"out of range (kappa={kappa:.3f})"


def cli():
    parser = argparse.ArgumentParser(description="v2.1 Triangulation (>=3 sources + Cohen kappa)")
    parser.add_argument("--report", required=True, type=Path, help="Path to final_turn_XXX.md")
    parser.add_argument("--min-sources", type=int, default=3, help="Min independent sources per claim (default: 3)")
    parser.add_argument("--compute-kappa", action="store_true", help="Compute Cohen kappa")
    args = parser.parse_args()

    if not args.report.exists():
        print(f"ERROR: report not found: {args.report}", file=sys.stderr)
        sys.exit(1)

    report = args.report.read_text(encoding="utf-8")
    claims = extract_claims_with_sources(report)
    print(f"Extracted {len(claims)} claims with sources")

    if not claims:
        print("\nVerdict: NOT EVALUATED (no cited claims were extracted)")
        sys.exit(5)

    result = check_triangulation(claims, min_sources=args.min_sources)
    n_pass = len(result["pass"])
    n_fail = len(result["fail"])
    print(f"\nTriangulation (>= {args.min_sources} independent sources):")
    print(f"  PASS: {n_pass}")
    print(f"  FAIL: {n_fail}")

    if n_fail > 0:
        print(f"\n  FAIL claims:")
        for item in result["fail"]:
            print(f"    - [{item['n_sources']} sources] {item['claim'][:100]}")

    if args.compute_kappa:
        total = n_pass + n_fail
        kappa = compute_cohen_kappa(n_pass, n_fail, total)
        print(f"\n  Cohen kappa (rater=triangulation rule, total={total} claims): {kappa:.3f}")
        print(f"  Interpretation: {interpret_kappa(kappa)}")
        if kappa >= KAPPA_THRESHOLD:
            print(f"  Verdict: PASS (kappa >= {KAPPA_THRESHOLD} substantial agreement)")
            sys.exit(0)
        else:
            print(f"  Verdict: FAIL (kappa < {KAPPA_THRESHOLD}, triangulation not met)")
            sys.exit(3)
    else:
        sys.exit(0 if n_fail == 0 else 4)


if __name__ == "__main__":
    cli()
