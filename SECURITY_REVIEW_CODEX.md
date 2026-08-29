# Codex security review

**Reviewed:** 2026-08-29

**Release candidate:** `2.1.1-codex.1`

**Original archive SHA-256:** `E4BC88D89C8DE79EDDF496DFAD7931662059A005C33CB65F98262CEC61071DFC`

## Scope

The review covered the complete release surface: `SKILL.md`, six workflow step
files, five Python helpers, licensing/security documentation, and packaging
metadata. Historical reports and simulation-only prototypes were removed from
the installable package and retained outside the repository as a recoverable
local backup.

## Checks performed

- Compared all 45 files in the supplied ZIP with the extracted staging copy;
  no missing files or hash mismatches were found before remediation.
- Scanned Python and instruction files for subprocess execution, shell escape,
  dynamic evaluation, deserialization, network clients, credential access,
  destructive filesystem operations, private keys, tokens, and machine-specific
  paths.
- Verified that retrieved webpages, PDFs, repositories, and quotations are
  treated as untrusted data and cannot supply executable instructions.
- Removed false sandbox assumptions and disabled code-acting execution because
  the package does not provide a real isolated runtime.
- Removed the bundled `.pyc`; the release surface contains no executable binary
  artifacts.
- Parsed every retained Python file with the Python AST parser.
- Ran the Codex Skill Creator structural validator.
- Tested negative and missing-evidence paths to ensure the helpers fail closed.
- Performed an independent forward review with a realistic medical-policy
  research request; no material workflow or authorization blocker remained.

## Regression results

| Check | Expected result | Observed |
| --- | --- | --- |
| Skill structure | valid | pass |
| Retained Python syntax | 5/5 parse | pass |
| Non-dry planning harness | refuse execution | exit 2 |
| Dry-run planning harness | plan only, unverified | exit 0, `verified: false` |
| Triangulation with zero claims | not evaluated | exit 5 |
| DRIFT with unsupported claims | fail | exit 3 |
| Self-audit with missing markers | fail | exit 1 |
| Audit of missing report | fail | exit 2 |
| High-risk retained-code pattern scan | no matches | pass |
| Binary artifact scan | zero files | pass |

## Residual risk

This is a prompt/workflow skill, not a security sandbox. Research quality still
depends on source availability, tool behavior, model judgment, and faithful
application of the stated boundaries. Heuristic audit scripts can flag obvious
problems but cannot prove factual correctness or citation entailment.

## Verdict

No known high-severity blocker remains in release candidate
`2.1.1-codex.1`. The package is suitable for public source release and isolated
installation testing. Production use should continue to treat all retrieved
content as untrusted and should not execute third-party/source-supplied code.
