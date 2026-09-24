# Luna Session Portable Runbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the approved Luna session workflow discoverable and safely reproducible from a fresh Windows checkout, with no automatic AutoCAD action or duplicate execution owner.

**Architecture:** Add one tracked runbook, one resume-state template, and a thin `scripts/luna-session.ps1` validator/command planner. It composes the existing bootstrap, verification, .NET solution, LSP dispatcher, `CADAGENT_DISPATCH`, Git/GitHub evidence, and #305 resume contract; it does not load AutoCAD or mutate drawings.

**Tech Stack:** Windows PowerShell, Python 3.11/pytest contract tests, Git, the existing .NET solution, and existing repository scripts.

**Spec:** `docs/superpowers/specs/2026-09-24-luna-session-portable-runbook-design.md`

**Status:** Executing

**Approval date:** 2026-09-24

**Base SHA:** `7523ac3641bcd2592ff9c3f7348ab29aba23dbec`

**Completion Head SHA:** Not recorded until the final implementation/evidence commit exists.

**Verification command:** `scripts/verify.ps1`

**Verification result:** Not recorded until execution completes.

**Required private/live gates:** `real_data` not affected; AutoCAD Mechanical live action is out of scope and will be `NOT RUN`. The authoritative verifier's unavailable-state probe remains `SKIP` if AutoCAD prerequisites are absent.

## Global Constraints

- Supported product boundary remains Windows, Python 3.11, AutoCAD Mechanical 2027, and Tesseract 5.4.0.20240606.
- Use existing `scripts/bootstrap.ps1`, `scripts/verify.ps1`, `autocad_plugin/CadAgent.AutoCAD2027.sln`, `mcp_dispatch.lsp`, `CADAGENT_DISPATCH`, and GitHub evidence owners.
- `Packet` must rebuild the clean exact current source head and hash the resulting DLL in the same invocation; fail closed if source-to-DLL provenance cannot be proven.
- Preserve #305's canonical twelve minimum resume fields; coordination labels never substitute for those fields, fresh GitHub/Git evidence, or a current verdict.
- Do not duplicate pytest selections, add dependencies, persist machine-specific values, or introduce a transport, dispatcher, authority, store, or control plane.
- Never automate `NETLOAD`, `APPLOAD`, AutoCAD UI/process control, or any drawing mutation. Print the manual packet only.
- Do not trust or delete pre-existing DLL/DWG/temp artifacts. Cleanup of old temporary directories is outside scope.
- Keep PR453 open/draft; do not merge, promote, or modify accepted/source drawings or frozen PR447.

## Review Focus

- Dirty or changing Git state during build/packet creation must fail closed before printing a load packet.
- A pre-existing DLL at the expected path must not be accepted without a same-invocation clean build and SHA-256 binding.
- Resume JSON with a missing canonical field, blank, or obvious placeholder must be rejected; coordination-only labels cannot make it valid.
- Machine-specific paths, credentials, conversation/session IDs, HWNDs, and PIDs must not be required or committed.
- Missing tools and unavailable AutoCAD must be reported truthfully without launching or controlling AutoCAD.

---

### Task 1: Track the runbook and canonical resume template

**Files:**
- Create: `docs/LUNA_SESSION_RUNBOOK.md`
- Create: `docs/templates/luna-resume-state.json`
- Modify: `AGENTS.md`
- Test: `tests/test_luna_session_contract.py`

**Interfaces:**
- Consumes: the approved portable-runbook spec and current #305 minimum context.
- Produces: a discoverable operator runbook and a blank JSON template containing exactly the canonical minimum fields; no current machine/runtime values.

The resume template's exact field names are: `GOAL`, `CURRENT_MAIN`, `CURRENT_HEAD`, `ACTIVE_PR`, `DONE`, `ACCEPTED_EVIDENCE_REFS`, `FIRST_UNSATISFIED_BOUNDARY`, `CURRENT_RISK`, `ACTIVE_WRITESET`, `LIVE_LOCK_STATE`, `UNACKED_CURRENT_ADVISORIES`, and `NEXT_ACTION`.

- [x] **Step 1: Write failing documentation-contract tests**

Add tests that assert the runbook links the canonical documents and authoritative scripts, states the manual-only load sequence and safety limits, and that the template contains the exact #305 twelve-field minimum with placeholder values that are not treated as valid resume evidence. Assert `AGENTS.md` routes operators to the runbook.

- [x] **Step 2: Run the focused test and confirm the expected failure**

Run: `.\.venv-py311\Scripts\python.exe -m pytest tests/test_luna_session_contract.py -q -p no:cacheprovider`

Expected: FAIL because the runbook/template/tests have not yet been added; no import or environment error.

- [x] **Step 3: Add only the runbook, template, and route**

Use `docs/LUNA_SESSION_RUNBOOK.md` as the stable entry point. Document Start/Doctor/BuildPlugin/Packet/ValidateResume, repository-relative path derivation, current-state re-reads, manual NETLOAD/APPLOAD/health sequence, and truthful `BLOCKER`/`SKIP`/`NOT RUN` states. Include only blank/obvious-placeholder values in the resume template. Add one concise canonical-source pointer in `AGENTS.md`.

- [x] **Step 4: Run the focused documentation tests**

Run: `.\.venv-py311\Scripts\python.exe -m pytest tests/test_luna_session_contract.py -q -p no:cacheprovider`

Expected: PASS; all assertions exercise tracked documentation/template content only.

- [x] **Step 5: Commit Task 1**

Commit message: `docs: add portable Luna session runbook`

### Task 2: Implement the thin PowerShell session validator

**Files:**
- Create: `scripts/luna-session.ps1`
- Modify: `tests/test_luna_session_contract.py`

**Interfaces:**
- Consumes: Task 1 runbook/template and existing bootstrap/build/verification owners.
- Produces: `Start`, `Doctor`, `BuildPlugin`, `Packet`, and `ValidateResume -ResumeState <path>` actions; unknown actions and unmet prerequisites fail closed.

- [x] **Step 1: Add RED tests for each action boundary**

Cover these behaviors with PowerShell subprocess tests using a temporary fixture repository and a fake `dotnet` executable where needed:

```text
Start reports repository identity, cleanliness, and fresh remote-main lookup without treating cached refs as fresh.
Doctor reports missing prerequisites and never launches AutoCAD.
BuildPlugin refuses dirty source before invoking dotnet.
Packet invokes the existing Release|x64 solution build in the same call, rechecks unchanged clean HEAD/tree, and prints the derived DLL path plus the SHA-256 of the bytes produced by that build.
Packet fails closed on a stale/dirty head, absent build output, or build failure.
ValidateResume accepts all canonical fields and rejects missing, blank, placeholder, malformed, or coordination-only state.
Unknown actions fail closed; the script never invokes NETLOAD, APPLOAD, AutoCAD, or CADAGENT_HEALTH.
```

- [x] **Step 2: Run the focused test and confirm expected failures**

Run: `.\.venv-py311\Scripts\python.exe -m pytest tests/test_luna_session_contract.py -q -p no:cacheprovider`

Expected: FAIL on missing `scripts/luna-session.ps1` or its specified behavior, not on PowerShell discovery or fixture setup.

- [x] **Step 3: Implement the minimum script**

Derive the repository root from `$PSScriptRoot`; use existing `git`, `dotnet`, Python launcher, and Tesseract discovery. For `Packet`, capture exact clean HEAD/tree, invoke `dotnet clean` and `dotnet build` on the existing solution with `-c Release -p:Platform=x64`, then recheck clean HEAD/tree and hash the derived DLL before printing the manual packet. Read the canonical field names from the tracked resume template rather than creating a second field list. Do not write persistent state or invoke AutoCAD.

- [x] **Step 4: Run the focused tests and confirm GREEN**

Run: `.\.venv-py311\Scripts\python.exe -m pytest tests/test_luna_session_contract.py -q -p no:cacheprovider`

Expected: PASS, including the causal dirty/stale/provenance refusal cases.

- [x] **Step 5: Commit Task 2**

Commit message: `feat: add safe Luna session validation commands`

### Task 3: Verify the final exact head and record truthful gates

**Files:**
- Modify: this plan's status/evidence fields only after verification.
- Verify: `scripts/luna-session.ps1`, the runbook/template, tests, and exact PR453 diff.

**Interfaces:**
- Consumes: Tasks 1-2 and the unchanged approved spec.
- Produces: one verified, reviewable exact head; no live AutoCAD action or promotion.

- [x] **Step 1: Run the focused neighboring contract checks**

Run: `.\.venv-py311\Scripts\python.exe -m pytest tests/test_luna_session_contract.py tests/test_documentation_contract.py tests/test_reuse_declaration.py -q -p no:cacheprovider`

Expected: exit `0`; no failures.

- [x] **Step 2: Run the authoritative verifier**

Run: `.\scripts\verify.ps1`

Expected: exit `0` and `All checks passed!`; report each unavailable private/live gate exactly as `SKIP` or `NOT RUN`, never as PASS.

- [x] **Step 3: Check the write set and whitespace**

Run: `git diff --check 7523ac3641bcd2592ff9c3f7348ab29aba23dbec...HEAD` and `git status --short`.

Expected: exit `0`; only the allowlisted implementation/runbook paths, this plan, and the truthful `docs/STATUS.md` verification note are changed, and no generated/private artifact is tracked.

- [ ] **Step 4: Record verification evidence and commit the evidence checkpoint**

Record the implementation head, exact verification result, and private/live states in this plan and `docs/STATUS.md`. Keep the final plan-only lifecycle-closing commit separate, after the exact-head review verdicts.

- [ ] **Step 5: Request exact-head reviews and checkpoint PR453**

After fresh-reading main/#409/PR453/local state, submit the implementation head for required independent Security Redteam and Integration CI review if the changed head crosses their material runtime/safety boundary. Record the exact-head verdicts once each. Keep PR453 draft/unmerged and make no AutoCAD/live-write attempt in this plan.

## Reuse Declaration

- Existing capability inspected: bootstrap/environment validation, canonical verifier, AutoCAD .NET solution/build, LSP dispatcher, `CADAGENT_DISPATCH`, GitHub checkpoint/resume, and existing #305 context.
- Existing API reused: those owners above; no new execution or evidence owner.
- Adapter required: one local PowerShell validator/command planner.
- New capability genuinely missing: a tracked portable session runbook and fail-closed local validator to derive paths and bind a just-built DLL to a clean exact source head.
- Exact write set: `AGENTS.md`, `docs/LUNA_SESSION_RUNBOOK.md`, `docs/templates/luna-resume-state.json`, `docs/superpowers/plans/2026-09-24-luna-session-portable-runbook.md`, `scripts/luna-session.ps1`, and `tests/test_luna_session_contract.py`.
- Forbidden duplication: second bootstrap/verifier/test selector, AutoCAD loader/UI driver, dispatcher, transport, resume store, provenance store, token/issuer/registry/approval authority, or control plane.
- Compatibility: existing bootstrap, verify, .NET solution, LSP dispatch, and CAD Agent interfaces remain unchanged.
- Migration/rollback: no persisted data migration; revert the bounded PR commits if declined. No machine-specific state is persisted.
- Actual tracked write set: `AGENTS.md`, `docs/LUNA_SESSION_RUNBOOK.md`, `docs/STATUS.md` (one verification-evidence entry), `docs/templates/luna-resume-state.json`, this plan, `scripts/luna-session.ps1`, and `tests/test_luna_session_contract.py`.
