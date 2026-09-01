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

## Skill loading attestation

Use three load states rather than a boolean:

- **verified**: the session or operator confirmed that the complete `SKILL.md`
  was read from an identified location. Record `loaded_from`; add a SHA-256
  content hash when the runtime can compute it.
- **partial**: only a summary, excerpt, prompt copy, or unverified Skill listing
  was available. The workflow may be protocol-assisted, but it is not a
  complete versioned Skill run.
- **false**: the Skill was not loaded.

Do not report `verified` merely because the Skill name/version was supplied in
the prompt or appeared in a directory listing. A declaration is still an
operator/runtime attestation, not remote proof.

At the beginning of a consequential run, record the runtime, model identifier
when exposed, Skill load state and provenance, and whether source search and
opening are available. `scripts/runtime_check.py` can classify this declaration.
It classifies values supplied by the operator or runtime; it does not detect,
probe, or attest that a product actually loaded the Skill. Missing optional
write, shell, MCP, and subagent fields default to `false`.

New manifests should use schema version 2. Schema version 1 boolean manifests
remain readable for migration, but `skill_loaded: true` is conservatively
treated as partial and produces a warning because it cannot establish complete
loading.

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

Keep only one broadly triggered deep-research Skill active in a Mavis
`skills_dir`. If a legacy `deep-research` Skill and `evidence-deep-research`
coexist, their descriptions may both match the same request; folder names do
not establish precedence. Back up the legacy Skill outside `skills_dir`, load
`evidence-deep-research`, and retain a run record containing the reported Skill
version. If the product cannot reveal which Skill it loaded, treat the run as
protocol-only rather than choosing by inference.

Runtime formats can change. Re-run the capability declaration after upgrades
or when tools, MCP servers, permissions, or model settings change.

When `runtime_check.py` reports `parallel_research_candidate: true`, this means
only that the declared Skill, source-inspection, and subagent capabilities are
compatible with the parallel protocol. Confirm that workers inherit the needed
source tools before following `parallel-research.md`.
