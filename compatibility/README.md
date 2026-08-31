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

## What the checks establish

Repository tests build the complete MiniMax package, run its packaged runtime
classifier, and audit its packaged schema-v2 example. This proves that the
portable files and Python helpers work together; it does not prove that a
MiniMax product loaded them.

An end-to-end MiniMax claim requires a retained run record showing:

- the exact MiniMax product and model identifier, when exposed;
- confirmation from the session or operator that this Skill version was loaded;
- the search/open tools or MCP servers actually available;
- at least one inspected source and the final cited output.

`runtime_check.py` only classifies the supplied declaration. It performs no
runtime discovery or remote attestation. Do not describe raw HTTP calls or a
copy into a Codex Skills directory as a MiniMax integration test.
