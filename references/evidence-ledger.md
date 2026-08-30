# Evidence ledger format

Use a JSON ledger when research is consequential, collaborative, reusable, or
will be checked by `scripts/evidence_audit.py`.

```json
{
  "schema_version": 1,
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
- `independence_group` identifies the underlying record, dataset, experiment,
  or direct observation. Different websites reproducing the same material use
  the same group.
- Unresolved claims may have no supporting evidence, but they must remain
  visibly unresolved in the report.
- A verified key claim normally needs at least two supporting independence
  groups. Lower the threshold only when the research plan explains why the
  evidence cannot reasonably be duplicated.

The ledger records traceability. It does not replace inspecting the source or
judging whether the evidence supports the wording of the claim.
