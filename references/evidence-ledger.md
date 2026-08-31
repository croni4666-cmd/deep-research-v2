# Evidence ledger format

Use a JSON ledger when research is consequential, collaborative, reusable, or
will be checked by `scripts/evidence_audit.py`.

See [evidence-ledger-example.json](evidence-ledger-example.json) for a complete,
synthetic ledger containing all five access states. It is a schema example, not
real-world evidence.

```json
{
  "schema_version": 2,
  "research_questions": [
    {"id": "RQ1", "question": "...", "status": "resolved"}
  ],
  "claims": [
    {
      "id": "C1",
      "claim": "A precise, bounded claim",
      "importance": "key",
      "status": "verified",
      "evidence": [
        {
          "source_id": "S1",
          "url": "https://example.org/source",
          "title": "Source title",
          "publisher": "Publisher",
          "published_at": "2026-08-01",
          "accessed_at": "2026-08-30",
          "access": "full_text",
          "location": "Table 2, page 14",
          "excerpt": "Short quotation or accurate paraphrase of the relevant passage",
          "stance": "supports",
          "independence_group": "dataset:official-survey-2026"
        }
      ],
      "limitations": ["..."],
      "notes": ""
    }
  ]
}
```

## Required semantics

- `importance`: `key` or `supporting`.
- `status`: `verified`, `qualified`, or `unresolved`.
- `stance`: `supports`, `contradicts`, or `context`.
- `access`: `full_text`, `partial_text`, `metadata_only`, `blocked`, or
  `secondary_substitute`. This records what was actually inspected.
- `full_text`, `partial_text`, and `secondary_substitute` require a precise
  `location` and `excerpt`. `metadata_only` and `blocked` require an
  `access_note` describing the limitation and cannot support a claim.
- `independence_group` identifies the underlying record, dataset, experiment,
  or direct observation. Different websites reproducing the same material use
  the same group.
- Regional work may add `source_role` (`local_primary`, `external_primary`,
  `high_quality_synthesis`, or `discovery_or_experience`) plus non-empty
  `geography`, `population`, and `language` fields. These dimensions do not
  replace access or independence.
- A recommendation that transfers evidence across contexts may add a claim-level
  `transfer_assessment` with `source_context`, `target_context`, `level`,
  `rationale`, and `adaptations`. Valid levels are `directly_transferable`,
  `adaptation_required`, `pilot_only`, and `not_transferable`; adaptation and
  pilot levels require at least one named adaptation or test condition.
- Cross-country comparison claims may add `comparative_status` with one of
  `target_not_observed`, `avoid_mechanism_replication`,
  `present_different_degree`, or `positive_lesson_candidate`. This descriptive
  status does not replace the separate `transfer_assessment` decision.
- Unresolved claims may have no supporting evidence, but they must remain
  visibly unresolved in the report.
- A verified key claim normally needs at least two supporting independence
  groups. Lower the threshold only when the research plan explains why the
  evidence cannot reasonably be duplicated.

The ledger records traceability. It does not replace inspecting the source or
judging whether the evidence supports the wording of the claim.

Schema version 1 remains accepted for old ledgers, with access reported as
`legacy_unspecified`. New ledgers should use version 2.
