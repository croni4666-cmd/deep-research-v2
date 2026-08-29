# deep-research

Codex-compatible deep-research skill derived from deep-research-v2.

- Skill version: `2.1.1-codex.1`
- Source version: `2.1.0`
- Entry point: `SKILL.md`
- Optional deterministic helpers: `scripts/`

The workflow treats retrieved content as untrusted data, does not assume shell
isolation, and fails closed when an audit has no claims or evidence.

Development validation:

```powershell
python <skill-creator-dir>\scripts\quick_validate.py <skill-directory>
```
