# Codex security and reliability review

**Reviewed:** 2026-08-30
**Version:** 2.2.0

## Current scope

The installable Skill contains its entrypoint, six workflow steps, one evidence
ledger reference, and two standard-library Python helpers. Tests and project
documentation are included in the repository but are not runtime authority.

## Security properties

- Retrieved content is explicitly untrusted and cannot supply instructions.
- The Skill does not claim that the local terminal is sandboxed.
- The plan preview does not search, delegate, execute generated code, or claim
  verification.
- The evidence audit reads one user-selected JSON file and performs no network
  access.
- Output replacement requires an explicit `--force` flag.
- Empty ledgers, malformed evidence, missing locations, invalid URLs, and
  insufficient independent evidence fail closed.

## Reliability limits

Deterministic checks validate structure and declared independence groups. They
cannot establish factual correctness, detect deceptive source content, or prove
that an excerpt entails a claim. Those remain substantive review tasks.

## Reproducible checks

```powershell
python -m compileall -q scripts tests
python -m unittest discover -s tests -v
python scripts\plan_preview.py --topic "security smoke test" --json
python <skill-creator-dir>\scripts\quick_validate.py .
```

The CI workflow runs compilation, adversarial tests, and a plan-preview smoke
test on Python 3.12 and 3.13.

## Release criterion

A release must not claim a successful research or factual audit from placeholder
content, URL counts, self-authored PASS markers, or simulated evaluator scores.
