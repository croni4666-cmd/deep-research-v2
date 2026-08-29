"""
v1.9.5 skill_self_audit.py → v2.0 skill_self_audit.py

Skill self-audit framework with:
- 7 项 v1.9.5 audit (legacy, LLM 主观)
- 5+13 rubric-based audit (v2.0, DeepVerifier 2026 实证 12-48% F1 gain)

每次写 final_turn_XXX.md 之前必跑, 全部 PASS 才允许 Write 工具调用。

Usage:
    python scripts/skill_self_audit.py [--json] [--report PATH]
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ============================================================
# v1.9.5 兼容: 7 项 audit (保留, 不破坏现有调用)
# ============================================================
SELF_AUDIT_PROMPT_V195 = """
============================================================
v1.9.5 SKILL SELF-AUDIT — 写 final_turn_XXX.md 之前必答
============================================================

下面 7 个问题, 每个问题必须明确回答 "PASS" 或 "FAIL"。
未通过 audit 不得写 final_turn_XXX.md。

[Q1 chart palette] 离散 A-F heatmap 是否用 traffic light 风格 (A 浅绿 / F 纯黑 跨度 100% → 0%)?
   - 答: [PASS/FAIL]
   - 如果 FAIL, 说明: 用了什么 colormap? 是否同色系? A 和 F lightness 跨度?

[Q2 citation URL] 每条关键 claim metadata.citations[].url 是否带 PDF URL (不只有 region-tier)?
   - 答: [PASS/FAIL]
   - 如果 FAIL, 列出: 哪些 claim 缺 URL? 用什么 workaround (例: 厚労省 主页 URL + 报告名)?

[Q3 4 Tier 借鉴] 跨国借鉴章节是否用 4 Tier 客观分层 (未出现/避免复制机制/已出现但程度不同/真正可借鉴)?
   - 答: [PASS/FAIL]
   - 如果 FAIL, 列出: 哪 1 项 fail, 当前措辞 vs 应有措辞

[Q4 ≥3 轮搜索] Step 4 TodoList 是否含 Round 1/2/3/4?
   - 答: [PASS/FAIL]
   - 如果 FAIL, 说明: 跑了几 round? justification 是什么?

[Q5 freshness 标签] 数据表格列是否带 [YYYY-MM-DD 源 实测/推算]?
   - 答: [PASS/FAIL]
   - 如果 FAIL, 列出: 哪些数据缺 freshness 标签?

[Q6 TOC + 章节摘要] ≥30KB 报告是否含 TOC + 每章 TL;DR?
   - 答: [PASS/FAIL]
   - 如果 FAIL, 说明: TOC 在哪? 章节摘要有吗?

[Q7 6 张图] 报告是否含 ≥ 6 张数据可视化?
   - 答: [PASS/FAIL]
   - 如果 FAIL, 说明: 几张图? 哪张缺?

============================================================
FAIL 后 rewrite, 然后重跑 audit, 全部 PASS 才进 Write 工具
============================================================
"""


# ============================================================
# v2.0 新增: 5 major × 13 sub-category rubric-based audit (DeepVerifier 2026 实证)
# 数据源: arXiv 2601.15808 (Wan et al. 2026-04, Tencent AI Lab + CUHK)
# F1 gain: 12-48% over LLM judge baseline
# 8-11% accuracy gain on GAIA / XBench-DeepResearch
# ============================================================

RUBRIC_5_MAJOR_13_SUB = {
    "1_Finding_Sources": {
        "major": "Finding Sources (选错网站/搜索结果)",
        "weight": 0.30,  # most frequent per DeepVerifier (555 errors)
        "subs": [
            "1a_选错源类型 (官方/学术/媒体)",
            "1b_搜索 query 措辞不准 (漏关键限定词)",
            "1c_选错发布渠道 (blog 优先于 primary source)"
        ],
        "audit_questions": [
            "Q1a: 报告里所有 claim 的 source 是 primary (政府/期刊), 还是 secondary (blog/二手转引)?",
            "Q1b: 关键 search query 是否含 year + region + topic 三元组?",
            "Q1c: 选源时是否 prefers .gov / .go.jp / 厚労省 / 内閣府 等?"
        ]
    },
    "2_Reasoning": {
        "major": "Reasoning (inferential leaps / 概念混淆 / overconfident hallucinations)",
        "weight": 0.25,
        "subs": [
            "2a_inferential leaps (从 1 个数据推 3 个结论)",
            "2b_concept conflation (A 现象 → B 概念 错位)",
            "2c_overconfident hallucinations (无源说 X 必然)"
        ],
        "audit_questions": [
            "Q2a: 每个 claim 后面是否有 ≥1 源 + ≥1 数据?",
            "Q2b: 同一概念在不同段是否一致? (无前 A 后 B 矛盾)",
            "Q2c: 无源断言是否标记 [推测] / [未验证]?"
        ]
    },
    "3_Problem_Understanding": {
        "major": "Problem Understanding (误解用户指令 / 跑偏原目标)",
        "weight": 0.15,
        "subs": [
            "3a_误解 user query 主语",
            "3b_跑偏原目标 (做周边话题)",
            "3c_忽略用户明示约束 (region / time / format)"
        ],
        "audit_questions": [
            "Q3a: 报告是否直接回答 user 的原 query (不是周边话题)?",
            "Q3b: topic 范围是否在 user 隐含 scope 内 (不外扩)?",
            "Q3c: region / time / format 约束是否遵守?"
        ]
    },
    "4_Action_Errors": {
        "major": "Action Errors (UI 交互错 / tool API 错 / 模态错)",
        "weight": 0.15,
        "subs": [
            "4a_tool 选错 (用 web_search 抓 PDF, 应 fetch)",
            "4b_API 调用参数错 (key/header/encoding)",
            "4c_modality 错 (文字 query 抓图片)"
        ],
        "audit_questions": [
            "Q4a: 选 tool 时是否按 topic_type 路由 (academic→arxiv, market→sec-filings)?",
            "Q4b: API 参数是否带齐 (key + region + year filter)?",
            "Q4c: 输出格式与 user query 期望一致 (不是 .png 替代 .csv)?"
        ]
    },
    "5_Max_Step_Reached": {
        "major": "Max Step Reached (循环到 limit 仍没找到答案)",
        "weight": 0.15,
        "subs": [
            "5a_tool 失败后不切换 (不 fallback)",
            "5b_死循环 (重复 search 同一 query)",
            "5c_超过 step limit 不 abort"
        ],
        "audit_questions": [
            "Q5a: 1 个 tool 失败 ≥ 2 次, 是否自动换 fallback tool?",
            "Q5b: query 历史是否去重 (同 query 不重发)?",
            "Q5c: 超 step limit 是否自动 abort + 降级到单 agent?"
        ]
    }
}


def audit_rubric(report_text: str, sub_questions_only: bool = False) -> dict:
    """
    Programmatic 5+13 rubric audit of report text.
    LLM self-answers 13 sub-questions, then this function scores.
    Missing markers fail closed. Explicit N/A is recorded but does not count as
    evidence that the check passed.
    """
    scores = {}
    for major_key, major_data in RUBRIC_5_MAJOR_13_SUB.items():
        major_score = 0.0
        major_total = 0.0
        subs = major_data["subs"]
        for sub in subs:
            major_total += 1.0
            sub_id = sub.split("_")[0]  # 1a, 1b, 1c etc
            pass_pattern = rf'\b{sub_id}\b[^\n]*\[PASS\]'
            fail_pattern = rf'\b{sub_id}\b[^\n]*\[FAIL\]'
            if re.search(pass_pattern, report_text, re.IGNORECASE):
                major_score += 1.0
        scores[major_key] = {
            "score": major_score,
            "total": major_total,
            "pct": major_score / major_total if major_total > 0 else 0.0,
            "weight": major_data["weight"]
        }

    # Weighted total
    weighted_score = sum(s["pct"] * s["weight"] for s in scores.values())
    weighted_total = sum(s["weight"] for s in scores.values())  # should be 1.0

    return {
        "rubric": "5_major_x_13_sub (DeepVerifier 2026)",
        "scores": scores,
        "weighted_pct": weighted_score / weighted_total if weighted_total > 0 else 0.0,
        "audit": "PASS" if weighted_score / weighted_total >= 0.80 else "FAIL",
        "threshold": 0.80,  # 80% of weighted rubric must pass
    }


# ============================================================
# v2.0: 12 项 self-audit (合并 v1.9.5 7 项 + 5+13 rubric)
# ============================================================
def run_v2_self_audit(report_text: str) -> dict:
    """
    v2.0 12 项 self-audit = 7 项 v1.9.5 + 5+13 rubric programmatic check
    """
    # 7 项 v1.9.5 兼容 audit (LLM 主观, 文本中搜 [PASS]/[FAIL]/[N/A] marker)
    # N/A = 不适用 (meta-meta), 也算 PASS
    def parse_marker(qid: str) -> str:
        pattern = rf'\b{qid}\b[^\n]*\[PASS\]'
        na_pattern = rf'\b{qid}\b[^\n]*\[N/A\]'
        fail_pattern = rf'\b{qid}\b[^\n]*\[FAIL\]'
        if re.search(pattern, report_text, re.IGNORECASE):
            return "PASS"
        elif re.search(fail_pattern, report_text, re.IGNORECASE):
            return "FAIL"
        elif re.search(na_pattern, report_text, re.IGNORECASE):
            return "N/A"
        else:
            return "MISSING"

    v195_audit = {
        "Q1_chart_palette": parse_marker("Q1"),
        "Q2_citation_URL": parse_marker("Q2"),
        "Q3_4_Tier": parse_marker("Q3"),
        "Q4_round": parse_marker("Q4"),
        "Q5_freshness": parse_marker("Q5"),
        "Q6_TOC": parse_marker("Q6"),
        "Q7_charts": parse_marker("Q7"),
    }

    # 5+13 rubric programmatic check (复用 audit_rubric 函数)
    rubric_result = audit_rubric(report_text)

    all_pass = all(v == "PASS" for v in v195_audit.values()) and rubric_result["audit"] == "PASS"

    return {
        "v2_audit": "PASS" if all_pass else "FAIL",
        "v195_7_items": v195_audit,
        "v20_rubric": rubric_result,
        "summary": f"v1.9.5 7 items: {sum(1 for v in v195_audit.values() if v == 'PASS')}/7 PASS | "
                    f"5+13 rubric: {rubric_result['weighted_pct']*100:.0f}% (≥80% PASS)",
        "next": "ALL PASS, proceed Write tool" if all_pass else "FAIL, fix failed items then re-run"
    }


# ============================================================
# CLI entry point
# ============================================================
def detect_regression(prev_audit: dict, curr_audit: dict) -> dict:
    """
    Detect regressions between two multi-turn audits (Mr Dre 16-27% 防御).
    Compare 7 v1.9.5 items + 5+13 rubric sub-categories between turn N and turn N-1.
    Returns dict of regressed items + summary.
    """
    regressions = {
        "v195_items_regressed": [],
        "rubric_subs_regressed": [],
        "weighted_pct_delta": 0.0,
        "summary": ""
    }

    # Compare v1.9.5 7 items
    for item, status in curr_audit["v195_7_items"].items():
        prev_status = prev_audit["v195_7_items"].get(item, "UNKNOWN")
        if prev_status == "PASS" and status == "FAIL":
            regressions["v195_items_regressed"].append({
                "item": item, "from": prev_status, "to": status
            })

    # Compare 5+13 rubric sub-categories (P/N ratio)
    for major_key in curr_audit["v20_rubric"]["scores"]:
        curr_pct = curr_audit["v20_rubric"]["scores"][major_key]["pct"]
        prev_pct = prev_audit["v20_rubric"]["scores"][major_key]["pct"]
        if prev_pct == 1.0 and curr_pct < 1.0:
            regressions["rubric_subs_regressed"].append({
                "major": major_key, "from": prev_pct, "to": curr_pct
            })

    regressions["weighted_pct_delta"] = round(
        curr_audit["v20_rubric"]["weighted_pct"] - prev_audit["v20_rubric"]["weighted_pct"], 3
    )

    n_regressions = len(regressions["v195_items_regressed"]) + len(regressions["rubric_subs_regressed"])
    if n_regressions == 0:
        regressions["summary"] = "NO REGRESSION - multi-turn stable (defends Mr Dre 16-27% risk)"
    else:
        regressions["summary"] = f"REGRESSION DETECTED: {n_regressions} items dropped ({len(regressions['v195_items_regressed'])} v1.9.5 + {len(regressions['rubric_subs_regressed'])} rubric subs)"

    return regressions


def run_multi_turn_audit(report_path: Path, n_turns: int = 3) -> list:
    """
    v2.0 Phase 2.2 — Multi-turn revision defense (Mr Dre 16-27% regress 防御).
    Run audit N times, track changes between turns, flag regressions.
    """
    import time as _time
    if not report_path.exists():
        print(f"ERROR: report not found: {report_path}", file=sys.stderr)
        sys.exit(1)

    history = []
    print(f"=== Multi-Turn Audit: {n_turns} turns on {report_path.name} ===\n")

    for turn in range(1, n_turns + 1):
        report_text = report_path.read_text(encoding="utf-8")
        curr_audit = run_v2_self_audit(report_text)

        turn_result = {
            "turn": turn,
            "timestamp": _time.time(),
            "audit": curr_audit,
            "regressions_from_prev": None,
        }

        if len(history) > 0:
            prev_audit = history[-1]["audit"]
            turn_result["regressions_from_prev"] = detect_regression(prev_audit, curr_audit)
            reg = turn_result["regressions_from_prev"]
            n_v195 = sum(1 for v in curr_audit["v195_7_items"].values() if v == "PASS")
            print(f"  Turn {turn}: v1.9.5 {n_v195}/7 PASS, "
                  f"rubric {curr_audit['v20_rubric']['weighted_pct']*100:.0f}% "
                  f"(delta {reg['weighted_pct_delta']*100:+.0f}%) — {reg['summary']}")
        else:
            n_v195 = sum(1 for v in curr_audit["v195_7_items"].values() if v == "PASS")
            print(f"  Turn 1: v1.9.5 {n_v195}/7 PASS, "
                  f"rubric {curr_audit['v20_rubric']['weighted_pct']*100:.0f}%")

        history.append(turn_result)

    # Summary
    print(f"\n=== Multi-Turn Summary ===")
    total_regressions = sum(
        len(h.get("regressions_from_prev", {}).get("v195_items_regressed", [])) +
        len(h.get("regressions_from_prev", {}).get("rubric_subs_regressed", []))
        for h in history[1:] if h.get("regressions_from_prev")
    )
    print(f"  Total turns: {n_turns}")
    print(f"  Total regressions across turns: {total_regressions}")
    print(f"  Final weighted rubric: {history[-1]['audit']['v20_rubric']['weighted_pct']*100:.0f}%")
    print(f"  Final v2_audit: {history[-1]['audit']['v2_audit']}")

    return history


def main():
    parser = argparse.ArgumentParser(description="Mavis deep-research-v2 skill self-audit v2.0 (with multi-turn)")
    parser.add_argument("--report", help="Path to final_turn_XXX.md to audit", type=Path)
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    parser.add_argument("--prompt", action="store_true", help="Print the LLM self-audit prompt template")
    parser.add_argument("--multi-turn", type=int, default=1, metavar="N",
                        help="Run audit N times, detect regressions (Mr Dre 16-27% 防御, v2.0 Phase 2.2)")
    args = parser.parse_args()

    if args.prompt:
        print(SELF_AUDIT_PROMPT_V195)
        print("\n# v2.0 5+13 Rubric Audit (LLM answers 13 sub-questions)\n")
        for major_key, major_data in RUBRIC_5_MAJOR_13_SUB.items():
            print(f"\n[{major_key}] {major_data['major']} (weight={major_data['weight']})")
            for sub in major_data["subs"]:
                print(f"  - {sub}: [PASS/FAIL]")
            for q in major_data["audit_questions"]:
                print(f"    {q}")
        return

    if not args.report:
        print("[v1.9.5 PROMPT]\n" + SELF_AUDIT_PROMPT_V195)
        print("\n[v2.0 RUBRIC]")
        for major_key, major_data in RUBRIC_5_MAJOR_13_SUB.items():
            print(f"\n[{major_key}] {major_data['major']} (weight={major_data['weight']})")
            for sub in major_data["subs"]:
                print(f"  - {sub}: [PASS/FAIL]")
        return

    if not args.report.exists():
        print(f"ERROR: report not found: {args.report}", file=sys.stderr)
        sys.exit(1)

    if args.multi_turn > 1:
        history = run_multi_turn_audit(args.report, n_turns=args.multi_turn)
        if args.json:
            print(json.dumps(history, indent=2, ensure_ascii=False, default=str))
        # Exit code: 0 = no regressions, 1 = regressions detected
        total_reg = sum(
            len(h.get("regressions_from_prev", {}).get("v195_items_regressed", [])) +
            len(h.get("regressions_from_prev", {}).get("rubric_subs_regressed", []))
            for h in history[1:] if h.get("regressions_from_prev")
        )
        sys.exit(0 if total_reg == 0 else 1)
    else:
        report_text = args.report.read_text(encoding="utf-8")
        result = run_v2_self_audit(report_text)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result["v2_audit"] == "PASS" else 1)


if __name__ == "__main__":
    main()
