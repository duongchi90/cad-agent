# PO model protection implementation plan

Status: executing (independent-review repairs; canonical adoption pending)
Base SHA: 4993a522e9739892e2653eed253d237b08c99a50
Completion Head SHA: not yet established
Approval: explicit Human directive, 2026-10-27, permanent PO model configuration protection.

Goal: preserve Luna/Medium and independently configure and verify Sol/High PO calls.
Architecture: one stateless maintenance command in scripts, a secret-free custom
agent template, and existing operating guidance. It uses the official App Server
configuration read and existing runtime records; it does not spawn agents or
introduce a transport, daemon, database, or production dependency.

- [ ] Test missing/correct/drifted settings, restart recheck, unsupported effective
  configuration and stale/wrong runtime evidence before implementing the guard.
- [ ] Repair only the authorized scalar settings and managed PO definition;
  preserve unrelated configuration, validate effective settings, then verify an
  exact fresh completed PO turn independently of the agent's answer.
- [ ] Add the preflight/runtime requirement to AGENTS and AI_OPERATING_MODEL and
  the existing guidance contract. Reuse a clean existing worktree; leave all
  production PR heads unchanged.
- [ ] Run focused tests, real isolated configuration/update simulations, one
  new bounded read-only PO call and canonical verification. Publish exact evidence.

Review repair: reject malformed/borrowed token evidence and already-correct
reparse paths. Replace compare-then-replace with same-handle exclusive Windows
custody and rollback, reusing file_integrity directory pinning. The bounded
Sol/high write-seam decision requires competing-process, writable-mapping,
racing-creation and partial-write controls. In-place repair remains non-atomic
under process interruption; no claim of automatic crash recovery is admitted.

Acceptance: configuration and runtime evidence are separate. A configured model,
role name, old session or AI self-report is insufficient. Failure holds only the
PO decision. Canonical persistence remains NOT_VERIFIED until merged and a fresh
repository-only session verifies this path. Native/private-data gates do not apply.
