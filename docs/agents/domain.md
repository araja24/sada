# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root.
- **`docs/adr/`**: read ADRs that touch the area you're about to work in.

This is a **single-context** repo: one `CONTEXT.md` at the root, no `CONTEXT-MAP.md`.

If `docs/adr/` doesn't exist yet, proceed silently — it's created lazily by `/domain-modeling` when the first decision actually needs recording.

## File structure

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-....md
│   └── 0002-....md
└── analysis/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (...), but worth reopening because…_
