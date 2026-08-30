# Forward-evaluation catalog

`cases.json` contains realistic prompts and observable expectations for testing
the Skill. It is deliberately separate from `SKILL.md` so evaluation detail
does not increase runtime context or alter research behavior.

## Modes to compare

Run every trigger case in three modes:

1. the available built-in or plugin Deep Research workflow;
2. `evidence-deep-research` with the same model and source access;
3. the Deep Research workflow followed by evidence-ledger conversion and audit.

Non-trigger cases test routing only and should be answered without a research
workflow.

Cases with a `fixture` field must be run with only the candidate material named
by that fixture. Evaluator-only ground truth must not be exposed to the mode
being scored.

Each compared mode must run in a fresh context. Do not load another mode's
output or evaluator-only ground truth into the candidate context. If isolation
is unavailable or ground truth was exposed, record the case as `blocked` or
`not_evaluated` instead of assigning scores.

## Recording a run

For each case and mode, record:

- date, model, tools, enabled data sources, and prompt revision;
- completion status and elapsed time;
- whether every expected and forbidden behavior was observed;
- number of key claims, supported key claims, and unresolved key claims;
- citation precision from a human-reviewed sample;
- unsupported-claim count from a human-reviewed sample;
- token or monetary cost when the runtime exposes it;
- reviewer notes and links to retained artifacts.

Do not combine runs from different models, source access, or prompt revisions
without labeling the difference. Do not publish benchmark scores until the raw
case-level results and evaluation method are reviewable.

Validate a retained result file against the catalog with:

```powershell
python scripts\eval_results.py path\to\result.json --allow-partial
```

`--allow-partial` is required for a pilot that intentionally runs only part of
the catalog. Validation checks structure and catalog consistency; it does not
turn reviewer judgments into objective quality measurements.

## Catalog validation

```powershell
python scripts\eval_catalog.py evals\cases.json --strict
```

The validator checks schema, minimum coverage, unique identifiers, risk mix,
non-trigger cases, and required adversarial themes. It does not run an LLM or
score research quality.
