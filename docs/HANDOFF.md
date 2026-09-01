# CAD Agent — Current Operational Handoff

Status: navigation-first current handoff. Exact mutable state must be read fresh from GitHub.

Updated: 2026-09-01.

This file intentionally does **not** cache current PR heads, CI runs, AutoCAD PID/HWND, plugin SHA, provider turn IDs, or numbered control sequence. Those values become stale quickly.

## 1. Read these first

For every new work session:

1. read Issue #305 for the persistent Luna/SOL operating contract and its newest current-lookahead pointer;
2. read Issue #301 for unconsumed decision-changing advisories/no-miss findings;
3. read the current lookahead issue named by #305;
4. read current `main`, active PRs, exact heads/diffs, and hosted CI;
5. read `docs/STATUS.md` and `docs/ARCHITECTURE.md` for durable evidence/architecture context;
6. use Issue #294 only when the active task mechanically requires numbered control;
7. treat Issue #131 as historical evidence, not the active daily ledger.

Prompt-carried or chat-memory state never overrides fresher GitHub evidence.

## 2. Operating ownership

```text
Human Owner
   │ final authority / genuine physical-provider-admin gates
   │
   ├── Luna Max Solo
   │    primary product PO/executor and local Windows/AutoCAD engine
   │
   └── SOL Web
        governance, architecture/reuse, integration/CI,
        security red-team, evidence/acceptance, lookahead
```

Luna and SOL communicate through GitHub. The Human Owner is not a routine relay hop.

Luna may continue autonomously across bounded work, causal RED/GREEN repair, tests, commits, PRs, live preparation, and safe local execution. SOL works ahead, reviews exact heads, closes false-PASS/evidence gaps, and handles disjoint maintenance/docs work without racing Luna's active write-set.

## 3. Product roadmap

The current product roadmap is:

```text
M0 Stabilize Pipe
  -> M1 Golden Path
  -> M2 Benchmark
  -> M3 Repair Loop
  -> M4 Production Hardening
```

As of this handoff update, M0/M1/M2 have accepted evidence and the product frontier is M3 until fresh GitHub evidence says otherwise. Do not use this sentence as an exact-state substitute: always fresh-read GitHub for whether M3 has moved or closed.

The current M3 sub-boundary is frozen at **`M3_REAL_PROVIDER = BLOCKED_BY_CREDIT_BALANCE_EXHAUSTED`**. PR #340 is still OPEN/DRAFT and unmerged at exact head `714620001e8dbc1c49adbb13b9af4d5821eb6a7d` on `codex/m3-task3-responses-provider`, based on `main` `e8386342d4a7bdab7ee12eb7b163f573e6b2df02`. Its single authorized `gpt-5.6-sol` attempt returned HTTP 429; no response identity, terminal completion, structured result, retry, or second provider call exists. The read-only account/limit inspection classified the failure as credit balance exhausted. This is non-PASS evidence. Do not call the provider, use billing/credentials, run M3 R5/R6 live CAD, rerun M2, or merge PR #340/#337 from this state.

Historical R/P/VS/S/Wave/older phase labels remain evidence and reuse vocabulary, not the automatic daily queue.

## 4. Current M3 semantics

M3 reuses the existing R4/R5/R6/R7 chain rather than building a new repair engine.

The intended first repair proof is a disposable candidate-only LINE epoch:

```text
exact current candidate
      ↓
genuine fresh R5 FAIL
      ↓
exact repair plan + single-use authorization
      ↓
exactly one approved repair attempt
      ↓
distinct POST_REPAIR candidate/evidence
      ↓
fresh independent R5 PASS|FAIL
      ↓
integrity + cleanup evidence
```

Contract-only composition evidence may prove wiring, validation, replay rejection, and candidate transition, but it does not equal genuine provider-backed/live acceptance.

The provider-backed live sequence is therefore stopped before any new CAD epoch:
offline/hosted adapter evidence remains reusable, but it cannot replace the
blocked real-provider boundary. Resume only after the account boundary is
resolved and a separately authorized fresh provider acceptance produces the
required provider identity, terminal completion, and validated structured
result.

For live acceptance, use only current canonical R5/R6 owner results and the current M3 record/oracle on `main`. `SKIP`, `NOT_RUN`, timeout, retry, ambiguous cleanup, stale identity, or caller-made summaries that are not bound to canonical owner results are non-PASS.

## 5. Reuse-first architecture

Always use this order:

```text
existing owner
  -> smallest repair
  -> thin adapter/validator/composition seam
  -> measured insufficiency
  -> new subsystem only if unavoidable
```

Current package authorities remain:

```text
primitive_ir_lib
  -> semantic_ir_lib
  -> agent_lib
  -> dxf_builder_lib
  -> mcp_integration_lib
```

`cad_agent` remains thin orchestration/composition. Do not create duplicate OCR, solver, DXF builder, AutoCAD transport, repair executor, truth store, retry daemon, telemetry/database, visual verdict path, publisher, or control plane without measured evidence that the current owner cannot close the boundary.

CADmind-style `observe_drawing` / `query_entities` work remains evidence-driven: do not build MECH-1 merely because it appears useful. Require a measured CAD-context/query bottleneck first.

## 6. Evidence reuse and retest

Accepted evidence is reused when the owning implementation and decision-relevant bytes have not changed.

Do not rerun expensive AutoCAD/provider gates solely because:

- documentation changed;
- commit topology changed while the relevant tree/artifact is equivalent;
- a disjoint security/docs PR merged;
- a previously accepted owner remains byte-identical and no contradictory runtime evidence exists.

Retest only when a touched owner, artifact identity, runtime contract, or new contradictory machine truth makes the old evidence non-applicable.

## 7. AutoCAD/live safety

For live work:

- bind the exact identities required by the active contract;
- mutate only disposable candidate/fixture drawings;
- never save over source/customer/accepted drawings during tests;
- no automated security/consent dialog clicking;
- no kill/restart merely to force progress;
- no blind retry after uncertain mutation/execution;
- no ambiguous/hidden receiver accepted as the target;
- cleanup/save state must be explicit evidence, not assumption.

A valid existing AutoCAD/plugin session may be reused across a batch when exact runtime/plugin/drawing identity proves it remains safe. A fresh NETLOAD/restart must not be demanded merely for reassurance.

## 8. Human-away mode

When the Human Owner is not at the machine:

1. continue every useful GitHub/offline/test/review/preparation task;
2. prepare exact DLL/artifact paths and hashes, provider requirements, runtime expectations, commands, record paths, and cleanup oracle;
3. batch live work into one session when safe;
4. do not ask for intermediate confirmations;
5. request one exact consolidated `HUMAN_ACTION` only when no safe non-Human work remains.

`HUMAN ACTION = NONE` is correct whenever the remaining work is still executable by Luna/SOL without physical/provider/admin consent.

## 9. Maintenance lanes

Disjoint maintenance may proceed while the product live lane is blocked, provided it does not move `main` during an exact-main-sensitive epoch.

Current maintenance principles:

- forward-port still-useful security/docs ideas onto fresh current main;
- close stale governance PRs rather than mass-rebasing them;
- keep Dependabot/CodeQL/SECURITY.md additive and separate from runtime owners;
- reconcile stale canonical docs through small current-main successors;
- prefer GitHub-native branch protection/rulesets over custom governance bots.

Main protection is a repository setting, not a reason to build another control subsystem.

## 10. Completion package

A meaningful Luna terminal should report:

- RESULT;
- DONE;
- exact evidence and current main/head/PR state;
- relevant milestone state;
- consumed advisory/ACK when applicable;
- FIRST UNSATISFIED BOUNDARY;
- NEXT work that can still proceed autonomously;
- exactly one HUMAN ACTION only if genuinely irreducible.

`NEXT=NONE` should mean no safe product, maintenance, review, or preparation work remains in the current delegated scope — not merely that one live mode is disabled.

## 11. Core rule

Keep the system moving toward a verified editable Mechanical CAD product, not toward more governance ceremony.

Fresh GitHub evidence wins. Reuse accepted owners and evidence. Fail closed. Minimize Human gates. Do not manufacture PASS.
