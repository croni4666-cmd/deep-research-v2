# Step 3: Build a proportional research plan

Create 3-7 non-overlapping research questions. For each, identify:

- why it matters to the final conclusion;
- the preferred evidence type and likely primary sources;
- dependencies on other questions;
- freshness, geography, population, or methodology constraints;
- a fallback if the preferred evidence is unavailable.

Order questions by decision impact and dependency. Define stopping conditions
before searching so the process cannot grow without bound.

If at least three questions have no unresolved dependency on one another,
record them as parallelizable. Parallel execution is optional and only
available when the runtime has actually declared subagent capability; follow
[../references/parallel-research.md](../references/parallel-research.md).

For broad, expensive, or materially ambiguous work, present the concise plan to
the user and wait for approval. If the user already supplied or approved a clear
plan, continue without another approval gate. For research spanning sessions,
multiple workers, material cost or risk, or an audit requirement, read
[../references/plan-artifact.md](../references/plan-artifact.md) and consider an
optional plan record plus a separate approval receipt.

The approval gate is satisfied only by the user's approval in the conversation.
Generating `plan_preview` output or writing a plan file does not satisfy it. Do
not begin source research while approval is pending. A runtime that cannot pause
must return the plan and stop; it must not silently continue in the same run.
If an approved plan's fingerprint changes, approval is stale and the revised
plan must be shown and approved again before source research resumes.
