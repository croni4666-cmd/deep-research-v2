# Isolated pilot summary — 2026-08-30

## Scope and method

Three fresh candidate contexts answered the same two trigger cases with the
same source boundary: a current semiconductor-policy comparison and the
offline mirrored-evidence fixture. The candidates used the built-in Deep
Research workflow, `evidence-deep-research`, or both in sequence. They could
not see the catalog expectations, fixture ground truth, or one another's
answers. A fourth fresh context tested a non-trigger quick fact.

The runtime did not expose model identifiers, elapsed time, token use, or
monetary cost. This is therefore a small directional pilot, not a publishable
leaderboard or a claim of statistical superiority.

## Results

| Mode | Trigger behaviors passed | Policy answer words | Policy source URLs | Mirrored answer words | Citation sample |
|---|---:|---:|---:|---:|---:|
| Built-in | 11/11 | 1,458 | 25 | 319 | 9/9 supported |
| Evidence | 11/11 | 650 | 14 | 281 | 9/9 supported |
| Combined | 11/11 | 1,072 | 27 | 334 | 9/9 supported |

All three modes:

- used an exact assessment date and official primary policy sources;
- separated enacted or operational measures from proposals and conditional
  instruments;
- traced the three favorable NQ-7 pages to one underlying company release;
- treated the independent registry search as inconclusive rather than as
  verification or disproof; and
- identified the underlying laboratory evidence needed to resolve the claim.

The quick-fact routing case returned only `Paris.` and initiated no web search,
research plan, or evidence ledger.

## Interpretation

The behavior rubric successfully detected the intended false-independence
failure mode, but it saturated: all three workflows passed every scored
behavior. Output and review-cost metrics were therefore added to distinguish
otherwise safe answers.

On this pilot, `evidence-deep-research` preserved the scored quality outcome
with the shortest policy answer: 55% fewer words than the built-in candidate.
The built-in candidate provided the broadest narrative coverage. The combined
candidate paired broad coverage with the clearest audit and stopping language,
but used the most source URLs and remained substantially longer than the
evidence-only response.

The practical default from this pilot is:

- use `evidence-deep-research` for most complex research where decision clarity
  and reading efficiency matter;
- use the combined workflow for high-stakes or reusable work where an explicit
  audit trail justifies the overhead;
- use the built-in workflow when breadth and exploratory discovery dominate.

This recommendation is provisional. More catalog categories, repeated runs,
known model identifiers, latency/cost capture, and a second reviewer are needed
before making a general superiority claim.

## Artifacts

- `pilot-builtin-2026-08-30.json`
- `pilot-evidence-2026-08-30.json`
- `pilot-combined-2026-08-30.json`
- `../raw/pilot-2026-08-30-builtin.md`
- `../raw/pilot-2026-08-30-evidence.md`
- `../raw/pilot-2026-08-30-combined.md`
- `../raw/pilot-2026-08-30-routing.md`
