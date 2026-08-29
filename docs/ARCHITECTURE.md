# CAD Agent Architecture

## Current data flow

```text
Image/PDF
  -> primitive_ir_lib       (geometry, text, tables, calibration -> Primitive IR)
  -> semantic_ir_lib        (parts, compounds, constraints, pruning, solving)
  -> agent_lib              (optional audited advice for ambiguous cases)
  -> dxf_builder_lib        (DXF build -> headless review -> headless repair)
  -> mcp_integration_lib    (AutoCAD Mechanical 2027 live review/repair through File IPC)
```

The phase number is not the call order in every entry point. In particular,
`agent_lib` may advise between semantic analysis and DXF generation.

## Package boundaries

### `primitive_ir_lib`

Consumes images or rendered PDF pages. Produces `PrimitiveIRDocument` with
geometry, text, source trace, confidence, and calibration. `run_image.py` and
`run_pdf.py` are file-oriented entry points. Calibration that has not been
human-verified must not be reused as verified production scale.

### `semantic_ir_lib`

Consumes Primitive IR. Produces `SemanticIRDocument` containing
single-primitive parts, compound parts, and pruned, solver-ready constraints.
Assembly keeps the raw detections in memory long enough for compound inference,
then calls `prune_constraints()` before serialization so quadratic pairwise
noise is not persisted. `prune_constraints()` still returns a separate
`PruneResult`, while `solve_constraints()` returns a separate `SolveResult`
with `solved_primitives`; solved coordinates are never written back into
`SemanticIRDocument` automatically.

### `agent_lib`

Consumes ambiguous Primitive/Semantic IR plus optional image evidence.
`run_agent()` produces an `AgentReport` without mutating the IR, and
`apply_agent_report()` is the separate mutation API. `agent_lib.run` and the
synthetic demo are advisory and non-mutating by default. The file runner
applies actions only in a second invocation against a saved report. The
operator supplies `--confirm-agent-actions APPLY`, a non-empty
`--agent-action-approval`, the report SHA-256, and the approved source,
Primitive IR, and Semantic IR SHA-256 values. `agent_application.json` records
those hashes, the action-set hash, the applied-action hash, and any
post-application solve status. Approved constraint changes are pruned and
solved again before DXF generation. This in-memory IR gate does not authorize
production AutoCAD mutation.

### `dxf_builder_lib`

Consumes Primitive IR, optional solved coordinates, and Semantic IR. Builds DXF
with handles and semantic layers/components. Reviewer #1 checks translation from
intended IR/build output to DXF; Repair #1 fixes confirmed translation defects
and is followed by another review.

### `mcp_integration_lib`

Connects the built DXF to AutoCAD Mechanical 2027 through a live client or File IPC. Reviewer
#2 and Repair #2 operate on AutoCAD-side entities by handle. Live tests require
an explicit local AutoCAD Mechanical 2027 session and never run silently in ordinary CI.
Raw-LISP document activation is accepted only when the normalized full
`DWGPREFIX + DWGNAME` equals the requested path.

## Contracts

- `primitive_ir.schema.json`: primitive geometry/text/calibration contract.
- `semantic_ir.schema.json`: semantic parts and constraints contract.
- `agent_ir.schema.json`: proposed actions and audit-trail contract.
- DXF entity handles connect build evidence to headless and AutoCAD Mechanical review.

Each phase writes or accepts a stable artifact so a later phase can be rerun
without reprocessing the original image.

### Drawing Setup contracts and provenance

The Drawing Initialization Gate adds orchestration and verification contracts
for a Drawing Definition, Drawing Profile, Domain Pack, template manifest,
setup plan, read-only setup audit, and setup evidence. Their configurable
values and provenance are hash-bound. An authoritative drawing path must
present `SETUP_VERIFIED` evidence before geometry creation; the existing
image/PDF path remains `DRAFT_REFERENCE` until that separate dimension-first
path exists.

### Visual Supervisor contract boundary

VS-T0 contract-only slice: the Visual Supervisor contract boundary is pure
Python and does not execute a visual loop.

The Visual Supervisor contract boundary is pure Python and contract-only in
VS-T0. It defines dimension, comparison, independent visual review,
repair-plan, region-verification, run-manifest, and run-scoped
publication-authorization artifacts. Codex cannot self-approve visual fidelity
or publication. No model call, image comparator, AutoCAD evidence operation,
repair loop, or publisher is implemented by VS-T0; those remain later slices.

The `visual_review` artifact is the only contract allowed to carry a visual
verdict. Repair plans describe bounded operations but have no PASS or publish
authority. Evidence hashes and gate contracts fail closed on stale or
unresolved critical data.

New image/PDF run manifests record `release_profile="DRAFT_REFERENCE"`,
`authoritative_release_eligible=false`, and `drawing_setup_evidence=null`.
Historical manifests that predate these fields receive the same safe defaults
when read; an explicit conflicting release claim is rejected rather than
silently downgraded.

This is orchestration and verification behavior: it does not move CAD
algorithms into `cad_agent` and does not replace the .NET/File IPC boundary.
`cad_agent` validates contracts and evidence, while the AutoCAD-side audit
continues through the existing File IPC boundary. Package ownership remains
unchanged.

### Personal Lean Dimension Pilot adapter

The offline Dimension Pilot is a narrow adapter, not a second CAD pipeline.
`cad_agent.dimension_pilot` validates the hash-bound approved plan and fresh
`SETUP_VERIFIED` evidence, converts the approved datum frame to solver-local
coordinates, and supplies approved driving lengths plus one explicit datum
anchor to the existing `semantic_ir_lib` SolveSpace boundary. It does not infer
attachments from proximity, OCR, or DWG content.

Closed solved geometry is converted back to world coordinates and routed
through the existing `dxf_builder_lib` native `DIMENSION` builder and headless
read-back reviewer. The CLI keeps candidate DXF and evidence outputs outside
the repository and always records Mechanical acceptance as `NOT_RUN`.
Offline readiness does not reorder or bypass acceptance: Gate A Drawing Setup
remains before Gate B dimension acceptance, and Gate C expansion remains after
both.

## Safety boundaries

- Unverified calibration or ambiguous recognition stops at a human approval
  boundary.
- Headless review/repair completes before AutoCAD Mechanical mutation.
- Production DXF repair requires a backup and explicit user approval.
- A production backup is valid only when the source hash is stable across the
  copy and equals the copied hash. Failed repair closes without save before a
  verified backup is reopened.
- Real drawings, private annotations, credentials, and API keys stay outside
  Git.

## Orchestrator boundary

The thin `cad_agent` package owns environment reporting, image/PDF run
manifests, atomic checkpoints, calibration-approval recording, resumability,
and staged evidence. Its `run` command delegates the deterministic
image-to-DXF path, while `run-pdf` renders every PDF page and records separate
Primitive IR, Semantic IR, DXF, and build-evidence checkpoints for each page.
`resume` and `resume-pdf` verify the input SHA-256 before they reuse any
checkpoint. It contains no recognition or CAD algorithms.

The ordinary `cad_agent run` and `run-pdf` commands produce staged artifacts
only. Agent application remains a separate hash-bound `agent_lib.run`
invocation. `mechanical-review` reads a SHA-bound `BuildResult` evidence record
through File IPC, while `mechanical-repair` requires an approval reference,
literal operator confirmation, a verified DXF/evidence backup, and a passing
second review before it saves. Existing package APIs remain the authority for
the underlying review and repair behavior.

The private fidelity path is also orchestrated by `cad_agent`, but it remains a
paper-coordinate review profile rather than a production model. After
composition, `fidelity-promote` records a delegated visual approval, the
region/composition/DXF hashes, and an expected structural signature in the
fidelity manifest. `fidelity-mechanical-review` opens only that promoted DXF,
compares the read-only AutoCAD type/layer signature, and records a page
checkpoint. It never saves, repairs, or exports. Fidelity artifacts remain
rejected by the ordinary Mechanical repair flow.

The fidelity review extensions for OCR/table text, linear dimensions, dashed
linetypes, and hatch fills are independently hash-bound. Their approval files
bind the source observation and base DXF, and their outputs remain revisioned
`needs_review` candidates. They do not authorize model export, production
repair, or a visual-fidelity pass by themselves.

## Historical reference

`CAD-Agent-Kien-Truc-v1_3.md` and `HANDOFF.md` preserve detailed implementation
history. They are evidence, not the current status ledger.

The approved design is
`docs/superpowers/specs/2026-08-02-cad-agent-complete-design.md`; the executing
M2 record is `docs/superpowers/plans/2026-08-02-m2-drawing-initialization-gate.md`.

## Reuse-first multisource reconstruction rebaseline

The approved reuse-first design is
[`docs/superpowers/specs/2026-08-04-reuse-first-multisource-cad-reconstruction-design.md`](superpowers/specs/2026-08-04-reuse-first-multisource-cad-reconstruction-design.md).
The machine-readable inventory is
[`docs/superpowers/reuse/2026-08-04-reuse-inventory.json`](superpowers/reuse/2026-08-04-reuse-inventory.json),
the audit is
[`docs/superpowers/reuse/2026-08-04-reuse-integration-audit.md`](superpowers/reuse/2026-08-04-reuse-integration-audit.md),
and the governing R0 plan is
[`docs/superpowers/plans/2026-08-04-reuse-integration-rebaseline.md`](superpowers/plans/2026-08-04-reuse-integration-rebaseline.md).

The existing `primitive_ir_lib -> semantic_ir_lib -> agent_lib ->
dxf_builder_lib -> mcp_integration_lib` packages remain the execution engine.
Future additions are orchestration-level adapters around those authorities;
they do not replace or duplicate recognition, solving, DXF generation, repair,
or AutoCAD transport.

VS-T3 deterministic projection remains structural/offline evidence for entity
mapping, region identity, and diagnostics. It is not automatically final
visual truth. When final fidelity depends on display or plot behavior,
AutoCAD-native render/plot evidence remains behind the existing File IPC
boundary.

The names R1-R8 describe a historical dependency map and prior locking model.
They do not authorize implementation by themselves.

## Lean Rebaseline — active forward architecture

The Human Owner approved the Lean Rebaseline under Issue #295. It changes
forward product prioritization and abstraction admission only. It does not
replace the accepted runtime engine, safety evidence, or standing Human/SOL/Luna
operating model.

The standing governance references remain Issue #131 comments `5396800691`,
`5419064061`, `5442771213`, `5443060158`, with #131 as historical control
ledger and #294 as the active successor. Every new capability built under this
architecture still requires the existing fresh-read, valid writer lease,
`PRE_ISSUANCE_GATE_V1`, long-horizon Luna mission, reuse-first/TDD/evidence,
review, live/private and acceptance rules.

### One engine, one AutoCAD route

The five package owners above remain authoritative. Future work must compose
those owners before creating a new subsystem. AutoCAD Mechanical execution must
continue through one canonical repository-owned request/result route. A second
executor, transport, dispatcher, ACK protocol, IPC root/store, or parallel
result authority is prohibited unless a fresh current architecture decision,
issued through the standing control model, proves the existing owner cannot
satisfy a measured requirement.

### Abstraction admission rule

Before creating a new top-level contract, registry, state machine, authority
store, publisher, long-lived evidence type, or orchestration subsystem:

1. first try to enforce the invariant in the existing owner;
2. then try a thin adapter or validator;
3. require a deterministic failing test, benchmark case, or measured
   operational bottleneck showing why those options are insufficient;
4. require the new abstraction to remove more complexity than it adds.

Without that evidence, freeze/defer the proposed abstraction rather than
building it speculatively.

This admission rule does not relax engineering process. Once a new capability
is justified, it is still implemented under the full existing Human/SOL/Luna
working principles.

### Conceptual evidence consolidation

For product reasoning, prefer three conceptual durable groups:

```text
JobManifest
  -> input/source identities, approved engineering inputs, configuration, run state

CandidateArtifact
  -> candidate identity/path/hash/revision, provenance, changed scope

VerificationEvidence
  -> deterministic checks, AutoCAD evidence, visual/engineering findings,
     approval and rollback references
```

This is a conceptual simplification target only. It does not authorize deleting,
merging, migrating, or weakening accepted schemas/contracts. Existing accepted
types remain until a separately authorized measured simplification task proves
migration is safer and cheaper than retaining them.

### Active product order

Forward architecture work is justified by the active milestones in
`docs/PROJECT.md`:

M0 Stabilize the Pipe -> M1 Golden Path -> M2 Benchmark -> M3 Repair Loop ->
M4 Production Hardening.

Earlier R/P/VS/M/S plans remain historical evidence. They may be reused when a
current milestone and fresh Issue/authority identify them as the smallest
correct owner, but their existence alone no longer creates sequencing pressure
or implementation authority.

The approved Lean Rebaseline design is
`docs/superpowers/specs/2026-08-29-lean-rebaseline-design.md` and its bounded
execution plan is
`docs/superpowers/plans/2026-08-29-lean-rebaseline.md`.
