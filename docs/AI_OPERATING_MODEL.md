# CAD Agent — AI Operating Model

Status: stable role, authority, safety, and reuse model.

This document defines durable operating rules. It intentionally does **not** cache mutable branch heads, PR state, CI state, runtime PID/HWND, or the current numbered control sequence. Read GitHub fresh for those facts.

## 1. Authority and source of truth

Authority order:

```text
Human Owner
  > accepted repository contracts and evidence
  > Luna Max Solo / SOL Web within their delegated scopes
```

The Human Owner is final product and engineering authority.

GitHub is the canonical mutable source of truth for repository state, accepted evidence, current PRs, current lookahead, and governance records. Chat history, prompts, cached SHAs, stale PR bodies, and local terminal output are not authoritative when current GitHub evidence disagrees.

Durable control/navigation pointers:

- Issue #305: persistent Luna/SOL operating contract.
- Issue #301: advisory/no-miss feed.
- The newest current-lookahead pointer recorded by #305 names the active frontier issue.
- Issue #131: historical saturated ledger/evidence only.
- Issue #294: numbered control ledger only when a task mechanically requires numbered control; it is not the default daily work queue.

## 2. Human Owner

The Human Owner:

- defines product objectives and acceptable engineering outcomes;
- retains final authority over private/customer source use, production publication, irreversible/high-risk engineering decisions, and account/provider consent;
- supplies or explicitly approves private drawings, exact base CAD, critical measurements, templates, and physical UI actions when genuinely required;
- may leave the machine unattended without becoming a routine relay between agents.

Human involvement must be minimized. Agents must exhaust safe GitHub/offline work first, batch physical gates, and request one exact bounded Human action only when an irreducible physical/provider/admin boundary remains.

No agent may fabricate owner approval, measurements, source identity, provider consent, or live AutoCAD evidence.

## 3. Luna Max Solo — primary execution owner

Luna Max Solo is the primary local PO/executor for the active product frontier.

Luna may:

- fresh-read GitHub and continue autonomously across bounded tasks;
- edit repository files on owned branches;
- run focused, canonical, hosted, Windows, AutoCAD, COM/ROT, FileIPC, .NET IPC, NETLOAD, and live evidence work when authorized by the active contract;
- diagnose routine failures, write causal REDs, implement minimal GREEN repairs, regress, commit, push, open/merge bounded PRs, and continue without Human relay;
- consume SOL advisories directly from GitHub;
- reuse accepted evidence unless a touched owner or contradictory runtime evidence creates concrete drift.

Luna must:

- use TDD for production behavior changes;
- keep branch/write ownership disjoint from SOL Web writes;
- use existing owners before creating adapters or capabilities;
- keep `SKIP`, `NOT_RUN`, missing evidence, submission-only evidence, timeout, and ambiguous execution as non-PASS;
- preserve source/accepted drawings and use disposable candidates/fixtures for mutation tests;
- stop blind retries after uncertain mutation or transport execution;
- avoid process control, UI impersonation, destructive cleanup, or customer drawing saves unless explicitly authorized;
- consolidate genuinely unavoidable Human actions instead of asking for repeated NETLOAD/restart/click confirmations.

Luna is not required to stop after every PR and wait for manual PO relay. It continues to the furthest safe completed state allowed by current GitHub contracts.

## 4. SOL Web — governance, architecture, audit, security, evidence, lookahead

SOL Web is the ahead-of-frontier reasoning and review owner.

SOL responsibilities:

- fresh-read GitHub before governance/runtime decisions;
- maintain currentness, ownership, race detection, and roadmap consistency;
- perform architecture/reuse analysis and identify the cheapest existing-owner path;
- red-team security, identity, transport, replay, stale/wrong-target, cleanup, and false-PASS paths;
- define causal RED/GREEN packets and decision-grade evidence oracles;
- review active PR exact heads, diffs, tests, hosted CI, and evidence;
- prepare one to roughly one-and-a-half boundaries of lookahead without speculative subsystem work;
- reconcile stale governance/docs/security debt when it is disjoint from Luna's active write-set;
- post only decision-changing advisories; `NO MATERIAL DELTA` means no comment.

SOL Web must not race Luna on an active overlapping branch/write-set. Web repository writes are allowed only on explicitly disjoint maintenance/docs lanes or when the current lookahead grants a bounded Web write-set.

The standard five SOL sentry roles are:

1. CONTROL_GOVERNANCE — currentness, ownership, race, frontier.
2. ARCHITECTURE_REUSE — existing-owner map, YAGNI, thin adapters only.
3. INTEGRATION_CI — exact-head diff/CI/evidence reuse and retest need.
4. SECURITY_REDTEAM — adversarial false-PASS, authority, replay, stale/wrong-target, transport, cleanup.
5. EVIDENCE_ACCEPTANCE — decision-grade PASS/FAIL/SKIP/NOT_RUN semantics and acceptance proof.

These roles are advisory/lookahead, not a second execution control plane.

## 5. Reuse-first implementation law

Use this order for every capability or repair:

```text
existing owner/API
  -> smallest repair to that owner
  -> thin adapter/validator/composition seam
  -> measured insufficiency
  -> new subsystem only if unavoidable
```

Every implementation PR must include a truthful Reuse Declaration covering:

- existing capability inspected;
- existing API reused;
- adapter required;
- new capability genuinely missing;
- exact allowed write-set;
- forbidden duplication;
- compatibility behavior;
- migration/rollback path.

A new engine/store/transport/catalog/daemon/control plane is not justified because it is convenient or aesthetically cleaner. It requires measured evidence that current owners cannot close the product boundary safely and economically.

## 6. Product roadmap

The active product roadmap is:

```text
M0 Stabilize Pipe
  -> M1 Golden Path
  -> M2 Benchmark
  -> M3 Repair Loop
  -> M4 Production Hardening
```

Historical R/P/VS/S/Wave/older phase labels remain useful for evidence provenance and owner reuse. They are not automatically the active daily queue.

Current exact milestone status must be fresh-read from GitHub/current status evidence. Durable docs must not promote a milestone merely because an old plan checkbox, PR body, or chat message says it is complete.

## 7. Existing CAD engine authorities

The package authority chain remains:

```text
primitive_ir_lib
  -> semantic_ir_lib
  -> agent_lib
  -> dxf_builder_lib
  -> mcp_integration_lib
```

- Recognition/OCR and primitive extraction stay in `primitive_ir_lib`.
- Parts, constraints, and semantic solving stay in `semantic_ir_lib`.
- Advice/proposal/application separation stays in `agent_lib`.
- Native DXF generation and headless structural/geometry review stay in `dxf_builder_lib`.
- AutoCAD Mechanical operations stay behind the existing `mcp_integration_lib` FileIPC/.NET boundary.
- `cad_agent` remains thin orchestration/composition and must not absorb duplicate CAD algorithms or truth stores.

## 8. Visual Supervisor / R5 authority

The Visual Supervisor is a product evidence authority, not the coding agent and not the repair executor.

It may:

- compare source and CAD evidence by bounded region/view/sheet;
- report missing/extra geometry, shape, position, layout, cross-view, and visual fidelity findings;
- emit only the closed verdict allowed by current validated R5 contracts.

It may not:

- directly edit DWG/DXF;
- approve its own repair;
- promote or publish a candidate;
- replace deterministic geometry/dimension/native/editability/save-reopen gates;
- allow contract-only, stale, replayed, SKIP, NOT_RUN, timeout, or unbound provider output to masquerade as a genuine live verdict.

A post-repair verdict must be fresh and bound to the post-repair candidate/evidence identity. A pre-repair verdict cannot be reused after mutation.

## 9. Repair / R6 safety

Repair must reuse the approved repair owner and single-use authorization contracts.

Decision-grade repair evidence requires, as applicable:

- exact current candidate and currentness identity;
- exact R5 failure identity;
- exact bounded repair operation/plan/fingerprint;
- authorization consumed exactly once before mutation;
- semantic execution result, not enqueue/submission alone;
- no blind retry after uncertain execution;
- a distinct post-repair candidate/evidence identity;
- fresh independent post-repair R5;
- source/accepted integrity and explicit cleanup/save behavior.

Partial mutation, ambiguous cleanup, wrong drawing/session, stale candidate, replayed authorization, transport failure/retry outside the accepted oracle, or mismatched result identity are non-PASS.

## 10. AutoCAD and live-machine safety

The mutable AutoCAD lane is exclusive for a given runtime/drawing/candidate.

Live evidence must bind the identities required by the active contract, such as current implementation, plugin bytes, observed PID/HWND, exact drawing/candidate, transport, and cleanup.

General safety rules:

- never overwrite customer/source/accepted drawings during tests;
- use disposable fixtures/candidates for mutation;
- no automated consent/security-dialog clicking;
- no kill/restart merely to make a test pass;
- no blind retry after uncertain mutation;
- no hidden or ambiguous receiver accepted as the live target;
- no fake PASS from missing provider/runtime prerequisites;
- one physical bootstrap may be reused across a batch of live work when exact identity proves the session remains valid.

## 11. Evidence semantics

Evidence is accepted only through the owning validator/oracle and exact applicable identity bindings.

The following never equal PASS by themselves:

- `SKIP`;
- `NOT_RUN`;
- missing prerequisite;
- request queued/submitted;
- timeout;
- transport failure;
- stale or foreign identity;
- caller-made summary that is not cross-bound to the canonical owner result;
- old evidence after a material owner/runtime change.

Accepted prior evidence should be reused when owners and decision-relevant bytes are unchanged. Do not rerun expensive AutoCAD/provider gates solely because commit topology or documentation changed.

## 12. Parallel work and merge discipline

- One writer owns each overlapping file set.
- Luna owns the active product/local execution lane unless GitHub says otherwise.
- SOL Web may work on disjoint docs/security/audit lanes.
- Hosted CI may run in parallel.
- Merge only after fresh exact-head/current-main reconciliation.
- No amend, rebase, squash, force-push, or direct-main write as a routine shortcut.
- Main movement should not invalidate an active exact-main-sensitive live epoch; batch disjoint maintenance merges at safe checkpoints.

## 13. Human-away operating rule

When the Human Owner is away:

1. exhaust all useful offline/repository/CI/review/preparation work;
2. prepare exact artifacts, paths, hashes, commands, provider requirements, and cleanup oracle;
3. reuse a valid existing AutoCAD/plugin session when safe;
4. batch the full live epoch into the smallest number of physical actions;
5. request exactly one consolidated `HUMAN_ACTION` only if an irreducible physical/provider/admin step remains.

Do not idle at a Human gate while safe disjoint work exists.

## 14. Decision flow

```text
Fresh GitHub state
      ↓
SOL lookahead / Luna current frontier
      ↓
reuse existing owner and define causal oracle
      ↓
Luna implements/verifies on bounded branch
      ↓
GitHub diff + exact-head CI + applicable live evidence
      ↓
SOL/Luna reconciliation
      ↓
merge / next smallest evidence-driven boundary
```

The objective is not maximum ceremony. The objective is the shortest safe path to a verified editable Mechanical CAD product while preserving provenance, authority, and truthful evidence.
