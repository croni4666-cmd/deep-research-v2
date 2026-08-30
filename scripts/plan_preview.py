"""Create a bounded research-plan preview without performing research."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResearchPlan:
    topic: str
    region: str
    depth: int
    questions: list[str]
    stopping_conditions: list[str]
    status: str = "plan_only"
    verified: bool = False


def build_plan(topic: str, region: str = "Global", depth: int = 3) -> ResearchPlan:
    if not topic.strip():
        raise ValueError("topic must not be empty")
    if not 1 <= depth <= 5:
        raise ValueError("depth must be between 1 and 5")
    questions = [
        f"What decision, definitions, and exclusions bound {topic}?",
        f"Which primary sources are authoritative for {region}?",
        "What do the strongest sources establish, and with what limitations?",
        "Which key claims have independent underlying evidence?",
        "Where do credible sources conflict, and why?",
        "What conclusion is supported, and what remains unresolved?",
    ]
    if depth <= 2:
        questions = [questions[0], questions[1], questions[2], questions[-1]]
    elif depth == 5:
        questions.insert(4, "What plausible counter-explanations survive the evidence?")
    return ResearchPlan(
        topic=topic.strip(),
        region=region.strip() or "Global",
        depth=depth,
        questions=questions,
        stopping_conditions=[
            "Additional searching is duplicative or unlikely to change the conclusion.",
            "Every question is resolved, qualified, unresolved, or excluded with a reason.",
            "Further progress requires unavailable credentials, paid access, or new authority.",
        ],
    )


def render_markdown(plan: ResearchPlan) -> str:
    question_lines = "\n".join(
        f"{index}. {question}" for index, question in enumerate(plan.questions, 1)
    )
    stop_lines = "\n".join(f"- {item}" for item in plan.stopping_conditions)
    return (
        f"# Research plan: {plan.topic}\n\n"
        f"- Region: {plan.region}\n"
        f"- Depth: {plan.depth}\n"
        f"- Status: plan only; no research performed\n\n"
        f"## Research questions\n\n{question_lines}\n\n"
        f"## Stopping conditions\n\n{stop_lines}\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview a research plan; this tool does not search or verify."
    )
    parser.add_argument("--topic", required=True)
    parser.add_argument("--region", default="Global")
    parser.add_argument("--depth", type=int, choices=range(1, 6), default=3)
    parser.add_argument("--out", type=Path, help="Optional output path")
    parser.add_argument("--force", action="store_true", help="Allow replacing --out")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args(argv)

    try:
        plan = build_plan(args.topic, args.region, args.depth)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    rendered = (
        json.dumps(asdict(plan), indent=2, ensure_ascii=False) + "\n"
        if args.json else render_markdown(plan)
    )
    if args.out:
        if args.out.exists() and not args.force:
            print(
                f"ERROR: output already exists: {args.out}; use --force to replace it",
                file=sys.stderr,
            )
            return 2
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
        print(f"Saved plan preview to: {args.out}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
