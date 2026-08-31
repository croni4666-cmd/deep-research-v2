# Changelog

## 2.4.0 - Unreleased

- Added versioned live, offline, routing, pilot, and repeated-run suite
  manifests with validation against the case catalog.
- Added collision-safe run-bundle creation with prompt, skill, catalog, suite,
  and candidate-fixture hashes while excluding evaluator ground truth.
- Added bundle revalidation that detects prompt, skill, catalog, suite, and
  candidate-fixture drift before comparison.
- Added fail-closed paired comparison reports that reject model, prompt,
  source-access, mode, or completed-case incompatibility.
- Added regression tests for suite boundaries, bundle isolation, hashing, and
  comparison compatibility.
- Added backward-compatible result schema v2 with suite/repeat linkage,
  artifact hashes, automatic-check output, and per-metric provenance.
- Extended fail-closed comparisons to reject mixed schema versions and v2
  suite or repeat mismatches.
- Added raw-answer ingestion for deterministic word, unique-link, and duplicate
  Markdown-row measurements without making semantic quality judgments.
- Added offline stale-release-status and duplicate-table-row fixtures plus a
  repeated three-mode regression suite.
- Added one-command creation and revalidation of the complete declared
  mode-by-repeat run matrix without claiming that candidate runs occurred.
- Added blinded two-reviewer sheets, strict artifact matching, field-level
  disagreement reports, explicit adjudication, and validated final-review
  reconstruction.

## 2.3.0 - 2026-08-31

- Added a versioned catalog of realistic trigger, routing, high-risk, and
  adversarial research requests.
- Added deterministic catalog validation for category, risk, routing, and
  adversarial-theme coverage.
- Added repository tests and CI validation for the evaluation catalog.
- Documented a three-mode comparison protocol without fabricating benchmark
  scores or increasing runtime Skill context.
- Added an offline mirrored-evidence fixture and a case-level result validator
  with explicit isolation, reviewer-note, source-retention, and partial-run
  requirements.
- Ran a blinded three-mode pilot, retained raw outputs, and added comparable
  output, source, claim, and citation-sample metrics to completed results.
- Added a second-pass compression rule after the pilot showed that all modes
  could meet the safety rubric while differing substantially in reading cost.
- Added final canonical-release verification for latest-version claims after a
  second-round candidate reported the previous Dagster release as current.
- Added a duplicate-row check after compression produced a repeated benchmark
  entry in an otherwise supported academic synthesis.

## 2.2.0 - 2026-08-30

- Renamed the installed skill to `evidence-deep-research` to avoid collisions
  with other Deep Research skills.
- Replaced proximity- and marker-based heuristics with a structured evidence
  ledger audit.
- Defined independence by underlying evidence rather than hostname count.
- Removed the invalid Cohen's kappa approximation and legacy self-pass markers.
- Replaced the inactive LangChain harness with an honest, collision-safe plan
  preview helper.
- Added adversarial unit tests and GitHub Actions for Python 3.12 and 3.13.
- Clarified that deterministic checks do not prove truth or citation entailment.
- Cleaned project positioning, third-party acknowledgments, security review,
  version metadata, and license labeling.

## 2.1.1-codex.1 - 2026-08-29

- Initial Codex-compatible release candidate.
