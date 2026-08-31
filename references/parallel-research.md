# Conditional parallel research

Use parallel research only when the runtime actually exposes subagents, at
least three research questions can proceed independently, and the expected
coverage benefit exceeds coordination cost. Otherwise research serially.

Multiple agents are not independent evidence. They may discover or interpret
the same underlying record and must share its `independence_group`.

## Dispatch contract

Assign non-overlapping questions or source classes. Give each worker the same
scope, cutoff date, access policy, and safety boundaries. Require a structured
return containing:

- `question_id` and bounded conclusion;
- inspected evidence items compatible with the evidence-ledger schema;
- contradictions, failed access attempts, and unresolved points;
- underlying independence groups;
- search cutoff and important scope limitations.

Workers do not write the final answer, change the research scope, or claim
coverage outside their assignment. Do not dispatch credentials, private data,
or external side effects without the same authorization required in the main
session.

## Merge and verify

The coordinating agent must:

1. reject malformed or unsupported findings;
2. merge duplicate underlying evidence before counting support;
3. reconcile differences in definitions, dates, populations, and geography;
4. retain contradictions and unresolved questions;
5. identify coverage gaps before synthesis.

When the runtime permits an isolated verifier, give it the frozen draft and
ledger, not the desired conclusion. The verifier reports unsupported wording,
citation mismatch, hidden transfer assumptions, duplicate evidence, and missed
contradictions. It does not silently rewrite or approve the answer. The
coordinating agent resolves or exposes every material issue.

If no real worker or verifier was invoked, do not describe generated prompts,
empty result objects, or a local loop as multi-agent research.
