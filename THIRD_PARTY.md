# Third-Party Acknowledgments

`deep-research-v2` skill v2.0+ integrates with or is inspired by the following third-party projects. Their licenses and contributions are gratefully acknowledged.

## LLM Providers (via Mavis runtime)
- **Anthropic Claude** (Opus 4, Sonnet 4): Multi-agent research architecture inspiration (2026-01)
- **OpenAI** (o3, GPT-5 series): DeepResearch Bench score reference (2025-2026)
- **Google Gemini** (3.1 Pro + Deep Research Max): GAIA / DeepSearchQA benchmark reference (2026-04)
- **HuggingFace** (smolagents): CodeAgent code-as-action pattern, 30% fewer steps (2026-05)

## Skill Frameworks (referenced / borrowed patterns)

| Project | URL | License | What we borrowed |
|---|---|---|---|
| `langchain-ai/open_deep_research` | github.com/langchain-ai/open_deep_research | MIT | 3-phase (Scope/Research/Write) pattern, RACE 0.4943 |
| `huggingface/smolagents` | github.com/huggingface/smolagents | Apache-2.0 | CodeAgent pattern, code-as-action prompt template |
| `assafelovic/gpt-researcher` | github.com/assafelovic/gpt-researcher | Apache-2.0 | "just run it" UX inspiration |
| `paper-agent` (croni4666-cmd) | github.com/croni4666-cmd/paper-agent | AGPL-3.0 + No-AI-Training-1.0 | License pattern, 10-round security audit template |
| `Ayanami0730/deep_research_bench` | github.com/Ayanami0730/deep_research_bench | (open) | RACE + FACT evaluation framework reference |

## Academic Research (foundational papers)

| Paper | URL | What we referenced |
|---|---|---|
| DeepVerifier (arXiv 2601.15808) | arxiv.org/abs/2601.15808 | 5+13 DRA Failure Taxonomy + verifier pattern |
| Mr Dre (arXiv 2601.13217) | aclanthology.org/2026.acl-long.609/ | Multi-turn revision regression (16-27%) defense |
| TELBench / DRIFT (arXiv 2606.02060) | arxiv.org/abs/2606.02060 | Segment-level audit pattern |
| MisKnow-Agent (arXiv 2607.20891) | arxiv.org/abs/2607.20891 | Misleading knowledge prevention (FCAR 34%→85%) |
| Reflexion (arXiv 2303.11366) | arxiv.org/abs/2303.11366 | Verbal self-reflection pattern |
| DSPy (arXiv 2310.03714) | arxiv.org/abs/2310.03714 | Programmatic signature + optimizer compile pattern |
| Tree-of-Thoughts (arXiv 2305.10601) | arxiv.org/abs/2305.10601 | Tree-search reasoning inspiration |
| AFlow (arXiv 2410.10762) | arxiv.org/abs/2410.10762 | Auto-workflow generation inspiration |
| Graph-of-Thoughts (arXiv 2308.09687) | arxiv.org/abs/2308.09687 | Graph reasoning inspiration |
| Toolformer (arXiv 2302.04761) | arxiv.org/abs/2302.04761 | API-calling tool-use baseline reference |
| Voyager (arXiv 2305.16291) | arxiv.org/abs/2305.16291 | Skill library + lifelong learning inspiration |
| Generative Agents (arXiv 2304.03442) | arxiv.org/abs/2304.03442 | Memory stream + reflection pattern reference |
| AutoGen (arXiv 2308.08155) | arxiv.org/abs/2308.08155 | Multi-agent conversable framework reference |

## Standards

- **ISO 31000** (Risk Management) — risk-based quality process control reference
- **ICH E6 GCP** (Good Clinical Practice) — DSMB-style independent review reference
- **OSF / AsPredicted** (Pre-registration) — pre-registration template inspiration
- **PRISMA / STROBE / CONSORT** (Reporting standards) — research reporting structure reference
- **scikit-learn k-fold** (Cross-validation) — out-of-sample validation reference

## Configuration (skill-specific)

- **Python 3.12+** + standard library (re, argparse, json, pathlib)
- **PowerShell 5.1+** (for backup scripts, not Python deps)
- **Git 2.30+** (for changelog + roadmap tracking)

## Licenses Summary

| License | Used by | How |
|---|---|---|
| MIT | Our skill, LangChain ODR, dzhng/deep-research | Permissive reuse |
| Apache-2.0 | smolagents, gpt-researcher, K-Dense | Permissive reuse |
| AGPL-3.0 | paper-agent | Network copyleft (when distributed) |
| No-AI-Training-1.0 | paper-agent (addendum) | Our skill prohibits use as AI training data |

We respect all upstream licenses. If you find a license conflict, please file an issue.
