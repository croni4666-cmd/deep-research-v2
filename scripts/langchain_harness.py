"""
v2.0 LangChain Deep Agents harness (lightweight local implementation)
============================================================================
Source: benjaminhan.net/posts/20260529-langchain-deep-agents (2026-05)
       + blog.langchain.com/deep-agents (2026-07)
       + hype08.github.io/gradual-notes/thoughts/Open-Deep-Research (2026-05)

Why: v1.9.3 multi-agent 协议只有 supervisor + sub-agents, 缺 LangChain Deep Agents
     7 步 pattern (Plan / Save / Delegate / Search / Synthesize / Write / Verify)
     + virtual filesystem (virtual FS). v0.7 (2026) 减 65% input tokens + 跑通
     production Apollo / Moda / Stripe Kai 部署。

Usage:
    python scripts/langchain_harness.py --mode research --topic "..." --dry-run
    python scripts/langchain_harness.py --mode analyze --files a.md b.md
    python scripts/langchain_harness.py --mode build --content-type slides

7 步 Plan / Execute / Synthesize pattern:
  1. Plan       - write_todos (built-in)
  2. Save       - virtual FS /research_request.md (built-in)
  3. Delegate   - sub-agents in isolated context (task tool)
  4. Search     - per sub-agent, your search tool (we pass web_search)
  5. Synthesize - compress + dedupe, supervisor gets signal not noise
  6. Write      - Final Report Model, one-shot, single context
  7. Verify     - re-read /research_request.md, confirm coverage

This is a planning preview only. It does not call an agent runtime, execute
generated code, search the web, or verify a report.
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ============================================================
# 7-step Plan / Execute / Synthesize pattern
# ============================================================

@dataclass
class ResearchRequest:
    """virtual FS /research_request.md 状态"""
    topic: str
    region: str = "Global"
    topic_type: str = "general"  # general / academic / market / code
    depth: int = 3  # 1-5, supervisor 控制 sub-agent 递归深度
    created_at: float = field(default_factory=time.time)
    todos: list = field(default_factory=list)
    sub_findings: list = field(default_factory=list)  # supervisor 压缩
    final_report: str = ""


def plan(request: ResearchRequest) -> list:
    """Step 1: Plan - 写 todos 列表 (v1.9.3 Step 3 DAG 派生)"""
    request.todos = [
        f"Define the decision, scope, and terms for: {request.topic}",
        f"Identify authoritative primary sources relevant to {request.region}",
        "Inspect source methodology, dates, population, and limitations",
        "Cross-check consequential claims with independent evidence",
        "Document conflicts, unresolved questions, and stopping conditions",
        "Synthesize a cited answer without treating heuristic scores as evidence",
    ]
    return request.todos


def save_to_virtual_fs(request: ResearchRequest, vfs_path: Path) -> None:
    """Step 2: Save - 写 /research_request.md (v1.9.3 virtual filesystem)"""
    vfs_path.write_text(
        f"# Research Request\n\n"
        f"**Topic**: {request.topic}\n"
        f"**Region**: {request.region}\n"
        f"**Topic Type**: {request.topic_type}\n"
        f"**Depth**: {request.depth}\n"
        f"**Created**: {time.ctime(request.created_at)}\n\n"
        f"## Todos ({len(request.todos)})\n" +
        "\n".join(f"- [ ] {t}" for t in request.todos) + "\n\n"
        f"## Sub-findings ({len(request.sub_findings)})\n\n"
        f"## Final Report\n\n"
        f"{request.final_report}\n",
        encoding="utf-8"
    )


def delegate_to_subagents(request: ResearchRequest, code_acting: bool = False) -> list:
    """Step 3: Delegate - N sub-agents in isolated context (Mavis task tool)

    v2.0 Phase 2.3: code-acting mode (smolagents 22-point GAIA gap)
    - code_acting=False (default): v1.9.3 JSON tool call style
    - code_acting=True: v2.0 Python snippet style (smolagents CodeAgent)
    """
    n_subagents = max(2, min(request.depth, 5))
    subagent_prompts = []

    if code_acting:
        # v2.0 code-acting: Python snippet style (smolagents 22-point GAIA gap fix)
        base_prompt = f"""你是一个 deep-research sub-agent (v2.0 code-acting 模式, smolagents CodeAgent 风格)。

研究主题: {request.topic}
地区: {request.region}
topic_type: {request.topic_type}

任务: 写 Python 代码片段完成研究, 不要用 JSON tool call。

可用工具 (作为 Python 函数):
- web_search(query: str) -> list[dict]: 返回 {{url, title, snippet}} 列表
- web_fetch(url: str) -> str: 返回页面 markdown
- web_extract(text: str, schema: dict) -> dict: 提取结构化数据

要求:
1. 必填 metadata.citations[].url 字段
2. 必填 freshness 标签 [YYYY-MM-DD 源 实測/推算]
3. 用 Python loop + branch 表达多步 action, 1 个代码块完成全流程
4. 返回 dict 含 sources / key_facts / judgment, 写在 return 语句

模板:
```python
import re

def research_subagent():
    sources = []
    key_facts = []

    # Step 1: 搜索
    results = web_search("{{request.topic}} 2024")
    for r in results[:3]:
        sources.append({{
            "url": r["url"],
            "title": r["title"],
            "tier": "T1-{{request.region}} 本地",
            "freshness": "2024 实測"
        }})
        # Step 2: 读 page + 抽 facts
        text = web_fetch(r["url"])
        for fact in re.findall(r"\\d+ \\w+", text)[:5]:
            key_facts.append({{"value": fact, "source": r["url"]}})

    return {{
        "sources": sources,
        "key_facts": key_facts,
        "judgment": "本角度: 找到 {{len(sources)}} 个 {{request.topic}} 权威源"
    }}

# Run
result = research_subagent()
```
"""
    else:
        # v1.9.3 JSON tool call style (默认, 向后兼容)
        base_prompt = """你是一个 deep-research sub-agent (v1.9.3 multi-agent 协议)。
研究主题: {topic}
地区: {region}
topic_type: {topic_type}

任务:
1. 用 web_search 找 3-5 个权威源
2. 优选 T1-{region} 本地源 + T2-英文 国际源
3. 必填 metadata.citations[].url 字段
4. 必填 freshness 标签 [YYYY-MM-DD 源 实測/推算]
5. 输出 JSON, 不写报告
"""

    for i in range(n_subagents):
        angle = ["核心数据", "政策史", "国际对比", "未来预测", "争议焦点"][i % 5]
        if code_acting:
            prompt = base_prompt.format(
                topic=request.topic, region=request.region, topic_type=request.topic_type
            ) + f"\n本次子代理焦点: {angle} (sub-agent #{i+1}/{n_subagents})"
        else:
            prompt = base_prompt.format(
                topic=request.topic, region=request.region, topic_type=request.topic_type
            ) + f"\n本次子代理焦点: {angle} (sub-agent #{i+1}/{n_subagents})"
        subagent_prompts.append(prompt)

    return subagent_prompts


def search_per_subagent(prompt: str, code_acting: bool = False) -> dict:
    """Step 4: Search - 每个 sub-agent 跑搜索

    v2.0 Phase 2.3: code_acting=True 时, sub-agent 写 Python snippet 表达多步 action
    (smolagents CodeAgent 风格, +22-point GAIA, 减少 30% LLM calls vs JSON)
    """
    # This harness does not have access to an agent runtime or search tools.
    # Return an explicit non-result instead of fabricating a successful search.
    return {
        "sub_agent_id": hash(prompt) % 10000,
        "status": "not_evaluated",
        "sources": [],
        "key_facts": [],
        "judgment": "",
        "code_acting": code_acting,
        "reason": "planning harness only; no agent or search tool was invoked",
    }


def synthesize(request: ResearchRequest) -> None:
    """Step 5: Synthesize - 压缩 + dedupe (sub-agent 输出 → supervisor 整合)"""
    # 真实版: LLM 读 N sub-agent 输出, 压缩 50%, 去重, 提核心
    # 这里: 主 agent 收集 sub_findings, 准备写 final
    request.sub_findings = [
        f"sub-agent #{i+1}: {len(s.get('key_facts', []))} facts, {len(s.get('sources', []))} sources"
        for i, s in enumerate(request.sub_findings)
    ]


def write_final_report(request: ResearchRequest) -> str:
    """Step 6: Write - Final Report Model, one-shot (single context, NOT multi-agent)"""
    # 真实版: 1 个 LLM call, 用 research_brief + sub_findings 一次性写完整报告
    # 这里: stub, 等价于 'final_turn_001.md'
    return f"# Final Report: {request.topic}\n\n" + \
           f"## 0. TL;DR (50 字)\n[Step 5 synthesize 输出]\n\n" + \
           f"## 1. Background (200 字)\n[sub-agent findings]\n\n" + \
           f"## 2. Methodology (150 字)\n[research_brief + sub_findings 整合]\n\n" + \
           f"## 3. Data (300 字)\n[5+13 rubric 验证后]\n\n" + \
           f"## 4. Discussion (300 字)\n[3 sub_findings 整合]\n\n" + \
           f"## 5. Conclusion (200 字)\n[judgment + 4 Tier 借鉴 (if applicable)]\n\n" + \
           f"## 6. References (n sources)\n[All sources with url + freshness]"


def verify_coverage(request: ResearchRequest, vfs_path: Path) -> bool:
    """Step 7: Verify - re-read /research_request.md, confirm coverage"""
    if not vfs_path.exists():
        return False
    content = vfs_path.read_text(encoding="utf-8")
    # Fail closed: headings, placeholders, or empty stub results are not evidence.
    todos_count = content.count("- [ ]") + content.count("- [x]")
    valid_findings = [
        finding for finding in request.sub_findings
        if isinstance(finding, dict)
        and finding.get("status") == "completed"
        and finding.get("sources")
        and finding.get("key_facts")
    ]
    has_report = len(request.final_report) >= 100
    return todos_count >= 5 and len(valid_findings) > 0 and has_report


# ============================================================
# CLI entry point
# ============================================================
def run_research_mode(args):
    """Research 模式: Plan → Execute (delegate + search) → Write → Verify"""
    request = ResearchRequest(
        topic=args.topic,
        region=args.region,
        topic_type=args.topic_type,
        depth=args.depth,
    )

    if not args.dry_run:
        print(
            "ERROR: this harness is planning-only. Re-run with --dry-run, or "
            "use the deep-research skill workflow with real search tools.",
            file=sys.stderr,
        )
        return 2

    if args.code_acting:
        print(
            "ERROR: --code-acting is disabled because this package does not "
            "provide an isolated code-execution runtime.",
            file=sys.stderr,
        )
        return 2

    # Step 1: Plan
    print(f"[Step 1] Plan: {len(plan(request))} todos")
    for t in request.todos:
        print(f"  - {t}")

    # Step 2: Save to virtual FS
    vfs_path = Path(args.vfs_path)
    save_to_virtual_fs(request, vfs_path)
    print(f"[Step 2] Save: {vfs_path}")

    # Step 3: Delegate to sub-agents (v2.0 Phase 2.3: --code-acting 启用 Python snippet style)
    subagent_prompts = delegate_to_subagents(request, code_acting=args.code_acting)
    mode_str = "code-acting (Python snippet)" if args.code_acting else "JSON tool call (v1.9.3 default)"
    print(f"[Step 3] Delegate: {len(subagent_prompts)} sub-agents, mode: {mode_str}")

    print("[Step 4] DRY RUN: no agents or search tools invoked")
    summary = {
        "status": "dry_run",
        "topic": request.topic,
        "region": request.region,
        "topic_type": request.topic_type,
        "n_planned_subagents": len(subagent_prompts),
        "todos_count": len(request.todos),
        "verified": False,
        "vfs_path": str(vfs_path),
    }
    print("\n=== Summary ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0

    # Step 5: Synthesize
    synthesize(request)
    print(f"[Step 5] Synthesize: {len(request.sub_findings)} sub-findings compressed")

    # Step 6: Write final report
    request.final_report = write_final_report(request)
    save_to_virtual_fs(request, vfs_path)  # re-save with final report
    print(f"[Step 6] Write: {len(request.final_report)} chars")

    # Step 7: Verify
    passed = verify_coverage(request, vfs_path)
    print(f"[Step 7] Verify: {'PASS' if passed else 'FAIL'}")

    # Output summary
    summary = {
        "topic": request.topic,
        "region": request.region,
        "topic_type": request.topic_type,
        "code_acting": args.code_acting,
        "n_subagents": len(subagent_prompts),
        "todos_count": len(request.todos),
        "sub_findings_count": len(request.sub_findings),
        "final_report_chars": len(request.final_report),
        "vfs_path": str(vfs_path),
        "verify": passed,
    }
    print("\n=== Summary ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(
        description="v2.0 LangChain Deep Agents harness (lightweight local)"
    )
    parser.add_argument("--mode", choices=["research", "analyze", "build"],
                        default="research",
                        help="Deep Agents mode: research / analyze / build")
    parser.add_argument("--topic", help="Research topic (required for research mode)")
    parser.add_argument("--region", default="Global",
                        help="Region (Global / CN / JP / etc.)")
    parser.add_argument("--topic-type", default="general",
                        choices=["general", "academic", "market", "code"],
                        help="topic_type for region routing (v1.8 region-aware)")
    parser.add_argument("--depth", type=int, default=3,
                        help="Supervisor depth (1-5 sub-agents)")
    parser.add_argument("--vfs-path", default="./research_request.md",
                        help="Virtual filesystem path (analog of LangChain /research_request.md)")
    parser.add_argument("--code-acting", action="store_true",
                        help="Disabled: requires a real isolated execution runtime")
    parser.add_argument("--files", nargs="*",
                        help="Files for analyze mode")
    parser.add_argument("--content-type", default="report",
                        help="Content type for build mode (report / slides / etc.)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview the plan; required because this harness does not execute research")
    args = parser.parse_args()

    if args.mode == "research":
        if not args.topic:
            print("ERROR: --topic required for research mode", file=sys.stderr)
            sys.exit(1)
        return run_research_mode(args)
    elif args.mode == "analyze":
        print(f"[analyze] would process {len(args.files or [])} files: {args.files}")
        print("  stub: implement per LangChain Deep Agents data analysis pattern")
        return 0
    elif args.mode == "build":
        print(f"[build] would generate {args.content_type}")
        print("  stub: implement per LangChain Deep Agents content builder pattern")
        return 0


if __name__ == "__main__":
    sys.exit(main())
