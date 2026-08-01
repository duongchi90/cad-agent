# Task Card T08 — AutoCAD Live Smoke and Final Review

**Role:** Coder/Reviewer  
**Model:** Luna Extra High (`gpt-5.6-luna`, reasoning `xhigh`)  
**Base:** The exact SHA of `integration/autocad-dotnet-option-a` after PO integrates T07  
**Branch:** `codex/autocad-dotnet-t08-live-review`  
**Worktree:** `D:\cad-agent-master\cad-agent\.worktrees\autocad-dotnet-t08-live-review`

## Objective

Run the smallest real AutoCAD Mechanical 2027 smoke test and record evidence without changing source or status ledger.

## Allowed files

- `docs/reviews/2026-08-01-autocad-dotnet-live-review.md` only if a review record is needed.

## Forbidden files

All source, solution/project configuration, contracts, scripts, `docs/STATUS.md`, existing dispatcher code, production drawings, and private artifacts.

## Required live sequence

1. Build artifact must already come from the PO-approved T07 integration commit.
2. Open AutoCAD Mechanical 2027 and use manual `NETLOAD`; do not add automatic loading.
3. Run `CADAGENT_HEALTH` and verify plugin version, active document path, and IPC path.
4. Open a disposable DXF under `C:\temp`, run review for a known handle, and verify the result is read-only.
5. Run `CADAGENT_CLOSE_DISPOSABLE`; verify the disposable document closes without save.
6. Record exactly `PASS`, `SKIP`, or `NOT RUN`, with prerequisite and evidence paths. A failed live check is not converted to pass.

## Completion report

Return live status, AutoCAD version/session evidence, disposable file paths, command results, whether any save occurred, review findings, and commit SHA if a review record was created. Do not merge; the PO owns final `docs/STATUS.md` update and integration decision.
