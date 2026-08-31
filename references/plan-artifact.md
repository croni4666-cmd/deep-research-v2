# Auditable plan artifact

Use a plan artifact when research will span sessions, involve multiple workers,
carry material cost or risk, or require an audit trail. It is optional for
ordinary single-session work and does not replace showing the plan to the user.

The artifact uses two files:

- the plan record contains the bounded questions, source requirements, stopping
  conditions, and a SHA-256 content fingerprint;
- the approval receipt points to the exact approved fingerprint and records how
  the actual user approval can be located.

Creating either a preview or a plan record never satisfies the approval gate.
Only explicit user approval in the conversation does. Run the `approve` command
only after that event; `approval_reference` is an operator attestation, not
independent proof that approval occurred.

## Create, approve, and verify

```powershell
python scripts\plan_record.py create --topic "Research topic" --region CN --depth 3 --out research-plan.json
python scripts\plan_record.py approve research-plan.json --approval-reference "conversation: user approved the displayed plan"
python scripts\plan_record.py verify research-plan.json
```

Use a real, non-invented reference appropriate to the runtime, such as a turn
identifier or a concise description of the approval message. Do not place
private conversation content in a shared artifact unless authorized.

The plan retains `approval_status: pending`; receipt state is derived from the
separate receipt. This prevents a saved plan from representing itself as user
approved. Receipt schema v2 fingerprints its own fields as well as naming the
plan hash, so accidental or unrehashed edits to either file are detected.
Verification emits:

- `RECEIPT_MATCHES_CURRENT_PLAN` with exit code `0` only when both artifacts are
  internally intact and the receipt names the exact current plan hash;
- `NO_CURRENT_MATCHING_RECEIPT` with exit code `1` when the receipt is absent,
  stale, legacy, edited without rehashing, or the plan has changed;
- `ERROR` with exit code `2` for unreadable input or command misuse.

These hashes detect inconsistency; they do not authenticate the operator or
prove that a user approved the plan. Anyone able to rewrite both files can
recompute both hashes. High-assurance workflows need a runtime-provided signed
event, trusted audit log, or external timestamp service outside this helper.

Use a non-invented, minimally identifying reference. Examples include
`session-2026-09-01-turn-42`, an opaque platform turn ID, or
`conversation: user approved displayed plan`. Avoid copying private message
content into a shared artifact.

Receipt schema v1 from v2.7.2 remains readable but fails closed because it has
no receipt integrity hash. After checking the original conversation, run
`approve --force` to replace it with schema v2; do not migrate by merely adding
fields or by assuming that the old file proves approval.

If scope, questions, source policy, or stopping conditions change materially,
create a new plan record or explicitly replace the old one, show the revised
plan to the user, and obtain new approval. Never carry a receipt forward across
a changed fingerprint.
