# CAD Agent — Current Operational Handoff

Status: current operational handoff for SOL and Luna/Codex Desktop.

Updated: 2026-08-29 by Issue #295 Lean Rebaseline branch.

## 0. Mandatory session-start authority

Before any governance/runtime decision, fresh-read GitHub in this order:

1. Issue #131 standing comments:
   - `5396800691` — Local Solo Executor + five-SOL standing model;
   - `5419064061` — cross-chat persistence, long-horizon/lookahead and reuse invariants;
   - `5442771213` — `PRE_ISSUANCE_GATE_V1`;
   - `5443060158` — five-SOL writer eligibility and fail-closed writer lease.
2. Issue #131 historical ledger plus Issue #294 active successor ledger; reconstruct newest observed sequence, newest valid authority, exact terminal/consumption state, and current baton.
3. Current `main`, active Issue/PR, exact base/head/state, cumulative diff and CI/reuse evidence as relevant.
4. `docs/PROJECT.md`, `docs/ARCHITECTURE.md`, `docs/AI_OPERATING_MODEL.md`, and the active design/plan.

GitHub current state and the newest valid numbered authority beat stale SHA/baton/sequence claims in this document or chat memory.

## 1. Human / SOL / Luna operating invariants

- Authority order: `Human Owner > SOL_POOL > Luna / Codex Desktop`.
- Human Owner is final product/engineering authority and is not a routine relay hop.
- Exactly one Local Solo Executor exists: Luna / Codex Desktop.
- Five SOL roles stay active: CONTROL_GOVERNANCE, ARCHITECTURE_REUSE, INTEGRATION_CI, SECURITY_REDTEAM, EVIDENCE_ACCEPTANCE.
- All five SOLs are writer-eligible, but each target CONTROL_SEQ has exactly one valid writer lease. Other cells stay advisory `CONTROL_SEQ=NONE` for that sequence.
- `SOL_WRITER_CLAIM_V1`, lowest-valid-comment-ID arbitration, exact readback, anti-race proof, terminal single-consumption and `PRE_ISSUANCE_GATE_V1` remain mandatory.
- While Luna executes N, SOLs prepare N+1/N+2 to dependency limit and reuse accepted PASS evidence absent concrete drift.
- SOL/Web owns broad reasoning, architecture/reuse/security/root-cause/source-contract analysis, CI/evidence interpretation, acceptance, reconciliation, merge/publication decisions and successor issuance.
- Luna owns machine-local edit/test/build/commit/push and live AutoCAD/COM/ROT/File-IPC/.NET execution only when exact authority grants it.
- Within authorized scope Luna continues through the whole same-layer causal family: RED-first TDD, minimal GREEN, focused/nearest regressions, cleanup, normal commits/push and same-epoch follow-through. Do not micro-handoff on small same-layer helper/test-harness defects.
- Hard handoff occurs only at the standing architecture/scope expansion, security/trust ambiguity, new cross-layer defect, exhausted causal budget, unprovable cleanup/custody, Human-only action, mission acceptance/merge/publication, or superseding-authority boundaries.
- Before expensive/stateful/live/mutating work, prove controller/orchestration behavior offline/synthetically as far as technically possible.
- Local repo write authority never implies merge. No amend/rebase/squash/force-push unless separately authorized.
- `SKIP` / `NOT RUN` never count as PASS.

## 2. Active product roadmap after Lean Rebaseline

Issue #295 changes product priority only. It does not replace any operating invariant above.

Active product order:

1. **M0 — Stabilize the Pipe** — close the current control/execution routing and semantic-result boundary; keep one canonical AutoCAD request/result route and truthful hosted CI/reuse.
2. **M1 — Golden Path** — one approved disposable drawing through the existing engine, native editable candidate, AutoCAD Mechanical review and deterministic evidence.
3. **M2 — Benchmark** — small varied case set; generalize only from measured failure/bottleneck.
4. **M3 — Repair Loop** — bounded verifier→repair→fresh verification only after M1/M2 demonstrate repeatable need.
5. **M4 — Production Hardening** — private-data, production save/reopen/rollback, promotion/publication and stronger operational hardening only when disposable reliability justifies them.

Historical R*, P*, VS-T*, M*, S* labels and plans remain evidence/traceability. They are not an automatic daily queue. A historical slice becomes active only when a current milestone plus fresh Issue/valid authority identifies it as the smallest correct owner.

Every newly built capability under M0-M4 still follows the full established Human/SOL/Luna process: reuse-first, exact write-set, causal TDD, focused/nearest/hosted evidence, independent SOL acceptance, live/private boundaries, writer lease, pre-issuance and long-horizon mission semantics.

## 3. Architecture admission rule

Preserve the current execution engine:

```text
primitive_ir_lib
  -> semantic_ir_lib
  -> agent_lib
  -> dxf_builder_lib
  -> mcp_integration_lib
```

Before creating a new top-level contract, registry, state machine, authority store, transport, executor, publisher, or long-lived artifact type:

1. try the existing owner/API;
2. try a thin adapter/validator;
3. require a deterministic failing case, benchmark failure or measured bottleneck proving those are insufficient;
4. require the new abstraction to remove more complexity than it adds.

No second OCR engine, solver, DXF writer, AutoCAD transport/dispatcher, repair executor, manifest/revision truth store, verdict path, or publisher is authorized by the Lean Rebaseline.

## 4. Live control state

Do not cache a numbered CONTROL_SEQ or PR head in this handoff. The live state is reconstructed from #131 + #294 plus the active Issue/PR at session start.

At the time Issue #295 was opened, the active runtime lane was Issue #284 / PR #285 under successor ledger #294. That fact is historical context only; fresh-read GitHub before relying on it.

## 5. Historical handoff snapshot — 2026-08-06

The remainder of this document preserves the earlier operational snapshot as historical evidence. It no longer defines the current daily product queue.

### Historical accepted implementation state

- Repository: `duongchi90/cad-agent`.
- Latest accepted implementation merge recorded by this snapshot:
  `a9968480258e01fda9d4dfbf01a27958b67747bc`.
- Latest merged PR recorded by this snapshot: #65 — S3B exact-base Xref inspection and approved extraction.
- Previous accepted implementation merges:
  - `365cb2df47cc3d0232a4b5df1901f55dbe46b22c` — PR #61 S2C actual read-only AutoCAD-native layout capture;
  - `ff6d199ef6cd401ccf5d06bace1135e4e55f1216` — PR #59 R1B;
  - `589d708a69f5c710c0a4c25e52a5b17db9749764` — PR #57 R1A;
  - `a8a962281b2d7480c9444eb8e1b56c6795c108aa` — PR #54 S3A.
- Runtime promotion in that snapshot: no source-fusion, repair, verdict, or publication runtime was promoted.

The accepted S2C implementation head recorded by that snapshot was `365cb2df47cc3d0232a4b5df1901f55dbe46b22c`. Later docs-only commits were not implementation bases.

### Historical accepted S2B boundary

S2B provided the closed `native_render_evidence` File IPC request/result contract, Python client adapter, C# validator, and dispatcher registration. The accepted seam returned `NATIVE_RENDER_NOT_IMPLEMENTED` before drawing access. Its mandatory .NET gate passed with 113 C# tests and hosted sequential integration passed. AutoCAD Mechanical live/native capture remained `NOT RUN`.

S2C could replace only that unsupported dispatcher path through the existing drawing gateway. It could not add a second transport, queue, dispatcher, protocol, renderer fallback, verdict, approval, repair, or publication path.

### Historical accepted S2C — Issue #60

S2C was accepted at merge commit `365cb2df47cc3d0232a4b5df1901f55dbe46b22c` (PR #61) for the bounded read-only AutoCAD-native layout capture scope.

Historical implementation branch: `task/s2c-autocad-native-render`.

Exact implementation base: `3d0aa999904f384efa4eb42a81637e4270591859`.

Approved design: `docs/superpowers/specs/2026-08-05-autocad-native-render-s2c-design.md`.

Approved implementation plan: `docs/superpowers/plans/2026-08-05-autocad-native-render-s2c.md`.

The branch was prepared with design commit `091f189bacf21f4d67c228672ff0137ac0af8f84` and plan head `2febca49526f560cd0daaa631aecc262936e8695`. Those commits were preparation only; the accepted implementation was the S2C merge recorded above.

Locked S2C profile recorded by the snapshot: named paper-space layout only; A4; white background; 300 DPI; fit-to-paper enabled; `monochrome.ctb`; PNG or one-page PDF; fixed approved PDF and PNG PC3 devices on AutoCAD Mechanical 2027; no device/media/style fallback.

Locked artifact boundary:

```text
<CAD_AGENT_DOTNET_IPC_DIR>/native-render/<request_id>/artifact.png
<CAD_AGENT_DOTNET_IPC_DIR>/native-render/<request_id>/artifact.pdf
```

`artifact.relative_path` was relative to the IPC root. No request output path or `artifact_directory` field was permitted. Request ownership, safe canonical containment, exclusive collision handling, temporary byte validation, and no-overwrite atomic publication were mandatory.

Success required unchanged DBMOD, unchanged on-disk DWG SHA-256, restored session state/current layout, `changed=false`, and `entity_handles=[]`. Failed restoration or any invariant produced a failure with `payload={}` and no final artifact publication.

### Historical accepted S3B boundary

S3B was accepted on PR #65 and merge `a9968480258e01fda9d4dfbf01a27958b67747bc` for exact-base Xref inspection and approved extraction. The accepted boundary was:

- source Xrefs and accepted DWGs read-only and immutable;
- inspection server-built and extraction with fresh live preflight immediately before mutation;
- extraction only into new disposable candidates;
- allowed local transforms: translation, rotation, positive uniform scale only;
- evidence preserving source handle, layer, block, source revision, source hash and `REUSED_FROM_BASE_CAD` provenance;
- AutoCAD Mechanical live acceptance `NOT RUN`;
- private drawing/source-data acceptance `NOT RUN`.

Runtime verification head: `9f5dc302643fdfae77cbda65dd6cdc0c8deccc59`.
Record-only final head: `67c3496da313245fc9ceeee26814e099b32f2c87`.

### Historical locked work

The 2026-08-06 snapshot kept S3C repair/publication, R1C source fusion, registry, dimension-authority expansion, candidate revision orchestration, repair-loop integration, visual verdict/publication and duplicate engines/transport/truth stores locked. Those labels remain historical evidence; current activation now follows M0-M4 plus fresh Issue/authority.

### Historical accelerated reuse-first planning record

Issue #68 / PR #69 and these documents remain historical planning evidence:

- `docs/superpowers/specs/2026-08-06-accelerated-reuse-first-program-design.md`;
- `docs/superpowers/plans/2026-08-06-accelerated-reuse-first-program.md`.

Their P0-P10 / wave structure is not the active daily product queue after the owner-approved Lean Rebaseline. Their accepted evidence and reuse decisions remain reusable where a current milestone needs them.
