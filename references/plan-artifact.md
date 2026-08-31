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

The plan retains `approval_status: pending`; approval state is derived from the
separate receipt. This prevents a saved plan from representing itself as user
approved. Verification emits:

- `APPROVED_CURRENT` with exit code `0` only when the plan is internally intact
  and the receipt names its exact hash;
- `NOT_APPROVED_CURRENT` with exit code `1` when approval is absent, stale, or
  the plan has changed;
- `ERROR` with exit code `2` for unreadable input or command misuse.

If scope, questions, source policy, or stopping conditions change materially,
create a new plan record or explicitly replace the old one, show the revised
plan to the user, and obtain new approval. Never carry a receipt forward across
a changed fingerprint.
