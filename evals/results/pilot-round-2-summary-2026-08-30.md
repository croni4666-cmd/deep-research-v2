# Isolated pilot round 2 — 2026-08-30

## Scope

Three fresh candidate contexts answered the same market, medical, academic, and
technical catalog cases. They used the built-in workflow,
`evidence-deep-research` 2.3.0, or both in sequence. Candidates could not see
the catalog expectations, prior results, or one another's output.

The medical condition and the three technical libraries were deliberately not
specified. This tested whether a workflow would expose assumptions and evidence
gaps instead of inventing a condition-specific conclusion or hiding its library
selection.

## Aggregate results

| Mode | Desired behaviors | Sampled citations supported | Final-answer words | Source URLs |
|---|---:|---:|---:|---:|
| Built-in | 19/20 | 13/14 | 2,185 | 40 |
| Evidence | 20/20 | 14/14 | 2,479 | 33 |
| Combined | 20/20 | 14/14 | 2,045 | 29 |

| Case | Built-in words | Evidence words | Combined words |
|---|---:|---:|---:|
| EV forecasts | 522 | 521 | 419 |
| Medical screening | 482 | 520 | 411 |
| RAG evaluation | 652 | 831 | 558 |
| Python orchestration | 529 | 607 | 657 |

## Findings

All three modes correctly:

- converted incompatible EV forecasts into scenarios rather than averaging
  them or presenting one certain number;
- treated the hypothetical screening question as insufficiently specified,
  distinguished insufficient evidence from ineffectiveness, and stayed at the
  population-policy level;
- compared RAG datasets and metrics by setup while exposing judge and benchmark
  limitations; and
- separated open-source maintenance evidence from commercial compliance and
  support claims.

One consequential factual miss separated the modes. The built-in candidate
reported Dagster 1.13.19 as the latest stable release on 30 August 2026. The
canonical PyPI history shows 1.13.20 released on 27 August and 1.13.19 on 21
August. Evidence and combined modes reported 1.13.20 correctly.

The evidence-only academic answer also listed RAGTruth twice in one comparison
table. The duplicate did not change the conclusion or citation support, but it
is a visible editing defect.

## Skill changes driven by the round

- Exact current-version claims must now be rechecked against canonical release
  history immediately before writing, including stable, prerelease, development,
  yanked, withdrawn, and unsupported status.
- The compression pass now includes an explicit duplicate-entity and
  duplicate-row scan for tables and lists.

## Interpretation

The combined workflow performed best in this small round: it avoided the
current-version miss, used the fewest total words and source URLs, and passed
all behavior checks. Evidence-only also passed every behavior and citation
sample, but was longest overall and had the duplicate table row. Built-in was
otherwise strong and often concise, but its stale exact-version claim matters
for a regulated technical decision.

This remains directional evidence. Exact model identifiers, elapsed time,
token use, and cost were unavailable for two candidates; combined reported only
the broad model name GPT-5. Repeated runs and a second reviewer remain necessary
for a general comparative claim.

## Artifacts

- `pilot-round-2-builtin-2026-08-30.json`
- `pilot-round-2-evidence-2026-08-30.json`
- `pilot-round-2-combined-2026-08-30.json`
- `../raw/pilot-round-2-2026-08-30-builtin.md`
- `../raw/pilot-round-2-2026-08-30-evidence.md`
- `../raw/pilot-round-2-2026-08-30-combined.md`
