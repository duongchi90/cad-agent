# Current Operating Docs Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile canonical operating documentation with the accepted Luna Max Solo + five-SOL model and the current M0→M4 product roadmap without changing runtime behavior.

**Architecture:** Treat GitHub fresh state as mutable authority and keep durable docs limited to stable operating rules and navigation. Replace stale PO/Codex-era handoff state with pointers to #305, #301, and the current lookahead issue; preserve reuse-first package ownership and evidence semantics.

**Tech Stack:** Markdown documentation and existing repository documentation tests only.

**Spec:** GitHub Issue #313.

## Global Constraints

- Documentation only; no runtime/workflow/schema/dependency/AutoCAD behavior changes.
- Human Owner remains final authority.
- #305 is the persistent Luna/SOL operating contract; #301 is the advisory/no-miss feed; the newest #305 lookahead pointer names the current frontier issue.
- #131 is historical; #294 is used only when a task mechanically requires numbered control.
- Product roadmap is M0 Stabilize Pipe -> M1 Golden Path -> M2 Benchmark -> M3 Repair Loop -> M4 Production Hardening.
- Historical R/P/VS/older phase labels remain evidence/reuse vocabulary, not the automatic daily queue.
- Reuse order: existing owner -> smallest repair -> thin adapter -> measured failure -> new subsystem only if unavoidable.
- Human is not a routine relay hop.
- SKIP, NOT_RUN, missing, submission, timeout, or stale evidence are non-PASS unless the owning contract explicitly says otherwise.

---

### Task 1: Reconcile AI operating model

**Files:**
- Modify: `docs/AI_OPERATING_MODEL.md`

**Interfaces:**
- Consumes: Issue #313, persistent contract #305, advisory #301, current lookahead pointer, existing package authority map.
- Produces: one stable role/authority document that does not cache mutable SHAs/PR heads.

- [x] **Step 1: Identify stale role semantics**

Record that the old document describes ChatGPT as sequential PO and Codex as a one-task worker that waits after every PR, which conflicts with current Luna Max Solo autonomous execution.

- [x] **Step 2: Replace with current durable model**

Document Human Owner > Luna/SOL collaboration; Luna as primary local PO/executor; SOL Web as governance/architecture/audit/security/evidence/lookahead; GitHub as canonical mutable state; Human relay minimization; exact live safety locks; reuse-first architecture.

- [x] **Step 3: Preserve product subsystem authorities**

Keep Visual Supervisor independence and the package chain `primitive_ir_lib -> semantic_ir_lib -> agent_lib -> dxf_builder_lib -> mcp_integration_lib` with `cad_agent` as thin orchestration.

### Task 2: Replace stale current handoff

**Files:**
- Modify: `docs/HANDOFF.md`

**Interfaces:**
- Consumes: current main only as the branch base, not as a durable cached authority; Issue #313 navigation rules.
- Produces: a short navigation-first handoff that points agents to fresh GitHub state and names the current roadmap/frontier semantics.

- [x] **Step 1: Remove cached 2026-08-06 PR/SHA frontier**

Delete the stale S2C/S3B-era current-state narrative and replace it with durable pointers.

- [x] **Step 2: Record accepted roadmap state without mutable head caching**

State M0/M1/M2 accepted, M3 active until current GitHub evidence closes it, M4 subsequent; require fresh GitHub reads for exact current head/PR/CI.

- [x] **Step 3: Define Human-away behavior**

Require Luna/SOL to exhaust offline/GitHub work first, batch physical gates, and request one exact Human action only when irreducible.

### Task 3: Verify and review

**Files:**
- Test: `tests/test_documentation_contract.py`

**Interfaces:**
- Consumes: the two updated docs.
- Produces: hosted documentation/regression evidence on a non-draft PR.

- [ ] **Step 1: Run documentation contract**

Run: `python -m pytest tests/test_documentation_contract.py -q`
Expected: PASS.

- [ ] **Step 2: Run diff hygiene**

Run: `git diff --check`
Expected: PASS.

- [ ] **Step 3: Open non-draft PR and use hosted checks**

Require fresh PR-triggered tests/reuse checks before merge. No AutoCAD/provider/live rerun is required because the write-set is documentation only.
