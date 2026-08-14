# SOL / Luna Cross-Account Handoff Design

## Goal

Make the Human-approved responsibility split portable across ChatGPT accounts and future SOL sessions without relying on chat memory.

## Approved authority model

```text
Human Owner > SOL > Luna / Codex Desktop local executor
```

SOL is the primary repository/off-machine engineering owner. Luna is the machine-local execution owner.

## Design

1. Add `docs/SOL_HANDOFF.md` as the stable role/authority and cross-account bootstrap contract.
2. Update `docs/CHATGPT_PROJECT_INSTRUCTIONS.md` so a new ChatGPT account reads the SOL handoff first and adopts the current SOL role instead of the superseded PO-read-only split.
3. Keep mutable runtime status out of the stable handoff. New sessions must fresh-read GitHub for `main`, the active frontier, latest relevant `LUNA_STATE`, current PR heads, CI, and camera-stack state.
4. Keep Luna bounded to genuine Windows/AutoCAD/File-IPC/installed-SDK/private-machine work. Local defects return to SOL for repository RED-first repair.
5. Enforce one primary Luna executor, zero subagents by default, and at most one explicitly justified independent diagnostic subagent.
6. Because the active R8-D epoch pins exact `main`, stage the docs on a branch/draft PR and publish a pointer on Issue #131 rather than moving `main` immediately.

## Routing rule

```text
Can the task be completed truthfully from GitHub/repository/hosted or offline tools
without the Human Owner's live Windows/AutoCAD machine?

YES -> SOL
NO  -> Luna, for the smallest bounded local gate only
```

## Success criteria

- Another ChatGPT account can take over by locating `docs/SOL_HANDOFF.md` or its staged PR and fresh-reading GitHub.
- The account knows SOL owns GitHub/code/tests/review/security/merge work.
- The account knows Luna owns only genuine machine-local execution.
- The account does not treat old chat memory or stale SHAs as authority.
- The account does not spawn a Luna agent swarm.
- `main` remains unchanged while the R8-D pin is active.

## Non-goals

- No runtime behavior change.
- No repository architecture change.
- No merge of the camera stack.
- No AutoCAD execution.
- No attempt to cache current mutable R8-D state in the handoff.
