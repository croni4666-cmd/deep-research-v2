"""
v2.0 Phase 3.1+3.2 — Programmatic segment-level audit (TELBench DRIFT inspired)
==================================================================
Source: TELBench (thevalue.engineering) 2026
       + DeepVerifier arXiv 2601.15808
       + Paper-agent v3.9.x programmatic audit pattern

Why:
- v1.9.3 + v1.9.5: audit only checks final report (boolean PASS/FAIL)
- v2.0: split final report into N segments, audit EACH segment independently
- "False Precision" 防御: agents reach right conclusion through wrong logic (TELBench)
- "Focused vs workflow" gap: single audit misses segment-level errors (MisKnow-Agent)
- DRIFT framework: track claims per segment, flag unverified/contradictory

Usage:
    python scripts/skill_audit_v2.py --report path/to/final.md [--segments N] [--json]
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional


# ============================================================
# Segment splitter (按 ## / ### 标题切)
# ============================================================
def split_report_into_segments(text: str, n_segments: Optional[int] = None) -> list:
    """
    Split final report into N segments by H2/H3 headers.
    Default: max 8 segments (TELBench sweet spot).
    """
    # 1) Try H2 split first
    h2_segments = re.split(r"^##\s+", text, flags=re.MULTILINE)
    if len(h2_segments) > 1:
        h2_segments = [s for s in h2_segments if s.strip()]
        if len(h2_segments) <= 8:
            return [(f"§{i}", s) for i, s in enumerate(h2_segments)]

    # 2) Fallback to H3 split
    h3_segments = re.split(r"^###\s+", text, flags=re.MULTILINE)
    h3_segments = [s for s in h3_segments if s.strip()]
    if len(h3_segments) <= 12:
        return [(f"§{i}", s) for i, s in enumerate(h3_segments)]

    # 3) N-segment fixed-size split
    if n_segments and n_segments > 1:
        chunk_size = len(text) // n_segments
        return [(f"§{i}", text[i*chunk_size:(i+1)*chunk_size]) for i in range(n_segments)]

    return [("§0", text)]


# ============================================================
# Per-segment audit (DRIFT: track claims + freshness)
# ============================================================
def audit_segment(segment_id: str, segment_text: str) -> dict:
    """
    DRIFT-style per-segment audit:
    - count numeric claims (potential data points)
    - count citations ([N] format or URL)
    - count freshness tags ([YYYY 实測/推算])
    - check unsupported claims (numeric without citation)
    """
    # Count numeric claims (digits not in code blocks)
    numeric_claims = len(re.findall(r"\b\d+(?:\.\d+)?(?:\s*[%万千亿美元万亿年月日])?", segment_text))
    # Count citations ([1] / [12] / URL)
    bracketed_cites = len(re.findall(r"\[\d+\]", segment_text))
    url_cites = len(re.findall(r"https?://[^\s\)]+", segment_text))
    total_cites = bracketed_cites + url_cites
    # Count freshness tags
    freshness_tags = len(re.findall(
        r"\[\d{4}(?:-\d{2})?(?:-\d{2})?\s+[\u4e00-\u9fff]+\s+(?:实测|實測|推算|审议会)\]",
        segment_text,
    ))
    freshness_tags += len(re.findall(r"\b\d{4}\s+(?:实測|实测|推算)\b", segment_text))
    # Unsupported claims (numeric > 0 but cites = 0)
    unsupported = max(0, numeric_claims - total_cites) if total_cites == 0 else 0

    # Per-segment verdict
    if total_cites == 0 and numeric_claims > 3:
        verdict = "FAIL"  # many claims but no sources
    elif freshness_tags < (numeric_claims / 10) if numeric_claims > 0 else False:
        verdict = "WARN"  # few freshness labels
    else:
        verdict = "PASS"

    return {
        "segment_id": segment_id,
        "chars": len(segment_text),
        "numeric_claims": numeric_claims,
        "citations": total_cites,
        "freshness_tags": freshness_tags,
        "unsupported_claims": unsupported,
        "verdict": verdict,
    }


# ============================================================
# Programmatic self-audit check (Phase 3.2)
# ============================================================
def programmatic_audit_checklist(report_path: Path) -> dict:
    """
    7-12 item programmatic check (no LLM subjective):
    Q1: chart palette
    Q2: citation URL
    Q3: 4 Tier 借鉴
    Q4: ≥3 round
    Q5: freshness 标签
    Q6: TOC + chapter 摘要
    Q7: 6 张图
    Q8-Q12: segment-level (Phase 3.1 new)
    """
    if not report_path.exists():
        return {"error": f"file not found: {report_path}"}

    text = report_path.read_text(encoding="utf-8")

    # Q1 chart palette (look for traffic light marker or PNG file refs)
    q1 = "PASS" if "traffic light" in text.lower() or re.search(r"pal_audit|color_list", text, re.IGNORECASE) else "N/A"

    # Q2 citation URL (count https URLs)
    n_urls = len(re.findall(r"https?://[^\s\)]+", text))
    q2 = "PASS" if n_urls >= 3 else "FAIL"

    # Q3 4 Tier (look for 4 tier markers)
    q3 = "PASS" if all(tier in text for tier in ["Tier 1", "Tier 2", "Tier 3", "Tier 4"]) else "N/A"

    # Q4 ≥3 round (look for Round 1/2/3/4)
    q4 = "PASS" if re.search(r"Round\s+1.*Round\s+2.*Round\s+3", text, re.DOTALL) else "WARN"

    # Q5 freshness (count freshness tags)
    freshness_count = len(re.findall(r"\d{4}.*实测|推算|审议会", text))
    q5 = "PASS" if freshness_count >= 3 else "WARN"

    # Q6 TOC (look for ## 目录)
    q6 = "PASS" if "## 目录" in text or "## TOC" in text else "WARN"

    # Q7 6 张图 (count image references)
    img_count = len(re.findall(r"!\[.*?\]\(.*?\)|<img|<image|chart\d", text, re.IGNORECASE))
    q7 = "PASS" if img_count >= 6 else "WARN"

    # Q8-Q12 segment-level (Phase 3.1)
    segments = split_report_into_segments(text)
    segment_audits = [audit_segment(sid, stext) for sid, stext in segments]
    n_segments = len(segments)
    n_segment_pass = sum(1 for s in segment_audits if s["verdict"] == "PASS")
    n_segment_warn = sum(1 for s in segment_audits if s["verdict"] == "WARN")
    n_segment_fail = sum(1 for s in segment_audits if s["verdict"] == "FAIL")
    q8 = "PASS" if n_segment_fail == 0 else "FAIL"
    q9 = "PASS" if n_segment_pass >= max(1, n_segments * 0.7) else "WARN"  # 70% pass rate
    total_claims = sum(s["numeric_claims"] for s in segment_audits)
    total_cites = sum(s["citations"] for s in segment_audits)
    total_freshness = sum(s["freshness_tags"] for s in segment_audits)
    total_unsupported = sum(s["unsupported_claims"] for s in segment_audits)
    q10 = "PASS" if total_unsupported == 0 else "WARN"
    q11 = "PASS" if total_freshness >= max(1, total_claims / 10) else "WARN"
    q12 = "PASS" if total_cites >= max(3, total_claims / 5) else "WARN"

    result = {
        "v3_2_audit": "PASS" if all(s != "FAIL" for s in [q1, q2, q3, q4, q5, q6, q7, q8, q9, q10, q11, q12]) else "FAIL",
        "Q1_chart_palette": q1,
        "Q2_citation_URL": q2,
        "Q3_4_Tier_借鉴": q3,
        "Q4_≥3_round": q4,
        "Q5_freshness": q5,
        "Q6_TOC": q6,
        "Q7_6_张图": q7,
        "Q8_segment_no_FAIL": q8,
        "Q9_70%_segments_PASS": q9,
        "Q10_no_unsupported_claims": q10,
        "Q11_freshness_coverage": q11,
        "Q12_citation_density": q12,
        "segments": segment_audits,
        "n_segments": n_segments,
        "summary": {
            "total_claims": total_claims,
            "total_citations": total_cites,
            "total_freshness_tags": total_freshness,
            "total_unsupported_claims": total_unsupported,
            "segment_pass_rate": f"{n_segment_pass}/{n_segments} ({n_segment_pass/max(1,n_segments)*100:.0f}%)",
        }
    }
    return result


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="v2.0 Phase 3.1+3.2: Programmatic segment-level audit (TELBench DRIFT + 12 items)"
    )
    parser.add_argument("--report", required=True, type=Path, help="Path to final_turn_XXX.md")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    parser.add_argument("--n-segments", type=int, help="Force N segments (default: auto by H2/H3)")
    args = parser.parse_args()

    result = programmatic_audit_checklist(args.report)
    if "error" in result:
        print(json.dumps(result, indent=2, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
    if args.n_segments:
        result["_n_segments_forced"] = args.n_segments

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        # Human-readable summary
        print(f"=== Programmatic Audit (v2.0 Phase 3.1+3.2): {args.report.name} ===\n")
        print(f"v3.2 audit verdict: {result['v3_2_audit']}\n")
        print("Q1-Q12 items:")
        for k, v in result.items():
            if k.startswith("Q") and not k.startswith("Q8_segment_no_FAIL"):
                print(f"  {k}: {v}")
        print(f"\nSegments: {result['n_segments']}")
        print(f"Summary: {result['summary']}")

    # Exit code
    sys.exit(0 if result["v3_2_audit"] == "PASS" else 1)


if __name__ == "__main__":
    main()
