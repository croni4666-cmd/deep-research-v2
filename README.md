# Evidence Deep Research

A Codex skill for complex research that requires inspected sources,
cross-checking, explicit uncertainty, and traceable claims.

The project is a research workflow skill, not a hosted search engine or an LLM.
It uses the tools and model available in the active Codex runtime. Its optional
Python helpers validate plan and evidence structure; they do not perform web
research or prove factual correctness.

## What changed in 2.2.0

- The installed skill is named `evidence-deep-research` to avoid colliding with
  built-in or plugin-provided Deep Research skills.
- Research quality is tracked with a structured claim/evidence ledger.
- Independent evidence means different underlying records, datasets,
  experiments, or observations—not merely different websites.
- Legacy URL-counting, self-PASS markers, placeholder execution modes, and the
  invalid Cohen's kappa approximation were removed.
- Adversarial tests cover empty evidence, arbitrary URLs, copied evidence on
  different hosts, strict warnings, and output overwrite protection.

## Install in Codex

Copy this repository to the personal Skills directory under the folder name
`evidence-deep-research`:

```powershell
Copy-Item -Recurse . "$env:USERPROFILE\.codex\skills\evidence-deep-research"
```

Restart or reload Codex if the skill does not appear immediately.

## Use

Ask for a complex, source-heavy investigation, for example:

```text
Use evidence deep research to compare the latest semiconductor industrial
policies in China, the United States, Japan, and the EU. Separate verified facts
from inference, prioritize primary sources, and explain unresolved conflicts.
```

The skill should not activate for quick facts or ordinary web lookups.

## Evidence ledger

For consequential or reusable work, use the JSON format documented in
[`references/evidence-ledger.md`](references/evidence-ledger.md). Audit it with:

```powershell
python scripts\evidence_audit.py path\to\ledger.json --strict
```

Exit codes:

- `0`: structural audit passed;
- `1`: evidence or warning policy failed;
- `2`: input, file, or command-line error.

Passing means the ledger satisfies deterministic traceability rules. It does
not mean the claims are true or that the citations entail them.

## Plan preview

Preview a bounded plan without launching research:

```powershell
python scripts\plan_preview.py --topic "Your topic" --region CN --depth 3
```

The helper prints to standard output by default. When `--out` is used, it
refuses to replace an existing file unless `--force` is explicitly supplied.

## Development

Requirements: Python 3.12 or newer; runtime helpers use only the standard
library.

```powershell
python -m compileall -q scripts tests
python -m unittest discover -s tests -v
python <skill-creator-dir>\scripts\quick_validate.py .
```

GitHub Actions runs compilation, adversarial tests, catalog and suite
validation, and a CLI smoke test on Python 3.12 and 3.13.

## Forward evaluation

The versioned catalog in [`evals/cases.json`](evals/cases.json) covers routing,
policy, market, medical, academic, technical, and adversarial scenarios. Check
its schema and coverage with:

```powershell
python scripts\eval_catalog.py evals\cases.json --strict
python scripts\eval_suites.py evals\suites.json
```

See [`evals/README.md`](evals/README.md) for run-bundle creation, hash
revalidation, raw-output metric extraction, schema-v2 provenance, repeated
offline regressions, independent-review adjudication, and fail-closed
comparison commands. Matrix completion gates distinguish prepared bundles from
retained raw, measured, and independently reviewed case runs. These helpers do
not run a model, prove truth, or create benchmark scores without retained human
review.

## Scope and limitations

- Source availability, model judgment, and tool behavior still affect quality.
- The evidence audit cannot determine truth, source independence in the real
  world, or citation entailment without substantive review.
- The skill does not provide a code sandbox and never authorizes external
  side effects beyond the user's request.

See [`SECURITY.md`](SECURITY.md), [`CHANGELOG.md`](CHANGELOG.md), and
[`THIRD_PARTY.md`](THIRD_PARTY.md) for additional details.
