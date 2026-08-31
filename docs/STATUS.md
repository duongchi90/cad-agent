# CAD Agent Status

## Status vocabulary

- **Verified:** the named command ran successfully on the named commit and
  environment.
- **Partially verified:** deterministic coverage passed, but a required private
  data or AutoCAD Mechanical gate has not run on the same candidate.
- **Unverified:** no current reproducible evidence supports the claim.
- **NOT RUN:** the gate was intentionally not executed; this is never a pass.

## Supported release environment

- Windows
- Python 3.11
- AutoCAD Mechanical 2027
- Tesseract 5.4.0.20240606

## M3 Task3 two-phase official provider start — merged boundary

- State: **Merged; offline and isolated official-SDK START verified; live
  AutoCAD M3 epoch NOT RUN**. This boundary is START_ONLY. Resume/fork remain
  fail-closed and are outside this boundary.
- Merged implementation: PR #334 at `cac069c45ea44ae09bd1c2062476b0febb4a37cb`;
  its exact implementation head was `42bdf11e256c7b68018962fbcab9142e3798074c`,
  based on `main` `b06e533bbcbe7221e7c3ad9234e8497f9b422ec8`. PR #332 remains
  OPEN/DRAFT/evidence-only and is untouched.
- The canonical Task3 child now validates server-owned start custody first,
  calls the existing low-level official `openai-codex` 0.144.4
  `CodexClient.thread_start`, and only then creates the immutable worker
  binding from the provider-generated thread ID. No caller-selected or
  pre-bound provider thread ID is accepted.
- Provider observation is a reduced typed allowlist: generated thread ID,
  model/provider, cwd, approval policy/reviewer, effective sandbox, and
  instruction-source path/hash observations. Server-owned config hash,
  `experimental_api=false`, schema/hash/validator identity, and authority
  source IDs/roles remain request/custody fields and are not echoed as
  provider evidence.
- Instruction-source binding is fail-closed: canonical observed paths must
  remain inside the disposable runtime root, be regular non-reparse files,
  hash to their actual bytes, and match exactly one expected authority source.
  Missing, extra, duplicate-hash ambiguity, path escape, symlink/reparse, and
  hash drift are rejected. Provider `readOnly` is accepted only as a stricter
  effective policy than server maximum `DISPOSABLE_ONLY`; widening access,
  network, cwd, model, or approval is rejected.
- Focused Task3 suites passed `128` tests; the nearest full offline suite
  passed `3059` tests with `18` deselected and `72` subtests. The affected
  Task6 event suite passed `161` tests after a compatibility repair. The
  authoritative verifier is rerun on the final documentation head before
  release integration.
- Real isolated official SDK START/BIND passed with package `openai-codex`
  `0.144.4` in a fresh disposable CODEX_HOME and no copied credentials. The
  typed response supplied provider-generated thread identity, exact model and
  provider, `approvalPolicy=never`, reviewer `user`, canonical instruction
  source hash, and effective `readOnly`/no-network sandbox. The bind result
  used that same provider thread ID; `config_sha256` was absent from provider
  observation as required. No Task6/R5/R6/AutoCAD mutation was performed.
- Remaining boundary: one NEW disposable provider-backed M3 LINE epoch. The
  current machine has no running AutoCAD process or FileIPC/COM/ROT receiver,
  so no live runtime identity, candidate, R5/R6 mutation, Task6 pair, or
  close-without-save evidence can be produced now. M2 remains accepted and is
  not retested; MECH-1 remains **NOT JUSTIFIED**.

## Accelerated reuse-first program: PLANNING/GOVERNANCE ONLY

- Exact planning base: `d00b24e4853d2bfa6bd94873d3014e37575e2718`.
- Issue: #68.
- PR: #69; GitHub is the live source of its current state.
- Before merge, complete the PO review and merge gate for PR #69.
- After merge, verify fresh `main` at the program merge SHA, then create three
  separate Wave 1 Issues:
  - official vision handoff;
  - R1C source integrity/fusion;
  - S2C/S3B live readiness.
- No runtime capability is automatically opened by this program, its PR, or its
  merge.
- S3B AutoCAD live: **NOT RUN**.
- Hosted AutoCAD .NET: **NOT RUN**.
- All current future-runtime locks remain in force.

## Reuse Integration Rebaseline

- State: **Accepted for R0 governance/rebaseline scope**. Runtime work remains
  locked; this acceptance does not promote any future subsystem.
- R0-T6 documentation phase state before aggregate verification: **Executing**.
- Current Task 7 implementation base:
  `07a14ce3623024f2df848b2b88ff447980772492`.
- Implementation record:
  `docs/superpowers/implementation-records/2026-08-04-reuse-integration-rebaseline.md`.
- Full-verifier candidate SHA:
  `a373114c91edd02a6a4dd086b02b2a89433be964`.
- Final record-only SHA: recorded in the final PR and handoff after the
  record-only commit; the canonical verifier was not rerun on that commit.
- R0-T6 implementation base:
  `cac38a1cf558aee1245ae669bcc106bf3619b8e5`.
- Design merge:
  `4cc2c0f198484581f5781466e769441d4e7da669`.
- Machine-readable inventory:
  `docs/superpowers/reuse/2026-08-04-reuse-inventory.json`.
- Canonical audit:
  `docs/superpowers/reuse/2026-08-04-reuse-integration-audit.md`.
- Evidence available through R0-T5: the closed inventory contains 20
  capabilities; the legacy compatibility baseline covers 37 commands and
  historical v1 manifest defaults; the architecture ratchet contains 24
  explicitly accepted existing violations; R0-T5 focused tests passed `6` and
  its canonical verifier passed with offline `787` tests and dotnet IPC `38`
  tests on the reviewed candidate.
- Runtime changes: none in the design merge or this documentation task. No
  runtime capability is promoted.
- VS-T4/VS-T5 old rollout: **locked**. M2 Drawing Initialization remains
  authoritative.
- Private-data gate: **NOT RUN**.
- AutoCAD Mechanical live gate: **NOT RUN**.
- Codex SDK spike: **NOT RUN**.
- Unavailable-state `SKIP` results, when collected, are not acceptance evidence.
- R0 acceptance evidence: inventory checker exit `0`; architecture checker
  `PASS`; focused R0 suite `41 passed, 0 skipped`; canonical candidate offline
  JUnit `808/0/0/0` and dotnet IPC JUnit `38/0/0/0`.
- Remaining locked work: S3B implementation/live acceptance, S3C, R1C-R8,
  and old VS-T4 through VS-T8. S1, S2, S3A, R1A, and R1B are accepted as
  recorded above.

## Authoritative verification

After bootstrap, run `.\scripts\verify.ps1`. It runs the offline gate and
collects unavailable-state probes for `real_data` and `autocad_mechanical` as explicit
`SKIP` results with prerequisites removed. A real private-data or live AutoCAD
Mechanical gate that was not separately executed remains `NOT RUN`.

## Roadmap and governance gate — S3B accepted; future runtime locked (2026-08-06)

- S1 and S2 are accepted. S2C, actual read-only AutoCAD-native layout capture,
  is accepted at `365cb2df47cc3d0232a4b5df1901f55dbe46b22c` (PR #61,
  `origin/main`).
- S3A offline inspection evidence and extraction-plan contract is accepted.
  R1A SourceBundle offline contract and R1B manifest binding are accepted.
- S3B implementation is accepted through PR #65 and merge
  `a9968480258e01fda9d4dfbf01a27958b67747bc`.
- Issue #64 is completed.
- Runtime verification head: `9f5dc302643fdfae77cbda65dd6cdc0c8deccc59`.
- Record-only final head: `67c3496da313245fc9ceeee26814e099b32f2c87`.
- The accepted S3B boundary uses read-only exact-base Xref inspection and
  approved extraction into new disposable candidates only. Source Xrefs and
  accepted DWGs remain immutable; allowed local transforms are translation,
  rotation, and positive uniform scale only.
- Fresh server-owned live preflight remains mandatory immediately before
  mutation, and extraction evidence retains source handle, layer, block,
  source revision, source hash, and `REUSED_FROM_BASE_CAD` provenance.
- AutoCAD Mechanical S3B live acceptance: **NOT RUN**.
- Hosted AutoCAD .NET: **NOT RUN**.
- No private drawing/source-data acceptance is promoted.
- S3C, R1C SourceBundle/source-fusion, registry, revision, repair, verdict, publication, and OCR remain **locked**.
- No next runtime milestone is selected by this rebaseline.

## Visual Supervisor VS-T0 contract-only slice (2026-08-04)

- State: **Partially verified; contract-only slice complete**.
- Implementation head SHA: `0a8c9830ee33967a11b774584383caea9d1fde33`.
- Scope is limited to pure-Python validators, closed JSON schemas, fixtures,
  and policy helpers for run manifests, dimensions, geometry comparison,
  independent visual review, repair plans, region verification, and
  run-scoped authorization.
- Contract inventory: 7 validators, 7 schemas, and 7 synthetic examples.
- Focused VS-T0 suite: **55 passed**. Authoritative `scripts/verify.ps1`
  passed on the implementation head; .NET was 76/76, dotnet IPC was
  38/0/0/0, and offline JUnit was 646/0/0/0.
- `real_data: NOT RUN`; `autocad_mechanical: NOT RUN`; `OpenAI API: NOT RUN`.
- No visual model review, image processing/comparator runtime, AutoCAD
  evidence operation, repair loop, Codex bridge runtime, or publication
  mutation is implemented in VS-T0.

## M2 Drawing Initialization Gate

- State: **Executing**. The approved M0-M8 rollout merged at `1969dc9`; the
  complete design is `docs/superpowers/specs/2026-08-02-cad-agent-complete-design.md`
  and the execution record is
  `docs/superpowers/plans/2026-08-02-m2-drawing-initialization-gate.md`.
- T2 Drawing Setup contracts and validation merged at `2b7a756`. Full M2 is
  still executing and has not produced `SETUP_VERIFIED` acceptance.
- Hosted evidence does not promote AutoCAD/.NET/private gates to `PASS`.
  For the current M2 candidate, the required private-data gate is `NOT RUN`;
  the unavailable-state `real_data` probe is `SKIP`; and the AutoCAD/.NET live
  gate is `NOT RUN`. No hosted or contract-only result is a substitute for
  operator-controlled AutoCAD Mechanical evidence.

## M2 Mechanical benchmark

- State: **Representative live acceptance PASS**.
  Four comparable live epochs pass across two genuinely distinct observed
  AutoCAD runtime identities. The approved design is
  `docs/superpowers/specs/2026-08-30-m2-mechanical-benchmark-design.md` and
  the execution record is
  `docs/superpowers/plans/2026-08-30-m2-mechanical-benchmark.md`.
- Draft PR `#309` remains the benchmark integration point at its exact
  GitHub-observed head `738dac0b11231a71f91376ebb5ef22b6c709461d`. The
  bounded C# health-owner successor is branch `codex/m2-plugin-identity`,
  based on that head. The final live implementation/harness evidence ran at
  `5c556b352f401bc084d4ee3f162c77d5df239378`; this acceptance-record update
  is committed at `38c640e4402dfc7868c67197b6d9a5bd4c0baa39`. Fresh
  `origin/main` remains `ffde4673be48f85a7fd4c0a10b9b35000c710e16`.
- Implemented scope: the closed `m2-mechanical-benchmark-record-1.0` oracle,
  cross-process deterministic staged-DXF fixture normalization with
  class-order semantic-invariance guards and post-normalization review,
  opt-in
  read-only Mechanical harness, and fail-closed runtime/implementation/PR/
  harness/plugin identity, transport, semantic wrong-target and stale-probe,
  failure-context, and cleanup accounting. No new transport, database,
  telemetry, or MECH-1 façade was added.
- Focused M2 verification before the final harness-only repairs passed `136`
  Python tests; the full C# suite passed `198`; Ruff and `git diff --check`
  passed. The final successor adds only the existing Python/FileIPC harness
  owner repairs described below; the canonical offline verifier is rerun
  separately before release integration.
- Authoritative full verifier on successor head `e8a42a5` exited `0`: C#
  `198` tests passed; offline JUnit `tests=3089, failures=0, errors=0,
  skipped=0`; dotnet IPC JUnit `tests=117, failures=0, errors=0, skipped=0`;
  real-data `2 skipped`; AutoCAD unavailable-state `14 skipped`; generic and
  M2 live markers **NOT RUN**; causal RED checks for fixture
  reproducibility, loaded identity, and semantic wrong-target refusal were
  accepted.
- Canonical offline verifier `scripts/verify.ps1 -SkipAutoCADDotNet` on
  successor head `78e06e5` exited `0`: offline JUnit `tests=3090`, dotnet IPC
  JUnit `tests=117`, with no failures/errors; the previously verified C# owner
  is unchanged. The final fixture proof includes no proxy/class-indexed entity
  invariant and equality of headless semantic review before/after
  normalization.
- A historical exact full-gate attempt at
  `4ee5e879214531b3d52c82a989de53e5541fbfd2` stopped in the .NET build with
  `MSB3027/MSB3021` because the Release plugin DLL was locked by AutoCAD PID
  `27168`; no process was launched or stopped to work around the lock.
- Current persisted record `C:\temp\cad-agent-m2-record.json` is SHA-256
  `360dd99c9ca88d9f09ef27af942cf2d52f545b7e6a4d58c888ae5d359d2c3ee0`.
  It contains four failed non-comparable epochs, aggregate `0/0`, status
  `BASELINE_ONLY`; after the modal was dismissed with Load Once, the current
  clean-head harness recorded a health/tool failure because the active plugin
  still omits the binary identity fields. That epoch also proved
  `closed_without_save`, source/staged unchanged, and release verified. Its
  sidecar is
  `C:\temp\cad-agent-m2-record.measurements.json`, SHA-256
  `b0e5d8e94bdc4b44d8f3acc58c3d873bb971400a2318b8944855d401d0eb301a`, with
  `0` measurements and `0` entity queries. The record is append-only evidence
  and is not promoted to acceptance.
- After the final artifact was loaded into the fresh runtime PID/HWND
  `27812/10881220`, the append-only
  `C:\temp\cad-agent-m2-record-r2.json` contains twelve total epochs, of
  which four are successful comparable epochs. The current record SHA-256 is
  `bbbdc33756b735e32acd7206d02a43f903f5ae944b72917d704260a096044c70`;
  its aggregate is `comparable=4`, `successful=4`, `success_rate=1.0`,
  `representative=true`, `status=REPRESENTATIVE`. The successful epochs
  observe the two distinct identities `acad-pid-1720-hwnd-1378378` and
  `acad-pid-27812-hwnd-10881220`; earlier non-comparable epochs remain
  recorded and are not backfilled. The successful epochs prove live geometry
  `3/3`, component `1/1`, dimension `1/1`, positive stale/wrong-target
  refusals, complete transport accounting, unchanged source/staged/candidate
  hashes, and close-without-save cleanup. No process control or blind retry
  was used.
- The current live harness binds runtime identity to the observed `acad.exe`
  PID/HWND, exact clean implementation and harness heads, and the exact
  Release DLL hash. The successor C# health owner now reports the executing
  assembly path and lowercase SHA-256, and the harness compares that observed
  value with the exact isolated Release artifact. Focused C# verification
  passed `198` tests; the final isolated x64 Release artifact is
  `C:\temp\cad-agent-m2-plugin-identity\autocad_plugin\CadAgent.AutoCAD2027\bin\x64\Release\net10.0-windows\CadAgent.AutoCAD2027.dll`
  with SHA-256
  `f7d3467a57ccb186b78d515ffe737afba08d3d3c691e0518e020a16ddfcbf40c`.
  The normal main-worktree Release DLL stayed locked/unchanged by AutoCAD;
  no process-control workaround was used. The DIMENSION read owner now uses
  DXF group 13/14 endpoint distance when AutoCAD reports the generated
  dimension's group 42 sentinel `-1.0`; the live evidence proves the fallback
  returns the expected 100 mm without COM write access. The harness also resets
  the disposable candidate after the wrong-target close and waits for the MDI
  transition to settle, preserving DBMOD/read-only evidence.
- Explicit gates: benchmark `autocad_mechanical` representative live
  acceptance is **PASS** with four successful comparable epochs across two
  observed runtime identities, exact loaded-plugin SHA attestation, semantic
  geometry/dimension, transport, stale/wrong-target, identity, and cleanup
  evidence. Benchmark `real_data` is **NOT RUN**; no repair or save attempts
  were made.
- MECH-1 remains **NOT JUSTIFIED**: no measured sidecar evidence shows that
  read-only CAD introspection materially improves coverage or context cost.

The exact future operator packet is tracked at
`docs/superpowers/plans/2026-08-30-m2-live-packet.md`. The packet records the
exact artifact, observed runtime identities, and final oracle. No remaining
Human-only action is required for M2 acceptance.

## M3 disposable LINE acceptance — contract-only boundary

- State: **Contract-only composition PASS; live AutoCAD M3 NOT RUN**.
  This is one bounded acceptance epoch over existing R4/R5/R6 owners, not M3
  milestone closure and not production drawing mutation.
- Implementation head: `9fd370120a1cd88f5b94955500d3fa38b8d3123f` on
  `codex/m3-disposable-acceptance`; plan:
  `docs/superpowers/plans/2026-08-30-m3-disposable-line-acceptance.md`.
- Contract-only epoch evidence: one v1.1 `ROOT_PRE_REPAIR` candidate produced
  an owner-validated R5 `FAIL`, one `REPAIR_DXF_PRIMITIVE` `LINE` operation was
  planned and authorized once, the existing `DotNetIPCClient` disposable
  workspace closed with `save_changes=false` and `zero_survivors`, and a new
  v1.1 `POST_REPAIR` candidate received an independently bound R5 `PASS`.
  The executor observed exactly one erase and one LINE create; replay and
  stale/rebound R5 paths were refused before a second mutation.
- Integrity/evidence: source, base, and accepted sentinel files remained
  byte-identical; candidate pre/post hashes and DARA/R3 correspondence were
  refreshed. Human-intervention events were empty because this was explicitly
  `CONTRACT_ONLY`; no AutoCAD process, `BVTL.dwg`, NETLOAD, save, or live visual
  provider was used.
- Causal owner repair: R6 now derives a canonical latest-mutation identity
  only for an owner-validated `candidate-revision-1.1` `ROOT_PRE_REPAIR` record
  whose closed mutation evidence has no legacy latest-mutation field. Legacy
  candidates retain the explicit field requirement; no second identity or
  repair subsystem was added.
- Verification on the exact head: focused M3/R4/R5/R6/R7 suite `300 passed`;
  Ruff passed; `scripts/verify.ps1 -SkipAutoCADDotNet` exited `0` in a clean
  worktree with offline JUnit `tests=3098, failures=0, errors=0, skipped=0`
  and dotnet IPC JUnit `tests=117, failures=0, errors=0, skipped=0`.
  The real-data unavailable probe recorded `2 skipped`, the AutoCAD unavailable
  probe recorded `14 skipped`, and the existing intentional causal RED gate
  failed as expected and was accepted by the verifier.
- Remaining M3 boundary: one real disposable candidate-only LINE epoch with a
  genuinely observed current R5 `FAIL`, live R6 mutation, cleanup, refreshed
  R4 lineage, and a fresh live R5 `PASS`. The current R8-D driver remains
  acceptance-only/read-only, so no live M3 PASS is claimed. MECH-1 remains
  **NOT JUSTIFIED**.
- Live follow-up packet: `docs/superpowers/plans/2026-08-30-m3-live-packet.md`.
  It freezes the current main/plugin artifact identity, the existing
  NETLOAD/APPLOAD prerequisite, transport variables, owner sequence, safety
  invariants, and the exact reason no live command is published yet: the
  merged main branch had no M3 live composition test or canonical live record
  writer. The bounded RED-first implementation is now on candidate head
  `910643227299c36ed96c846b6edaf2b2eb4320e9` in
  `codex/m3-live-driver`; it remains offline/provider-callback only until
  hosted review is complete and is not a live acceptance result.

## M3 provider-backed live seam — offline boundary

- State: **Offline contract PASS; provider-backed live acceptance NOT RUN**.
  `R5_MODE=contract-only` remains unchanged and cannot create a live PASS.
- Candidate implementation: `cad_agent/m3_live_record.py` is the pure,
  closed-key canonical record oracle; `mcp_integration_lib/m3_live_harness.py`
  is the opt-in fixed-order callback composition seam. It performs no
  NETLOAD, UI automation, process control, or AutoCAD mutation.
- Fail-closed bindings require observed PID/HWND/document identity, current
  main and exact loaded-plugin SHA-256 equality, provider-backed pre-repair
  R5 `FAIL`, one consumed candidate/R5/operation-bound authorization, exactly
  one semantic R6 mutation, a distinct post-repair candidate, fresh provider
  R5 `PASS`, reconciled FileIPC/.NET/Task6/R6 transport counts, protected-file
  integrity, captured Human-intervention events, and observed zero-survivor
  cleanup. Caller labels, stale/rebound evidence, contract-only results,
  `SKIP`/`NOT_RUN`, retries, and ambiguous outcomes fail closed.
- Verification on candidate head: focused new contract suite `13 passed`,
  nearest M3/R4/R5/R6/R7 regression `225 passed`, Ruff and `git diff --check`
  passed. The canonical offline verifier recorded JUnit
  `tests=3111, failures=0, errors=0, skipped=0`, dotnet IPC
  `tests=117, failures=0, errors=0, skipped=0`, accepted causal RED `1`,
  real-data `2 skipped`, and AutoCAD `14 skipped`.
- Remaining boundary: hosted verification of this bounded seam, then a
  genuine provider-backed disposable AutoCAD epoch with fresh runtime,
  candidate, R5, repair, transport, integrity, and cleanup evidence. No live
  command or Human action is requested while the mode remains contract-only.

## M3 live oracle hardening — red-team correction

- Advisory `#301` comment `5468292161` identified a critical false-PASS risk
  after the seam was merged: reconciled transport failures/retries, reduced
  caller-made R5/R6 mappings, missing repair-executor cross-binding, and an
  unnecessarily non-empty Human-event requirement.
- Candidate hardening is commit
  `4d15a6e7830961f68200b7098a8a15c802e829ea` on
  `codex/m3-oracle-hardening`, based on main
  `ad1ac402b83b88780c7392e36f9f609fea5650b9`. It remains offline and does not
  perform provider calls, NETLOAD, UI automation, process control, or AutoCAD
  mutation.
- `cad_agent/m3_live_record.py` now validates the exact current-main
  `validate_visual_verdict_result` and `validate_approved_repair_result`
  payloads, binds their sealed identities to the reduced record, rejects any
  transport failure/retry, cross-binds `repair_executor` attempts to the one
  R6 attempt, and accepts `human_intervention={captured: true, events: []}`.
- RED/GREEN evidence on the candidate: focused hardening suite `18 passed`;
  nearest M3/R4/R5/R6/R7 regression `230 passed`; Ruff and
  `git diff --check` passed. Canonical verifier on the clean exact commit
  recorded offline JUnit `tests=3116, failures=0, errors=0, skipped=0`,
  dotnet IPC `117/0/0/0`, causal RED `1 accepted`, real-data `2 skipped`,
  AutoCAD `14 skipped`, and exit `0`. `LIVE_REPAIR_ACCEPTANCE=NOT_RUN`
  remains true.
- The critical advisory is actionable, not stale; merge/live decisions remain
  blocked on this exact-head hardening candidate until hosted checks pass.

## M3 Task6 provider accounting correction — follow-up

- Advisory `#301` critical source `#311` comment `5468458694` identified a
  remaining contradiction: the record requires distinct canonical pre/post
  Task6 turns while `transport.task6_provider` could claim only one attempt.
- Candidate commit `8b4c5acfb48d791d11aa28fc42bf7ad5a0b8736d` on
  `codex/m3-task6-accounting`, based on main
  `14ad95bd038f23c4d6e22808762b3a6a7ea49fe3`. The bounded validator now
  requires `task6_provider` attempts `2`, successes `2`, failures `0`, retries
  `0`, and exact ordered `turn_ids=[pre_r5.turn_id, post_r5.turn_id]`.
  Attempts `1`, `>2`, or turn identity drift fail closed; no other transport
  cardinality is generalized.
- Verification: focused Task6/M3 suite `21 passed`; nearest R5/R6/M3
  regression `214 passed`; docs contract `34 passed`; Ruff and
  `git diff --check` passed. Canonical verifier on the clean exact commit
  exited `0` with offline JUnit `tests=3119, failures=0, errors=0, skipped=0`,
  dotnet IPC `117/0/0/0`, causal RED `1 accepted`, real-data `2 skipped`, and
  AutoCAD `14 skipped`. Provider/live AutoCAD acceptance remains `NOT_RUN`
  and `R5_MODE=contract-only` remains unchanged.

## Personal Lean Pilot — Gate A Setup Lite

- State: **Partially verified; Gate A remains open**. The personal-project
  rebaseline is approved in
  `docs/superpowers/specs/2026-08-03-personal-lean-pilot-rebaseline-design.md`;
  its executable Gate A plan is
  `docs/superpowers/plans/2026-08-03-personal-lean-pilot-gate-a-setup-lite.md`.
- Offline implementation candidate: `579732a511e6775ed0b749a28f6627c7b92dba89`
  on `codex/personal-lean-pilot-rebaseline`. It includes legacy
  `DRAFT_REFERENCE` classification, the read-only Drawing Setup snapshot and
  IPC operation, SHA-bound audit/verify CLI commands, deterministic blockers,
  stale-evidence refusal, and the opt-in one-drawing live gate.
- Focused unavailable-state run: the Drawing Setup, IPC, live-harness,
  contract, and CLI suites reported `114 passed, 2 skipped, 18 subtests
  passed`. The personal live test skipped because
  `CAD_AGENT_LEAN_DISPOSABLE_DWG`, `CAD_AGENT_AUTOCAD_HWND`, and
  `CAD_AGENT_DOTNET_IPC_DIR` were absent. This skip is not live acceptance.
- Authoritative verifier on the implementation candidate: `scripts/verify.ps1
  -SkipAutoCADDotNet` exited `0`; dotnet_ipc JUnit was `38/0/0/0`, offline
  JUnit was `547/0/0/0`, the `real_data` unavailable-state probe was `2/2`
  skipped, and the `autocad_mechanical` unavailable-state probe was `8/8`
  skipped. Python was 3.11.9 and the required Tesseract version was present.
  The AutoCAD .NET build/test gate is **NOT RUN** because `dotnet` is absent;
  the AutoCAD live marker is also **NOT RUN**.
- External acceptance prerequisites checked on 2026-08-03 were all absent:
  owner-approved DWT, disposable DWG, AutoCAD HWND, plugin path, Drawing
  Definition, and .NET IPC directory. Therefore the real three-command flow
  and profile gate are **NOT RUN**. No personal profile metadata or live review
  record was created, because approved values and a real run do not exist.
- Acceptance consequence: no owner-approved disposable drawing has produced
  hash-stable, DBMOD-stable `SETUP_VERIFIED` evidence. Gate A cannot be called
  complete, and the legacy image/PDF path remains `DRAFT_REFERENCE` rather
  than authoritative.

## Personal Lean Pilot — Gate B offline dimension candidate

- State: **Partially verified; Gate A remains open and Gate B acceptance is
  NOT RUN**. The approved offline continuation is recorded in
  `docs/superpowers/specs/2026-08-03-personal-lean-pilot-offline-continuation-design.md`
  and its implementation plan is
  `docs/superpowers/plans/2026-08-03-personal-lean-pilot-gate-b-dimension-offline.md`.
  The offline implementation candidate is
  `88bdb1c` on
  `codex/personal-lean-pilot-rebaseline`.
- Implemented scope: strict dimension plan/evidence contracts; approved
  driving lengths and explicit datum anchoring at the existing SolveSpace
  boundary; native editable DXF `DIMENSION` generation and read-back;
  hash/provenance/Setup refusal; immutable IR byte snapshots; post-review and
  post-publish DXF hash binding; a non-overwriting temporary-output publish;
  rogue-geometry refusal; and one non-overwriting private-output CLI.
  Successful offline evidence still fixes `acceptance=NOT_RUN`.
- Focused Gate B offline run on 2026-08-03: **155 passed** with no failure.
  It covered contracts, orchestration, CLI, Drawing Setup, constraint solving,
  native DXF building, and headless review, including mutation and
  non-overwrite regressions.
- Authoritative verifier on the candidate:
  `scripts/verify.ps1 -SkipAutoCADDotNet` exited `0`; dotnet_ipc JUnit was
  `38/0/0/0`, offline JUnit was `603/0/0/0`, the `real_data`
  unavailable-state probe was `2/2` skipped, and the `autocad_mechanical`
  unavailable-state probe was `8/8` skipped. Python was 3.11.9, Ruff passed,
  and the required Tesseract version was present.
- Required gates not executed: the owner-approved compatible geometry export
  is absent, so the private `real_data` constraint benchmark is **NOT RUN**;
  Gate B private acceptance is **NOT RUN**; the AutoCAD .NET gate is **NOT
  RUN**; and the AutoCAD Mechanical 2027 live gate is **NOT RUN** because no
  qualifying session/prerequisites exist on this machine. Unavailable-state
  `SKIP` results are not acceptance evidence.
- Sample custody: an owner-provided DWG was hash-copied to a non-overwriting
  custody location outside Git, and the source hash remained stable. Content
  inspection, conversion, open, save, and mutation were all **NOT RUN**.
- Acceptance consequence: the Gate A → Gate B → Gate C order is unchanged.
  No `PERSONAL_VERIFIED`, `SETUP_VERIFIED` live outcome, or release outcome is
  claimed by this offline candidate.

## AutoCAD .NET plugin — Option A / phần cũ 1

This subsection records the completed Windows-only managed .NET slice. The
read-only Mechanical BOM extension is recorded separately below.

- Integrated into `main` at `bb1c6e9`; latest synchronized head:
  `f69d6a0` on `main` and `origin/main`.
- State: **Verified for the managed disposable smoke scope**; the repository's
  legacy-LISP aggregate marker remains a separate gate.
- Scope completed: Windows-only AutoCAD Mechanical 2027 managed plugin scaffold,
  versioned JSON/File IPC contracts, Mechanical no-op boundary, deterministic
  read-only review core, isolated Python dotnet_ipc backend, and the four
  command/dispatcher boundaries, plus the Windows `CADAGENT_DISPATCH` trigger,
  disposable .NET live-smoke harness, and one-shot `Application.Idle`
  disposable-close fix.
- C# evidence: restore/build/test passed on Release x64 with 51 passed, 0
  failed, 0 skipped; Autodesk reference-conflict warnings remain, and no
  Autodesk DLL was copied to plugin output.
- Python focused evidence: the .NET IPC focused suite passed 16 tests plus 18
  subtests; the opt-in live module passed 2 offline cleanup tests and skipped
  its one live test; the exact three-file Ruff gate passed.
- Authoritative verifier: **PASS** when run on commit `f69d6a0` with the
  explicit lock-matching Python 3.11 interpreter
  `D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe`:
  40/40 locked distributions, .NET 68/68, dotnet_ipc JUnit 36/0/0/0,
  offline JUnit 444/0/0/0, unavailable probes 2 + 7 skipped, and full Ruff
  passed. The verifier reports the current automated AutoCAD marker as
  `NOT RUN` when live prerequisites are absent; this does not invalidate the
  separately recorded managed disposable smoke.
- Direct AutoCAD .NET smoke: **PASS** on a fresh disposable DXF in an isolated
  AutoCAD Mechanical 2027 process. Health and read-only review succeeded for
  handle `2F`; `close_disposable` returned
  `closed_without_saving=true`; after an 8-second independent postcondition
  check AutoCAD was back on `[Start]` and no longer had the DXF document open.
  The DXF remained on disk and was not saved or mutated.
- Automated AutoCAD live marker: **FAIL** when attempted with the legacy LISP
  dispatcher (`8 failed, 5 passed, 423 deselected`); the legacy close path
  reports `Automation Error. Drawing is busy`. The focused .NET live test
  reported `1 passed, 3 deselected`; this is retained as historical evidence for
  the legacy-LISP bootstrap failure and is separate from the direct managed
  smoke above.
- Safety boundary: no production save, repair, or mutation was added or run;
  the existing dispatcher was not modified.
- Evidence records: `docs/reviews/2026-08-01-autocad-dotnet-live-review.md`,
  `docs/reviews/2026-08-01-autocad-dotnet-close-live-review.md`, and
  `docs/reviews/2026-08-01-autocad-dotnet-close-live-followup.md`.
- Completion: the reviewed candidate is integrated and pushed. No COM/ActiveX
  code was added to the plugin. No production drawing or `Drawing1.dwg` was
  opened, saved, or modified by this work.

## AutoCAD .NET plugin — Mechanical BOM 2A extension

- Candidate code head: `1ebb4db` on `integration/mechanical-bom-readonly`.
- Date: 2026-08-01.
- State: **Partially verified**. The managed read-only implementation, IPC
  contract, Python helper, unit tests, and authoritative offline verifier pass;
  the live AutoCAD Mechanical gate is explicitly **NOT RUN**.
- Scope: operation `mechanical_bom` reads direct ModelSpace `BlockReference`
  inserts and direct `AttributeReference` values, returns deterministic
  `component_count`/`components` payload data, and always reports
  `changed=false`. It does not traverse nested blocks, mutate/save drawings,
  create balloons, or use Mechanical SDK/COM/ActiveX/native APIs.
- Contract evidence: schema remains `1.0`; `parameters` is exactly `{}`;
  request/result examples and C#/Python validation are included under
  `contracts/autocad-ipc/`.
- C# evidence: Release x64 build/test passed with **68 passed, 0 failed, 0
  skipped**. Existing Autodesk `MSB3277` reference-conflict warnings remain;
  no Autodesk DLL was copied to plugin output.
- Python evidence: the .NET IPC suite passed **18 tests and 18 subtests**; the
  live-module suite passed **5 offline tests** with one expected live
  prerequisite skip. The fixture topology test passed; actual plugin nested
  exclusion remains live **NOT RUN**.
- Authoritative verifier: **PASS** on code head `1ebb4db` using the lock-matching Python
  3.11 interpreter `D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe`:
  C# **68/68**, dotnet IPC JUnit **36/0/0/0**, offline JUnit
  **444/0/0/0**, real-data unavailable probe **2 skipped**, AutoCAD Mechanical
  unavailable probe **7 skipped**, and Ruff/environment checks passed.
- AutoCAD live marker: **NOT RUN** because `CAD_AGENT_FILE_IPC`, a live
  AutoCAD HWND, and the declared File IPC bootstrap path were not available.
  No AutoCAD process or `Drawing1.dwg` was touched; no live PASS is inferred
  from build or unit tests.
- Evidence records: `docs/superpowers/specs/2026-08-01-mechanical-bom-readonly-design.md`,
  `docs/superpowers/plans/2026-08-01-mechanical-bom-readonly.md`, and the
  task reports/review packages in the plan's ignored SDD workspace.
- Integration: reviewed candidate merged into `main` and pushed as `1d9af6b`.
- Remaining live gate: a future operator-controlled disposable-DXF AutoCAD
  session may promote the live marker from `NOT RUN` to `PASS` or `SKIP`.

## AutoCAD .NET plugin — live BOM and legacy close continuation (2026-08-02)

- State: **Verified for the Windows disposable-DXF live scope**. This
  continuation promotes the Mechanical BOM live gate and removes the legacy
  no-save close race without changing the external dispatcher or .NET plugin.
- Managed BOM live gate: **PASS** on AutoCAD Mechanical 2027 using a fresh
  session and a DXF created below `C:\temp`. The opt-in test passed health,
  read-only review, `mechanical_bom` with two direct components (`COMP_EMPTY`
  and `COMP_FRAME`), unchanged `DBMOD`, unchanged source hash, request/result
  cleanup, and close-without-save (`1 passed, 5 deselected`).
- Legacy close live smoke: **PASS** on a separate disposable DXF. The client
  opened the drawing, read an entity, sent the queued no-save close command,
  and the SHA-256 remained unchanged. No `Drawing is busy` error occurred.
- Legacy aggregate context: the broader `test_file_ipc_e2e.py` run had
  `4 passed, 7 failed`; the remaining failures were existing round-trip handle
  assumptions after save/reopen (`Entity not found`), outside this close fix.
- Regression/unit evidence: the no-save path now emits exactly
  `(command-s "_.CLOSE" "_N")`; the save-enabled branch remains on its COM
  save path. Focused Python tests passed `49` tests plus `18` subtests, and
  Ruff passed.
- Authoritative verifier: **PASS** on the integrated candidate with .NET
  `68/68`, dotnet IPC JUnit `36/0/0/0`, offline JUnit `446/0/0/0`, lock and
  environment contracts passed. Autodesk reference-conflict warnings remain
  informational. No production/customer drawing was saved or modified; all
  live fixtures were disposable files below `C:\temp`.

## Pre-foundation baseline

| State | Date | Commit | Environment | Command | Result |
|---|---|---|---|---|---|
| Verified | 2026-07-22 | `908d016` | Windows, bundled Python 3.12.13, Tesseract 5.4.0.20240606 | `python -m pytest primitive_ir_lib/tests semantic_ir_lib/tests dxf_builder_lib/tests mcp_integration_lib/tests agent_lib/tests -q -p no:cacheprovider` | `255 passed, 11 skipped, 3 warnings` |

This baseline demonstrates that the existing core is worth preserving. It is
not the Python 3.11 foundation certificate because seven solver tests were among
the skips and the run used Python 3.12.

## Current module status

| Area | State | Evidence and limit |
|---|---|---|
| Primitive IR | Verified | Final Python 3.11 offline gate passed with zero skips; the approved private PDF, identified by SHA-256 below, completed Primitive IR for all nine pages. |
| Semantic IR | Verified | Final Python 3.11 offline gate passed with `python-solvespace` installed and zero offline skips; the approved private PDF completed all nine Semantic IR checkpoints. Assembly now uses raw detections for compound inference but persists only deterministic solver-ready constraints, reducing private page 1 from 538,983 raw relations to 3,693 retained constraints. |
| DXF build/review/repair | Verified | Final Python 3.11 offline DXF tests passed; production AutoCAD Mechanical mutation is outside this state. |
| Visual PDF-to-DXF fidelity | Verified for reviewable paper-layout and primary-linework scope | All nine delegated visual approvals were promoted into the fidelity manifest, and 9/9 promoted DXFs passed the dedicated read-only AutoCAD Mechanical review checkpoint. OCR/font, hatch, linetype, table placement, and dimension extensions now have review-only approval/reconstruction paths, but remain non-authoritative CAD content; model export remains excluded. |
| MCP/File IPC | Verified | Offline/fake IPC tests and the current six-test `autocad_mechanical` live gate passed on AutoCAD Mechanical 2027, including identical filenames under different directories and disposable-drawing cleanup. Active-document identity is full-path-bound. |
| Agent advice/audit | Verified | Agent execution is non-mutating by default. Application is a separate step bound to a saved report SHA-256 and exact source/IR hashes; approved constraint drops trigger a new solve before DXF generation. |
| Reproducible foundation | Verified | See the Foundation certificate and `docs/reviews/2026-07-22-reproducible-foundation.md`. |
| Thin image/PDF orchestration CLI | Verified | `cad_agent` run/resume and run-pdf/resume-pdf produce SHA-bound staged DXF and build evidence. Separate Mechanical review/repair commands enforce evidence, approval, backup, and second-review boundaries. |
| Production repair safety loop | Partially verified | Fake-MCP tests cover refusal, hash-verified backup, repair, second review, close-without-save rollback, and verified-backup reopen. A real staged-DXF review passed; no production drawing repair was requested or run. |
| M2 Drawing Initialization Gate | Executing | The image/PDF pipeline remains `DRAFT_REFERENCE`. A separate dimension-first path must provide hash-bound `SETUP_VERIFIED` evidence before an authoritative drawing path can create geometry; current M2 private/live gates are `NOT RUN` or `SKIP` as recorded above. |

## Known production gates

- Calibration may be auto-accepted only with at least two independent
  candidates and median relative error at most 3 percent. Current production
  callers must opt into consensus and retain human approval for unverified
  scale.
- Private drawing benchmarks remain outside Git and are addressed by SHA-256.
- AutoCAD Mechanical mutation requires backup, human approval, live review, repair, and
  a second review.

## Next slice

Maintain the SHA-bound private benchmark and run any future optimization against
it. Review-only fidelity extensions must be rerun against the private PDF before
they can be considered for visual acceptance. Production repair remains a
separate human-approved operation with backup and a second live review; it was
not requested or run here.

## Latest continuation evidence

- Head: `dae1f2c128c1b58eb84a400d15b53d9ada127916`.
- Offline gate: `scripts/verify.ps1` passed with `387 passed, 8 deselected`; the
  unavailable-state probes recorded `2` real-data skips and `6` AutoCAD skips.
- Live gate: with AutoCAD Mechanical 2027 and the local File IPC dispatcher,
  `python -m pytest -m autocad_mechanical -ra -p no:cacheprovider` passed
  `6 passed, 389 deselected` in `143.68s`. All smoke files were disposable
  DXFs under `C:\temp`; each live test now closes its temporary drawing without
  saving.
- Fidelity hatch: commits `50e49a1`, `75b5b80`, and `939cc29` add stable
  candidate IDs, hash-bound polygon approval, native review-only `HATCH`
  reconstruction, and the corresponding CLI/design evidence. No production
  AutoCAD mutation is authorized.

## Fidelity, stable identity, and P1 continuation (2026-08-02)

- Candidate implementation head: `aeaf950`. The specification and plan are
  recorded in `docs/superpowers/specs/2026-08-02-fidelity-legacy-p1-design.md`
  and `docs/superpowers/plans/2026-08-02-fidelity-legacy-p1.md`.
- Stable component identity: review and repair now use an exact `PART_ID`
  fallback when a saved/reopened INSERT handle changes. Ambiguous duplicate
  identities fail closed; the live E2E helper rebinds the current handle before
  inspection. This removes the old `Entity not found` assumption without
  weakening the mismatch gate.
- Advanced fidelity: text, table text, dimension, hatch, and linetype review
  sidecars are now exposed as hash-bound per-page entries in the review index
  and queue. Missing or invalid sidecars remain `not_run`/`invalid_artifact`,
  and the overall fidelity state remains `needs_review`; no production CAD
  mutation or model export is enabled by this change.
- P1 local image gate: **PASS** for the workstation-local page scan
  `bv (1)_p01.png`, SHA-256
  `95fb77b16c61cac7a3463e9fc29d0883fb34fbf5ad92d311e9ee6c658a736918`.
  The official real-image benchmark passed `1` test using Tesseract
  `5.4.0.20240606`/`eng`; it found the expected `2760`/`1525` OCR region and
  the overlapping Hough-line witness chain, with relative scale consistency
  error about `1.46%`. The source image and report remain outside Git.
- Focused evidence: DXF reviewer/repair suite `30 passed`; fidelity suite
  `41 passed`; line-merging/tick suite `26 passed`; Ruff and `git diff --check`
  passed.
- Authoritative verifier: **PASS** on `aeaf950` with the lock-matching Python
  3.11 interpreter: .NET `68/68`, dotnet IPC JUnit `36/0/0/0`, offline JUnit
  `450/0/0/0`, unavailable probes `2` and `7` skipped, environment/lock/Ruff
  checks passed. Autodesk reference-conflict warnings remain informational.
- AutoCAD live session probe: **NOT RUN for acceptance**. An attempt against a
  fresh AutoCAD Mechanical 2027 window with the declared dispatcher path gave
  `2 passed, 10 failed`; all failures timed out waiting for the dispatcher
  after the new session remained on `[Start]`. This is a session/bootstrap
  prerequisite failure, not evidence that offline tests are live PASS. No
  production drawing or `Drawing1.dwg` was opened, saved, or modified.
- Remaining gates: run the live component round-trip only after a fresh
  AutoCAD session has loaded and answered `mcp_dispatch.lsp`; advanced fidelity
  sidecars still require private-data review before visual acceptance; the
  production repair loop remains a separately human-approved operation with
  backup and second review.

## Fidelity P1 live round-trip continuation (2026-08-02)

- The live prerequisite was completed in a fresh AutoCAD Mechanical 2027
  session by loading the declared `mcp_dispatch.lsp` through a startup script.
  All live fixtures were disposable DXFs under `C:\\temp`; no production
  drawing or `Drawing1.dwg` was opened, saved, or modified.
- Live smoke: **PASS**, `1 passed`.
- Live legacy round-trip: **PASS**, `5 passed, 7 subtests passed` in
  `154.69s`. Coverage includes beam `PART_ID` tamper/save/reopen/repair,
  primitive repair, native dimension inspection, six component repairs, and
  same-name drawings in different directories.
- Determinism fixes: command-boundary `CLOSE` with an open-document
  postcondition, command-level `OPEN` fallback when AutoCAD is on the Start
  tab, and a unique expected-block fallback that replaces a tampered component
  instead of creating a duplicate. Ambiguous candidates still fail closed.
- The final live run was performed after the dispatcher was loaded and a
  transient AutoCAD Options modal was dismissed. The result is the acceptance
  evidence for this candidate; the earlier bootstrap-only attempt remains a
  historical failure record above.
- Authoritative verifier on the final implementation: **PASS**, .NET `68/68`,
  dotnet IPC JUnit `36/0/0/0`, offline JUnit `453/0/0/0`, unavailable probes
  `2` and `7` skipped, with lock/environment/Ruff checks passing. Because this
  verifier invocation intentionally did not attach to the interactive AutoCAD
  session, its separate live marker is `NOT RUN`; the direct live result above
  is the live acceptance evidence.
- Remaining limits are unchanged: advanced fidelity sidecars still require
  private-data review before visual acceptance, and production repair remains
  separately human-approved with backup and second review.

## First product milestone decision

- State: **Verified** for the reviewable-DXF scope defined in
  `docs/PROJECT.md`.
- Date: `2026-07-28`.
- The approved nine-page private PDF completed Primitive IR, Semantic IR,
  optional audited Agent advice, staged/reconstructed DXF, headless structural
  checks, delegated visual promotion, and nine SHA-bound read-only AutoCAD
  Mechanical 2027 review checkpoints.
- The Agent path is advisory by default and has a separate explicit approval
  gate. No production drawing was mutated.
- Deferred work does not block the reviewable milestone: the user explicitly
  deferred the known font/OCR correction. Hatch, linetype, table placement,
  and true dimension semantics remain review observations rather than
  fabricated authoritative CAD entities.
- Production repair is an operational gate, not an automatic completion step:
  it still requires a named production DXF, matching evidence, verified backup,
  explicit repair confirmation, and a passing post-repair review.

## Thin vertical-slice CLI evidence

- State: **Verified**
- Date: `2026-07-22`
- Implementation Head SHA: `8410712f0c7c23f707acc1b251620712806be971`
- Design and plan: `docs/superpowers/specs/2026-07-22-vertical-slice-cli-design.md`; `docs/superpowers/plans/2026-07-22-vertical-slice-cli.md`
- Focused command: `& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_cad_agent_cli.py -q -p no:cacheprovider` → `3 passed`
- Authoritative command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` → exit `0`
- Offline JUnit: `tests=295; failures=0; errors=0; skipped=0`
- `real_data`: unavailable-state probe `SKIP` (`tests=1; skipped=1`); approved private run `NOT RUN`
- `autocad_lt`: historical unavailable-state probe `SKIP` (`tests=4; skipped=4`); live session run `NOT RUN` at this pre-target-change commit
- Historical limitation: this former image-only slice is superseded by the PDF vertical-slice evidence below.

## PDF vertical-slice orchestration evidence

- State: **Verified**
- Date: `2026-07-22`
- Implementation Head SHA: `1669f25e88847b47284219c92769801a5bc81768`
- Design and plan: `docs/superpowers/specs/2026-07-22-pdf-vertical-slice-design.md`; `docs/superpowers/plans/2026-07-22-pdf-vertical-slice.md`
- Behavior: `run-pdf` and `resume-pdf` SHA-bind a PDF, its explicit scale approval, the package render manifest, and per-page rendered PNG, Primitive IR, Semantic IR, staged DXF, and build-evidence checkpoints. Resume reuses intact pages, rebuilds only invalid dependent stages, and rejects a changed PDF before reuse.
- Focused command: `& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_cad_agent_pdf.py tests\test_cad_agent_cli.py tests\test_cad_agent_live.py -q -p no:cacheprovider` -> `12 passed`; coverage includes multi-page output, byte-identical resume, changed source refusal, affected-page rebuild, missing Primitive IR recovery, and CLI run/resume.
- Live staged review: a newly generated two-page PDF under `C:\temp\cad-agent-pdf-live-20260722` completed through `run-pdf`; `mechanical-review` opened only page 1's staged DXF through the AutoCAD Mechanical 2027 File IPC dispatcher and reported `passed=true`, `structural_checked=1`, `geometry_checked=1`, with no mismatches or warnings. No repair or production save was requested.
- Current live marker gate: with AutoCAD Mechanical HWND `393650` and the loaded dispatcher, `& '.\.venv-py311\Scripts\python.exe' -m pytest -m autocad_mechanical -ra -p no:cacheprovider` -> `4 passed, 305 deselected` in `69.50s`; the smoke scope used only disposable DXFs under `C:\temp`.
- Authoritative command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` -> exit `0`; offline JUnit `tests=304; failures=0; errors=0; skipped=0`; SHA-256 `d9f8d85ed0ae42b14d4db00639a51d329a438b11ee2878cb8428b576dbd0e0fe`.
- `real_data`: unavailable-state probe `SKIP` (`tests=1; skipped=1`), SHA-256 `9bef0b1195208264fc4b7e0f07c0ec898f659f9925b6caa983143659ebb107d5`; approved private run `NOT RUN`.
- `autocad_mechanical`: unavailable-state probe `SKIP` (`tests=4; skipped=4`), SHA-256 `ec6a9b12540c9188a76988880e3651f81c63c399d4da5c989002f2c9b4b801f4`.
- Remaining risk: no approved private PDF was run at this historical command; the later full private-PDF evidence is recorded below.

## Approved private PDF full-run evidence

- State: **Verified**
- Date: `2026-07-22`
- Approved input: private PDF SHA-256 `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`; it remains outside Git.
- Calibration: all nine title blocks state `1:40`; the approved 144-DPI conversion is `7.055555555556 mm/px`. OCR also records any detected scale label as a `needs_verification` candidate and never overrides the approved manual calibration.
- Checkpoints: all 9/9 rendered-page, Primitive IR, Semantic IR, staged-DXF, and SHA-bound build-evidence records completed under private staging. Every staged DXF passed the headless reviewer.
- Visual-fidelity correction: these checkpoints are analysis-pipeline evidence only. The page-wide model-scale transform, zero extracted text primitives, and semantic `INSERT` overlays mean they must not be read as faithful drawing-sheet reconstructions. The separate fidelity workflow below is the only current visual-comparison path.
- Dense-data optimization evidence: page 1 completed compound recognition with 1,170 primitives and 538,983 detected constraints. Page 5 reduced 109,399 raw constraints to 1,392 after pruning; its 478 relevant lines exceed the documented 1,000-coordinate solver capacity, so the DXF preserved calibrated primitive geometry through the explicit `too_many_unknowns` fallback instead of spending minutes in an unstable solve.
- Live staged review: the standard `cad_agent mechanical-review` command with `--timeout-s 60` reviewed page 5 through AutoCAD Mechanical 2027 and reported `passed=true`, `structural_checked=485`, `geometry_checked=485`, no mismatches, no warnings, and no degraded geometry check. It was read-only: no repair or save was requested.
- Final repository verification: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` passed on `8c24896` with `318 passed, 5 deselected`; the final timeout-option revision is covered by focused CLI/live tests and the same verifier run.

## Fidelity reconstruction CLI evidence

- State: **Partially verified**
- Date: `2026-07-22`
- Implementation Head SHA: `374e75fb15abe9fd33df74fe61a84c966946f488`
- Design and plan: `docs/superpowers/specs/2026-07-22-fidelity-reconstruction-cli-design.md`; `docs/superpowers/plans/2026-07-22-fidelity-reconstruction-cli.md`
- Behavior: the private `fidelity-pdf`, `fidelity-overlay`, `fidelity-region-proposal`, `fidelity-region-approve`, `fidelity-reconstruct`, and `fidelity-observe` commands bind source and artifact hashes, keep output outside Git, forbid Mechanical operations on fidelity DXFs, and preserve `needs_review` rather than claiming a visual pass.
- Private source evidence: all nine paper-coordinate baselines and overlays completed. Under the user's explicit 2026-07-22 approval, every page has one SHA-bound `sheet_content` layout-region approval, reconstruction candidate, and composed page DXF outside Git (page 5 uses revision 4). These are broad layout regions, not approved model-view geometry. Table-grid observations and bounded table-region OCR completed for 9/9 pages. After the user's explicit approval to accept OCR subject to later correction, all 419 ordinary OCR candidates were hash-approved and emitted as `TEXT` into fresh private DXFs; the original geometry layouts remain unchanged.
- Authoritative command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` -> exit `0` on `ef7140d`; offline JUnit `tests=327; failures=0; errors=0; skipped=0`.
- `real_data`: private command evidence exists but the marker benchmark is **NOT RUN** for this workflow; `autocad_mechanical`: **NOT RUN** by design because fidelity artifacts are refused before live review/repair.
- Follow-on fidelity evidence: after the user's blanket approval for correctable OCR, 419 ordinary OCR candidates were emitted as Unicode `TEXT`. Bounded table-region OCR then supplied 81 additional table-text candidates (pages 2, 3, 5, 6, 8, and 9); dashed-line candidates and 14 dimension-value candidates were observed with provenance outside Git. These later candidates remain `needs_review`: linetypes are heuristic, table placement needs visual review, dimensions are observations only (no inferred `DIMENSION` entities), and hatch/model-view reconstruction are intentionally not fabricated.
- Latest source verification: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` passed on `99f9931`; offline JUnit `tests=328; failures=0; errors=0; skipped=0`. The private integrated PDF/DXF overlay set covers 9/9 pages and remains a diagnostic comparison, not a fidelity pass.
- Linetype reconstruction: `fidelity-linetype-reconstruct` was added on `1c8cbc8`. It clones an existing private layout DXF, applies `FIDELITY_DASHED` only to hash-bound observed horizontal patterns, and writes revisioned candidates with a report. The private nine-page revision changed 76, 88, 7, 60, 8, 14, 82, 16, and 67 LINE entities respectively; this remains a visual candidate, not an authoritative linetype mapping. The official verifier passed on that commit with `330 passed, 6 deselected`.
- Region-quality gate: the review-only reconstruction now compares an unfiltered and a short/near-duplicate-stroke filtered candidate on the approved crop before writing DXF. A private nine-page rerun under `C:\temp\cad-agent-fidelity-e48f3970-region-quality-r2` rejected the filtered profile on all pages because local F1 would decrease (baseline: 0.799, 0.817, 0.758, 0.738, 0.826, 0.875, 0.785, 0.709, 0.764; filtered: 0.787, 0.808, 0.751, 0.728, 0.821, 0.851, 0.781, 0.701, 0.757). The composed-page candidates therefore retain baseline geometry; their review-only F1 values are 0.506, 0.539, 0.369, 0.425, 0.345, 0.419, 0.380, 0.313, and 0.432. This is evidence that the heuristic was safely rejected, not a visual-fidelity pass.
- Hatch observation: `fidelity-hatch-observe` now writes SHA-bound, review-only diagonal-stroke sidecars. Its nine-page private rerun found six candidates only on pages 3, 5, and 9 (peak segment counts 20, 5, and 10); it found none on the other pages. No DXF `HATCH` entity or production mutation is emitted, and every candidate remains `needs_review` pending explicit boundary approval.
- Remaining risk: all nine compositions remain `needs_review`, and broad layout approvals do not validate visual similarity. OCR text remains correctable and text placement/style needs review. Disciplined model-view reconstruction, true dimension semantics, verified linetypes/hatches, and table-cell placement still require visual review before they can be represented as authoritative CAD content.

## Delegated-review fidelity promotion

- State: **Verified** (reviewable paper-layout and primary-linework scope only)
- Date: `2026-07-28`
- Source: approved private PDF, SHA-256
  `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`.
- Private artifact identifier: source prefix `e48f3970`, final manifest SHA-256
  `e36814340cb8ec32b71cefec67f454de29619632be30283d3bf77311fe0fe90d`.
  The external root contains all nine rendered pages, structural round-trip
  passes, overlays, observations, approvals, composed DXFs, promotions, and
  Mechanical review reports.
- OCR evidence: all 419 new OCR candidates exactly match the candidate text and
  pixel boxes in the previously approved set. Nine fresh text-approval files
  were created. Fresh DXF text reconstruction was intentionally not run because
  the user deferred the known Vietnamese preview-font correction.
- Private-data command with `<private-pdf>` and `<private-fidelity-root>`
  environment values plus `CAD_AGENT_FIDELITY_REQUIRE_RECONSTRUCTION=1`:
  `python -m pytest tests\test_cad_agent_fidelity_real_data.py -ra -p
  no:cacheprovider` -> `1 passed`. The gate validates 9/9 promotion and
  Mechanical checkpoints.
- Live command: AutoCAD Mechanical 2027 session `acad.exe`, HWND `787740`,
  loaded File IPC dispatcher; `python -m pytest -m autocad_mechanical -ra -p
  no:cacheprovider` -> `5 passed, 355 deselected` in `82.78s`. All live DXFs
  were disposable.
- Authoritative offline command:
  `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1`
  -> exit `0`; offline JUnit `tests=353; failures=0; errors=0; skipped=0`.
- Delegated visual review: all nine `reconstruction_pages/page_XX/overlay.png`
  files were inspected on 2026-07-28. Red is source raster edge, cyan is
  reconstructed DXF edge, and green is overlap. The paper layout and primary
  vehicle/structure linework were accepted for review use on every page.
- Integrated promotion: all nine composed pages received a delegated visual
  approval record and transitioned through
  `approved_for_mechanical_review` to `mechanical_reviewed`. The dedicated
  command compared each promoted type/layer signature with AutoCAD and wrote
  nine SHA-bound reports. Every report records `save_performed=false` and
  `repair_performed=false`.
- Limit: this is not a production model or a claim of pixel-perfect fidelity.
  Text/font/OCR, hatch, linetype, table placement, and dimension semantics are
  outside the accepted primary-linework scope.

## Agent action approval evidence

- State: **Verified**
- Date: `2026-07-28`
- Hardened Head SHA: `4656e9f148bcd90c43c9eba672fdd5977f8cc307`.
- Design and plan:
  `docs/superpowers/specs/2026-07-28-agent-action-approval-design.md`;
  `docs/superpowers/plans/2026-07-28-agent-action-approval.md`.
- Safety behavior: the file runner and synthetic demo are advisory by default.
  Application is a second step requiring a saved report and SHA-256, literal
  `APPLY`, an approval reference, and exact source/Primitive/Semantic IR hashes.
  The audit records provenance/action hashes and the post-application solve
  state. Approved constraint drops are solved again before DXF generation.
- Advisory smoke: the real runner loaded the repository's 900x700 synthetic
  image and IR, produced 10 constraint-drop proposals, exited `0`, and recorded
  `application_requested=false` and `actions_applied=false` under
  `C:\temp\cad-agent-agent-gate-09c276c`.
- Final authoritative command is recorded in the release candidate section:
  353 offline tests, one private fidelity test, and five live AutoCAD
  Mechanical tests all passed.
- Boundary: this gate controls in-memory IR application only. It does not grant
  permission to repair or save a production AutoCAD drawing.

## Semantic constraint compaction evidence

- State: **Verified** on
  `4656e9f148bcd90c43c9eba672fdd5977f8cc307`.
- Date: `2026-07-28`.
- Design and plan:
  `docs/superpowers/specs/2026-07-28-semantic-constraint-compaction-design.md`;
  `docs/superpowers/plans/2026-07-28-semantic-constraint-compaction.md`.
- Behavior: assembly uses the complete detected set for compound inference and
  persists only `prune_constraints(...).kept` in Semantic IR.
- Focused result: compound/pruning tests -> `26 passed`; final authoritative
  offline run -> `353 passed, 7 deselected`; Ruff -> `PASS`.
- Approved private page 1: 1,170 primitives, 1,187 parts, 3,693 retained
  constraints, Semantic assembly `34.002s`. The earlier raw count was 538,983.
- Approved private page 5: 485 primitives, 495 parts, 1,392 retained
  constraints, Semantic assembly `5.758s`, matching the previously recorded
  pruning result.
- Final private-data and live AutoCAD Mechanical gates passed on the same
  candidate.

## File IPC active-document verification

- State: **Verified** on
  `4656e9f148bcd90c43c9eba672fdd5977f8cc307`.
- Date: `2026-07-28`.
- Release-gate observation: the initial four-test AutoCAD Mechanical run had
  one transient `block-get-attributes` timeout followed by one wrong-document
  `Entity not found`; four later component subcases passed.
- Root cause: raw-LISP document opening waited for a dispatcher ping and
  originally verified only the basename.
- Fix: `drawing_open()` verifies normalized `DWGPREFIX + DWGNAME`, retries one
  mismatch, and rejects identical basenames under another directory.
  `block_get_attributes()` retries one timeout because it is read-only. No
  mutating command is retried.
- Final live evidence: five tests passed in `82.78s`, including two disposable
  `same-name.dxf` files in different directories.
- Design and plan:
  `docs/superpowers/specs/2026-07-28-file-ipc-active-document-verification-design.md`;
  `docs/superpowers/plans/2026-07-28-file-ipc-active-document-verification.md`.

## Mechanical production review/repair evidence

- State: **Partially verified**
- Date: `2026-07-22`
- Implementation Head SHA: `ddf683431cabf4b4a12c3448aed0a20b7b54d429`
- Design and plan: `docs/superpowers/specs/2026-07-22-mechanical-production-repair-design.md`; `docs/superpowers/plans/2026-07-22-mechanical-production-repair.md`
- Safety behavior: `run` writes `build-evidence.json` bound to the staged DXF
  SHA-256. `mechanical-review` is read-only; `mechanical-repair` requires an
  approval reference, literal `--confirm-repair APPLY`, source/copy hash-verified
  DXF/evidence backups, and a passing post-repair live review before save. A
  failed review closes the modified drawing without save before reopening the
  verified backup.
- Focused tests: `tests/test_cad_agent_live.py` and `tests/test_cad_agent_cli.py` → `7 passed`; coverage includes missing approval refusal, backup creation, successful fake repair, and failed-second-review rollback.
- Live staged review: `cad_agent mechanical-review` on a disposable DXF under `C:\temp` through AutoCAD Mechanical 2027 → `passed=true`, `structural_checked=10`, `geometry_checked=10`, no mismatch or degraded geometry check.
- Authoritative command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` → exit `0`; offline JUnit `tests=299; failures=0; errors=0; skipped=0`; SHA-256 `80140e4ca6c7089742a8282ad0e9cea083ce167c110b91f11cbe3f0d485e3569`
- `real_data`: unavailable-state probe `SKIP` (`tests=1; skipped=1`), SHA-256 `f6b25dd4aa7da9b5c12eaad290bc042061a53b54897fec50d176e9035f0aadb3`; approved private run `NOT RUN`
- `autocad_mechanical`: unavailable-state probe `SKIP` (`tests=4; skipped=4`), SHA-256 `69ba0f74887b47dfb2a09f4a4a670acdead32db67677e63f70b28084f7a402e5`
- Remaining risk: no customer/production drawing was repaired. A real repair remains gated on an approved input, backup verification, explicit operator approval, and a post-repair review.

## Historical File IPC evidence before the AutoCAD Mechanical target change

- State: **Partially verified**
- Date: `2026-07-22`
- Head SHA: `52b92885698827c36984f02e8461f4e18de6072c`
- Command: `CAD_AGENT_FILE_IPC=1`, AutoCAD HWND `393650`, and the locally loaded dispatcher; `& '.\.venv-py311\Scripts\python.exe' -m pytest -m autocad_lt -ra -p no:cacheprovider`
- Result: `4 passed, 296 deselected` in `69.52s`; the run covered active-document access, primitive live review/repair, beam INSERT attribute repair, and five remaining component INSERT repairs.
- Session: AutoCAD Mechanical 2027, process `acad.exe`, HWND `393650`.
- Safety: all smoke DXFs were newly created under `C:\temp`; no production drawing was saved or modified.
- Limit: the then-current marker was `autocad_lt`, so this evidence predates the AutoCAD Mechanical target contract and is retained as historical context only.

## AutoCAD Mechanical 2027 target evidence

- State: **Verified**
- Date: `2026-07-22`
- Implementation Head SHA: `bda0cf0ea094d67bddca65aa8f9df953a4f25078`
- Design and plan: `docs/superpowers/specs/2026-07-22-autocad-mechanical-2027-design.md`; `docs/superpowers/plans/2026-07-22-autocad-mechanical-2027.md`
- Live command: `CAD_AGENT_FILE_IPC=1`, AutoCAD Mechanical HWND `393650`, and the loaded dispatcher; `& '.\.venv-py311\Scripts\python.exe' -m pytest -m autocad_mechanical -ra -p no:cacheprovider` → `4 passed, 296 deselected` in `69.41s`
- Live scope: active-document access, primitive live review/repair, beam INSERT attribute repair, and five remaining component INSERT repairs; every smoke DXF was created under `C:\temp`.
- Session: AutoCAD Mechanical 2027, `acad.exe`, HWND `393650`.
- Authoritative command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` → exit `0`
- Offline JUnit: `tests=295; failures=0; errors=0; skipped=0`; SHA-256 `5d380796e1c5582ee3f1df48b9979853cda782f66ba3268fe8a46f5126b57298`
- `real_data`: unavailable-state probe `SKIP` (`tests=1; skipped=1`); SHA-256 `c2e3927cd97a46b1c45658ec263e5d221cb169a0be3de26a99a5651c9e42d289`; approved private run `NOT RUN`
- `autocad_mechanical`: unavailable-state probe `SKIP` (`tests=4; skipped=4`); SHA-256 `039a06a9c3c6a0a4aa7c6283fae44cd4c44caa04c7809f5bc7ffdbe20146be74`
- Remaining risk: production drawing mutation remains prohibited without a verified backup, explicit human approval, live review, repair, and a second review.

## Foundation certificate

- State: **Verified**
- Date: `2026-07-22`
- Reviewed implementation Head SHA: `a96a31df6a735d103c29548855fa8a170e535c18`
- Command: `.\scripts\verify.ps1`
- Exit code: `0`
- Python: `3.11.9`
- Tesseract executable: `C:\Program Files\Tesseract-OCR\tesseract.exe (tesseract v5.4.0.20240606)`
- Dependencies: `numpy=2.4.6; opencv-python=5.0.0.93; pytesseract=0.3.13; Pillow=12.3.0; pypdf=6.14.2; PyMuPDF=1.28.0; ezdxf=1.4.4; anthropic=0.117.1; python-solvespace=3.0.8; pytest=9.1.1; ruff=0.15.22`
- Offline JUnit: `tests=292; failures=0; errors=0; skipped=0`; SHA-256 `c35bde5ee7f22eeb7489baa7bcabdf3a16b6c89555a079482e0d3d61a41e742c`
- `real_data`: `SKIP` unavailable-state probe; `tests=1; skipped=1`; SHA-256 `b63e0effc175a3854ea6b217d68f894a3fcc0bc7299a5616f6f3d452c2028986`
- `autocad_lt`: `SKIP` unavailable-state probe; `tests=4; skipped=4`; SHA-256 `6818b5d401859ff92ee0b3b3f40891ac320018bdf386aa29bc8fb2cb0aa1bd0c`
- Unexpected warnings: `0`; scoped intentional ROI warning policy remains documented in `docs/QUALITY.md`
- Ruff: `PASS`
- Lock/environment, Git whitespace, and repository content-hash side-effect checks: `PASS`
- Verification transcript SHA-256: `486ec0fe693a209a866e96673a34e249b4496ec3906e35d101e44f538c93de3a`
- Independent review: `docs/reviews/2026-07-22-reproducible-foundation.md`; three final-head reports; unresolved P0/P1 `0`
- Remaining risks: at this historical foundation head, the approved private `real_data`
  gate and then-current live `autocad_lt` gate were not run, and the Agent
  entry points still auto-applied reports. Later sections supersede those
  specific limits with private-data, AutoCAD Mechanical 2027, and Agent
  approval-gate evidence.
