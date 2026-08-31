# Forward-evaluation catalog

`cases.json` contains realistic prompts and observable expectations for testing
the Skill. It is deliberately separate from `SKILL.md` so evaluation detail
does not increase runtime context or alter research behavior.

`suites.json` selects versioned groups of cases, allowed modes, repeat counts,
source-access policy, and whether live web access is permitted. Validate it
before preparing runs:

```powershell
python scripts\eval_suites.py
```

Prepare a collision-safe run bundle in a user-authorized output directory:

```powershell
python scripts\eval_bundle.py create `
  --suite offline-independence-v1 `
  --mode evidence `
  --model gpt-example `
  --repeat 1 `
  --output path\to\run-bundles
```

The bundle records prompts, source policy, the skill commit, and SHA-256 hashes
for declared inputs and candidate fixture files. It excludes evaluator-only
ground truth and does not run or score a model.

Revalidate the prepared bytes before and after a candidate run:

```powershell
python scripts\eval_bundle.py validate path\to\run-bundle
```

The repeated offline regression suite covers copied evidence, stale release
status, and duplicated Markdown table rows without live-web variability:

```powershell
python scripts\eval_bundle.py create `
  --suite offline-regression-v1 `
  --mode evidence `
  --model gpt-example `
  --repeat 1 `
  --output path\to\run-bundles
```

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

Completed cases also use a `metrics` object. Counts are deliberately simple
and reviewable: final-answer words, sources reported in the raw answer, primary
sources, sampled citations and supported samples, unsupported claims found in
that sample, and key claims classified as supported or unresolved. These
metrics distinguish answers that satisfy the same safety rubric but differ
materially in coverage, precision, and reading cost. They are not a single
composite quality score.

Raw candidate responses belong in `evals/raw/`. Freeze them before exposing
the candidate runner to catalog expectations or evaluator-only ground truth.

After freezing one case's raw answer, extract only deterministic measurements:

```powershell
python scripts\eval_ingest.py path\to\run-bundle\manifest.json `
  evals\raw\candidate-answer.md `
  --case-id adversarial-duplicate-table-row `
  --output path\to\metric-extraction.json
```

The extraction report hashes both inputs and counts lexical words, unique
reported HTTP(S) URLs, and repeated normalized Markdown data rows. It does not
infer primary-source status, citation entailment, unsupported claims, claim
support, or truth; reviewers must score those fields.

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

Historical schema-v1 results remain valid. New schema-v2 results add:

- `run.suite_id` and the one-based `run.repeat`;
- SHA-256 records for the bundle manifest, raw output, and metric extraction;
- per-metric provenance (`automatic` or `human`);
- the automatic `duplicate_table_row_count` check.

In schema v2, only `output_word_count` and `source_count` are automatically
derived. All semantic quality fields remain explicitly human-reviewed.

Compare two or more completed results only when their model, prompt revision,
source access, and completed case sets match:

```powershell
python scripts\eval_compare.py result-builtin.json result-evidence.json
```

The comparison command fails closed on mismatched fingerprints. It reports
behavior judgments, citation samples, unsupported claims, answer length, and
source count separately; it does not emit an opaque winner score.

## Catalog validation

```powershell
python scripts\eval_catalog.py evals\cases.json --strict
```

The validator checks schema, minimum coverage, unique identifiers, risk mix,
non-trigger cases, and required adversarial themes. It does not run an LLM or
score research quality.
