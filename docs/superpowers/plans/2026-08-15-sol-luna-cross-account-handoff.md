# SOL / Luna Cross-Account Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan inline. Do not dispatch Luna or local AutoCAD agents for this docs-only task.

**Goal:** Make the Human-approved `SOL = repository/off-machine owner` and `Luna = machine-local executor` split discoverable and reusable from another ChatGPT account without relying on chat memory.

**Architecture:** Add one stable role/authority handoff document and align the ChatGPT bootstrap instructions to read it first. Keep mutable runtime state out of the contract and point new sessions to fresh GitHub reads. Stage everything on a docs-only branch/PR so the active R8-D exact-main epoch does not drift.

**Tech Stack:** Markdown, GitHub branch/PR/issues.

## Global Constraints

- Authority: `Human Owner > SOL > Luna / Codex Desktop local executor`.
- GitHub is canonical mutable truth.
- SOL owns all repository/off-machine engineering work by default.
- Luna owns only genuine local Windows/AutoCAD/File-IPC/installed-SDK/private-machine gates.
- Local AutoCAD policy: one primary Luna executor, zero subagents by default, at most one explicitly justified diagnostic subagent.
- No `main` merge while the active R8-D exact-main epoch remains pinned unless SOL explicitly re-epochs it.
- Do not cache mutable SHAs/status as authority in the handoff.

---

### Task 1: Canonical SOL/Luna handoff

**Files:**
- Create: `docs/SOL_HANDOFF.md`

**Interfaces:**
- Consumes: Human Owner role split and current repository governance conventions.
- Produces: stable cross-account authority, routing, bootstrap, camera/supervision orientation, and anti-stale rules.

- [x] Create `docs/SOL_HANDOFF.md` with explicit SOL/off-machine and Luna/machine-local ownership.
- [x] Include one-agent Luna policy and defect-routing STOP rule.
- [x] Include fresh-read session-start protocol and another-account bootstrap prompt.
- [x] Avoid mutable project status as cached truth.

### Task 2: Align ChatGPT bootstrap instructions

**Files:**
- Modify: `docs/CHATGPT_PROJECT_INSTRUCTIONS.md`

**Interfaces:**
- Consumes: `docs/SOL_HANDOFF.md`.
- Produces: a copy/paste ChatGPT Project instruction block that directs new accounts to the current SOL role rather than the superseded PO-read-only role.

- [x] Replace the stale PO-only bootstrap with SOL-first instructions.
- [x] Make `docs/SOL_HANDOFF.md` the first role/authority document read.
- [x] Preserve fresh GitHub verification and truthful PASS/FAIL/SKIP/NOT RUN rules.
- [x] Explicitly reserve Luna for machine-local gates.

### Task 3: Publish discoverability without drifting main

**Files:**
- GitHub PR and Issue #131 comment only.

**Interfaces:**
- Consumes: docs-only branch head.
- Produces: discoverable pointer for a new account even before the handoff document is merged to `main`.

- [ ] Open a docs-only draft PR to `main` with exact head and note that merge is intentionally deferred while R8-D pins `main`.
- [ ] Add a concise governance pointer to Issue #131 naming the PR and `docs/SOL_HANDOFF.md`.
- [ ] Fresh-read the PR/head and verify `main` did not move.

## Verification

- No repository runtime/code files changed.
- `main` remains unchanged.
- The new handoff contains no `TODO`/`TBD` placeholders.
- New-account instructions clearly route repo/off-machine work to SOL and machine-local work to Luna.
- GitHub pointer is sufficient to find the staged handoff while `main` remains pinned.
