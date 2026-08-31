# Runtime compatibility

This Skill uses a platform-neutral contract: load `SKILL.md`, follow its
relative references, inspect sources, and cite what was actually inspected.
Shell, file-writing, subagents, and deterministic helpers are optional. Their
absence must reduce convenience, not be disguised as successful execution.

## Capability levels

- **native**: the runtime loaded this Skill and can both discover and open
  sources. It may claim a complete Skill run.
- **compatible**: the runtime loaded this Skill and can inspect user-supplied or
  otherwise available sources, but cannot independently search the web. State
  that discovery was constrained and do not imply comprehensive coverage.
- **protocol-only**: the Skill was not loaded, or the runtime cannot inspect
  source content. It may use the workflow as a prompt, but must label the result
  a simulation and must not call it a versioned Skill run.

At the beginning of a consequential run, record the runtime, model identifier
when exposed, whether the Skill was loaded, and whether source search and
opening are available. `scripts/runtime_check.py` can classify this declaration.
It classifies values supplied by the operator or runtime; it does not detect,
probe, or attest that a product actually loaded the Skill. Missing optional
write, shell, MCP, and subagent fields default to `false`.

## Codex

Install the runtime bundle as `evidence-deep-research` in the configured Codex
Skills directory. Built-in search/page tools may satisfy source discovery and
inspection. Do not assume terminal commands are sandboxed.

## MiniMax Mini-Agent

Point Mini-Agent's `skills_dir` at a directory containing the
`evidence-deep-research` folder and enable Skills. Web research additionally
requires tools or an MCP server that can search and open sources; enabling the
Skill alone does not create web access. File and shell tools are optional.

Example configuration is in `compatibility/minimax/config-example.yaml` in the
repository. The packaged Skill itself contains no Codex-only tool names.

## Mavis and other hosted agents

Claim native or compatible execution only when the session demonstrably loaded
the Skill and can inspect sources. If the interface accepts only pasted prompts
or cannot expose its loaded Skills, use protocol-only and say so. Do not infer
capabilities from a product name or from API compatibility alone.

Runtime formats can change. Re-run the capability declaration after upgrades
or when tools, MCP servers, permissions, or model settings change.

When `runtime_check.py` reports `parallel_research_candidate: true`, this means
only that the declared Skill, source-inspection, and subagent capabilities are
compatible with the parallel protocol. Confirm that workers inherit the needed
source tools before following `parallel-research.md`.
