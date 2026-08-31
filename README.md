# Evidence Deep Research

A portable agent skill for complex research that requires inspected sources,
cross-checking, explicit uncertainty, and traceable claims.

The project is a research workflow skill, not a hosted search engine or an LLM.
It uses the tools and model available in the active runtime. Its optional
Python helpers validate plan and evidence structure; they do not perform web
research or prove factual correctness.

## What changed in 2.7.3

- Added a schema-v2 receipt fingerprint so unrehashed edits to the approval
  reference or any other receipt field fail closed.
- Renamed the successful verification result to
  `RECEIPT_MATCHES_CURRENT_PLAN`; local hashes establish file consistency, not
  user identity or cryptographic proof of approval.
- Documented legacy-receipt migration and a single-active-Skill rule for Mavis
  to prevent ambiguous routing between old and current research Skills.

## Install in Codex

Copy this repository to the personal Skills directory under the folder name
`evidence-deep-research`:

```powershell
Copy-Item -Recurse . "$env:USERPROFILE\.codex\skills\evidence-deep-research"
```

Restart or reload Codex if the skill does not appear immediately.

## Install in MiniMax Mini-Agent

Build a minimal bundle, then place the generated folder under Mini-Agent's
configured `skills_dir`:

```powershell
python scripts\package_skill.py --target minimax --output path\to\packages
```

Enable Skills in Mini-Agent and configure search/open tools or MCP separately.
Loading a Skill does not itself provide web access. See
[`compatibility/README.md`](compatibility/README.md) and the example Mini-Agent
configuration. A Mavis session that cannot demonstrably load the Skill must be
reported as protocol-only, not as a v2.7.3 run.

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

The first output label is `STRUCTURAL_PASS` or `STRUCTURAL_FAIL`. Exit codes:

- `0`: structural audit passed;
- `1`: evidence or warning policy failed;
- `2`: input, file, or command-line error.

Passing means the ledger satisfies deterministic traceability rules. It does
not mean the claims are true or that the citations entail them.
The complete synthetic example at
[`references/evidence-ledger-example.json`](references/evidence-ledger-example.json)
contains every supported access state.

## Runtime capability check

Before comparing runs across products, declare the capabilities actually
available in that session:

```json
{
  "schema_version": 1,
  "runtime": "minimax-mini-agent",
  "model_identifier": "exact-model-id-if-exposed",
  "skill_loaded": true,
  "search": true,
  "open_url": true,
  "read_local_files": true,
  "mcp": true,
  "subagents": true
}
```

Save this as JSON and run `python scripts/runtime_check.py manifest.json`. The
result is `native`, `compatible`, or `protocol-only`; it describes execution
conditions declared in the manifest, not detected capabilities or research
quality. `write_local_files`, `shell`, `mcp`, and `subagents` may be omitted and
default to `false`.

## Portable research depth

The core Skill loads deeper guidance only when the task needs it:

- [`references/region-source-routing.md`](references/region-source-routing.md)
  routes regional claims by provenance and claim type;
- [`references/transferability.md`](references/transferability.md) separates
  evidence strength from cross-context applicability;
- [`references/comparative-framing.md`](references/comparative-framing.md)
  prevents biased “avoid another country's outcome” wording before transfer is
  assessed;
- [`references/parallel-research.md`](references/parallel-research.md) defines
  worker, merge, and verifier contracts for runtimes with real subagents.

`subagents: true` only marks parallel research as a candidate. Confirm that
workers inherit the required search/open tools. Generated prompts, empty result
objects, and multiple model opinions are not executed agents or independent
evidence.

For broad, costly, or materially ambiguous work, the plan must be shown in the
conversation and research must pause until the user approves it. Running
`plan_preview.py` or saving a plan file does not count as approval.

## Plan preview and auditable approval

Preview a bounded plan without launching research:

```powershell
python scripts\plan_preview.py --topic "Your topic" --region CN --depth 3
```

The helper prints to standard output by default. When `--out` is used, it
refuses to replace an existing file unless `--force` is explicitly supplied.

For work that spans sessions or workers, or requires an audit trail, use a plan
record and a separate approval receipt:

```powershell
python scripts\plan_record.py create --topic "Your topic" --region CN --depth 3 --out research-plan.json
python scripts\plan_record.py approve research-plan.json --approval-reference "conversation: user approved displayed plan"
python scripts\plan_record.py verify research-plan.json
```

Run `approve` only after explicit user approval. Verification returns
`RECEIPT_MATCHES_CURRENT_PLAN` only when the receipt and current plan are
internally consistent. It returns `NO_CURRENT_MATCHING_RECEIPT` if the receipt
is missing, stale, legacy, modified without rehashing, or the plan was changed.
These local hashes do not authenticate the approving user. See
[`references/plan-artifact.md`](references/plan-artifact.md).

## Development

Requirements: Python 3.12 or newer; runtime helpers use only the standard
library.

```powershell
python -m compileall -q scripts tests
python -m unittest discover -s tests -v
python scripts\release_check.py --expected-version 2.7.3
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
not run a model or prove truth. The matrix result builder also blocks release
claims when the actual model identifier is unavailable.

## Scope and limitations

- Source availability, model judgment, and tool behavior still affect quality.
- MiniMax compatibility means the portable Skill contract can be loaded by its
  documented Skills mechanism; exact Mavis product capabilities remain dependent
  on the session's exposed tools and permissions.
- The evidence audit cannot determine truth, source independence in the real
  world, or citation entailment without substantive review.
- The skill does not provide a code sandbox and never authorizes external
  side effects beyond the user's request.

See [`SECURITY.md`](SECURITY.md), [`CHANGELOG.md`](CHANGELOG.md), and
[`THIRD_PARTY.md`](THIRD_PARTY.md) for additional details.
