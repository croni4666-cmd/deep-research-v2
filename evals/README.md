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

Prepare the complete three-mode, three-repeat matrix in one operation:

```powershell
python scripts\eval_bundle.py create-matrix `
  --suite offline-regression-v1 `
  --model gpt-example `
  --output path\to\run-matrices
```

This creates nine isolated bundles plus a hashed `matrix.json`. It prepares the
experiment but does not run a model. Verify every bundle before and after the
runs with:

```powershell
python scripts\eval_bundle.py validate-matrix path\to\run-matrix
```

`offline-regression-v1` retains the original three-case baseline. Use
`offline-regression-v2` for a higher-discrimination six-case matrix that also
tests denominator reversal, bounded negative evidence, and conflicts between
data dates and metric definitions:

```powershell
python scripts\eval_bundle.py create-matrix `
  --suite offline-regression-v2 `
  --model "exact-model-id" `
  --output path\to\run-matrices
```

Every matrix entry has a random `blind_id`. Keep `matrix.json`, which maps
`blind_id` to mode and repeat, away from reviewers. Store each case answer and
its downstream artifacts under the blind path:

```text
run-matrix/
  blind-artifacts/
    candidate-<opaque-id>/
      <case-id>/
        raw.md
        metrics.json
        review-a.json
        review-b.json
        adjudication.json
        final-review.json
```

Use one `raw.md` per case. Combining several cases in one raw file makes word,
source, and duplicate-row measurements non-comparable. The operator may see
the matrix mapping to dispatch the correct mode; candidate runners receive only
their bundle, and reviewers receive only anonymized case artifacts.

Inspect honest completion state at any time:

```powershell
python scripts\eval_status.py path\to\run-matrix
python scripts\eval_status.py path\to\run-matrix --require-stage raw
python scripts\eval_status.py path\to\run-matrix --require-stage metrics
python scripts\eval_status.py path\to\run-matrix --require-stage reviewed
```

The default `prepared` gate confirms only the matrix and bundles. Later gates
require all case runs to have non-empty raw answers, hash-linked automatic
metrics, or two complete reviews plus validated adjudication. Missing artifacts
remain missing; the checker never converts prepared work into completed runs.

After the `reviewed` gate passes, materialize one schema-v2 result for every
case run and one compatible three-mode comparison for every case and repeat:

```powershell
python scripts\eval_matrix_results.py path\to\run-matrix `
  --output path\to\run-matrix-results
```

The command validates the complete hash-linked review chain before writing any
output. It creates `individual/` results, `comparisons/` reports, and a
descriptive `summary.json`. Existing output directories are never overwritten.
If the matrix model string is unavailable, unknown, unspecified, or
unidentified, the summary sets `release_claim_ready` to `false` and records a
`model_identifier_unavailable` blocker even when every result validates.

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
`source_count` is the number of unique HTTP(S) URLs printed in the answer; it
is not the size of the evaluator-retained candidate `sources` array. Likewise,
a human reviewer may inspect more primary sources than the answer prints as
URLs. Validators keep those distinct measurements separate.

## Independent review and adjudication

First give the frozen raw answer an anonymized path that does not contain
`builtin`, `evidence`, or `combined`; the preparation command rejects paths
that reveal the mode. An exact catalog case-id path segment is exempt so a
valid case such as `adversarial-mirrored-evidence` is not mistaken for a mode
label. Prepare two review sheets from that same anonymized raw answer. Reviewer
IDs must be distinct:

```powershell
python scripts\eval_review.py prepare evals\raw\candidate-answer.md `
  --reviewer reviewer-a --date 2026-08-31 `
  --case-id adversarial-current-release-status `
  --output path\to\review-a.json

python scripts\eval_review.py prepare evals\raw\candidate-answer.md `
  --reviewer reviewer-b --date 2026-08-31 `
  --case-id adversarial-current-release-status `
  --output path\to\review-b.json
```

Each reviewer completes their sheet independently. Do not show either sheet to
the other reviewer. Automatic word, URL, and duplicate-row measurements are
excluded from these sheets so reviewers cannot overwrite them. Validate both
completed reviews and compare them:

```powershell
python scripts\eval_review.py validate path\to\review-a.json --complete
python scripts\eval_review.py validate path\to\review-b.json --complete
python scripts\eval_review.py compare path\to\review-a.json `
  path\to\review-b.json --output path\to\adjudication.json
```

The comparison hashes both review files and records every differing routing,
behavior, or human-metric judgment. It does not select a winner. An adjudicator
must fill `adjudicator_id`, `adjudicated_on`, and every disagreement's `final`
and `rationale`. Numeric adjudications may correct both reviewers when neither
count is accurate. Then validate and rebuild the complete final review:

```powershell
python scripts\eval_review.py validate-adjudication path\to\adjudication.json
python scripts\eval_review.py finalize path\to\adjudication.json `
  path\to\review-a.json path\to\review-b.json `
  --output path\to\final-review.json
```

Finalization rechecks the two review hashes, recomputes the disagreement set,
applies the resolutions, and validates all cross-field count relationships.
Agreement counts are descriptive and must not be presented as model quality.

## 2.4 evidence-release gate

Do not publish a comparative benchmark claim or mark the repeated pilot
complete until all of the following are true:

1. the same identifiable model and declared source access were used across
   compared modes;
2. `validate-matrix` passes before and after execution;
3. `eval_status.py --require-stage reviewed` passes for every declared case run;
4. raw answers, automatic metric reports, both independent reviews,
   adjudications, and final reviews are retained;
5. `eval_matrix_results.py` produces every expected case result and comparison;
6. schema-v2 result files pass `eval_results.py`; and
7. `eval_compare.py` accepts the compared results without a fingerprint or
   completed-case mismatch.

If any condition is unavailable, report the pilot as incomplete or blocked.
Infrastructure readiness alone is not evidence that one mode is better.

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
