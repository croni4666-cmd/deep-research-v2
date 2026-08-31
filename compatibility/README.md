# Runtime compatibility

Build a clean runtime bundle without repository-only evaluations or ground
truth:

```powershell
python scripts/package_skill.py --target minimax --output path/to/packages
python scripts/package_skill.py --target codex --output path/to/packages
```

Both targets use the same platform-neutral Skill content. The target name is
recorded in `PACKAGE.json` for deployment diagnostics; it does not change the
research rules.

For MiniMax Mini-Agent, place the generated `evidence-deep-research` directory
under the configured `skills_dir`, enable Skills, and configure search/open
tools or MCP for live research. For Mavis, verify that the particular session
actually indexes the Skill. If it cannot, use the protocol-only label described
in `references/runtime-compatibility.md`.
