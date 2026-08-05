# R0 Reuse Integration Rebaseline Audit

This audit is the canonical documentation record for the reuse-first
rebaseline. It records evidence and sequencing policy; it does not authorize
runtime implementation.

## 1. Audit identity and exact base SHA

- Task: R0-T6, Issue #44.
- Exact implementation base: `cac38a1cf558aee1245ae669bcc106bf3619b8e5`.
- Approved design merge: `4cc2c0f198484581f5781466e769441d4e7da669`.
- Reuse inventory base: `c325d009c3035be5c3202e3939efd4a82bcd2f42`.
- Architecture baseline base: `db91f3585f20984b7892454b3a5f9a6d2c32a567`.
- Machine-readable inventory: `docs/superpowers/reuse/2026-08-04-reuse-inventory.json`.
- Legacy CLI baseline: `contracts/reuse-integration/legacy-cli-baseline.json`.
- Architecture baseline: `contracts/reuse-integration/architecture-boundaries.json`.
- Approved design: `docs/superpowers/specs/2026-08-04-reuse-first-multisource-cad-reconstruction-design.md`.
- Historical rollout: `docs/superpowers/plans/2026-08-04-visual-supervisor-rollout.md`.
- The audit consumes these machine-readable contracts, the approved design,
  and the historical rollout.

## 2. Inventory validation command and result

The closed inventory contains 20 capability records and is validated with:

```powershell
.\.venv-py311\Scripts\python.exe scripts/reuse_inventory.py check docs/superpowers/reuse/2026-08-04-reuse-inventory.json --repo-root .
```

Result: exit `0` on the exact implementation base. The inventory is
SHA-bound, path-valid, and records current owners, APIs, consumers, tests,
acceptance gates, migration, rollback, inspected paths, and gap reasons.

The supporting R0 compatibility and architecture tests also consume the
existing contracts; the pre-audit focused evidence was `27 passed` for the
inventory, legacy compatibility, and architecture suites.

## 3. Existing capability ownership map

The existing execution engine remains:

```text
primitive_ir_lib -> semantic_ir_lib -> agent_lib -> dxf_builder_lib -> mcp_integration_lib
```

| Capability | Existing owner | Classification |
|---|---|---|
| Image/PDF recognition, OCR, and calibration | `primitive_ir_lib` | `REUSE_AS_IS` |
| Semantic parts, constraints, and solving | `semantic_ir_lib` | `EXTEND_WITH_ADAPTER` |
| Ambiguity proposal and separate apply | `agent_lib` | `EXTEND_WITH_ADAPTER` |
| Native DXF/entity generation | `dxf_builder_lib` | `REUSE_AS_IS` |
| Headless review and repair | `dxf_builder_lib` | `REUSE_AS_IS` |
| AutoCAD File IPC and .NET dispatcher | `mcp_integration_lib` plus `autocad_plugin` | `EXTEND_WITH_TEST` |
| Approved AutoCAD repair | `mcp_integration_lib` plus `dxf_builder_lib` | `EXTEND_WITH_ADAPTER` |
| Run manifest, checkpoint, and resume | `cad_agent` | `EXTEND_WITH_ADAPTER` |
| Drawing Setup | `cad_agent` plus `contracts/drawing-setup` | `REUSE_AS_IS` |
| Dimension Pilot | `cad_agent` plus `contracts/dimension-pilot` | `REUSE_AS_IS` |
| VS-T1 dimension observer | `primitive_ir_lib` plus `cad_agent` | `REUSE_AS_IS` |
| VS-T2 geometry comparator | `primitive_ir_lib` plus `cad_agent` | `REUSE_AS_IS` |
| VS-T3 evidence exporter | `mcp_integration_lib` plus `autocad_plugin` | `REUSE_AS_IS` |
| Source bundle and evidence fusion | none complete | `NEW_MISSING_CAPABILITY` |
| Exact-base component extraction | none complete | `NEW_MISSING_CAPABILITY` |
| Component/view registry | none complete | `NEW_MISSING_CAPABILITY` |
| Candidate revision synchronization | none complete | `NEW_MISSING_CAPABILITY` |
| Independent visual verdict | none complete | `NEW_MISSING_CAPABILITY` |
| Codex repair planning | none complete | `NEW_MISSING_CAPABILITY` |
| Verified promotion | `cad_agent` plus `mcp_integration_lib` | `EXTEND_WITH_ADAPTER` |

## 4. Reuse classifications and reasons

The classifications are intentionally conservative. Recognition, solving,
DXF generation, headless review, Drawing Setup, Dimension Pilot, and the
existing VS-T1 through VS-T3 evidence paths remain authoritative. Adapters
may route new orchestration evidence through those APIs, while tests extend
the existing File IPC boundary without creating a second transport.

The six `NEW_MISSING_CAPABILITY` entries are not substitutes for existing
engines. Each was accepted only after the inventory named inspected paths and
why those paths do not provide the complete missing capability. Verified
promotion is an adapter because backup, review, save/reopen, and rollback
pieces already exist.

## 5. Genuine missing capabilities

The inventory records these precise gaps:

- `source-bundle-fusion`: existing manifests, PDF staging, and AutoCAD
  evidence export are separate boundaries; no complete source-bundle object
  fuses their roles and hashes into one multisource input record.
- `exact-base-component-extraction`: current recognition and DXF building do
  not provide a read-only exact-base component registry bound to source hashes
  and provenance.
- `component-view-registry`: Semantic IR parts and DXF handles are not a
  persistent graph linking one component across overall, detail, section, and
  AutoCAD-native views.
- `candidate-revision-synchronization`: current manifests and checkpoints do
  not coordinate multiple source/view candidates, supersession, and immutable
  artifact hashes as one revision lifecycle.
- `independent-visual-verdict`: geometry comparison and AutoCAD review provide
  separate evidence, but no independent verdict record aggregates them with
  delegated or human approval without becoming self-approval.
- `codex-repair-planning`: agent advice/application and repair executors exist,
  but no non-mutating Codex plan binds visual findings, scope, approvals,
  backups, and executor inputs into one auditable artifact.

## 6. Compatibility baseline

R0-T4's `contracts/reuse-integration/legacy-cli-baseline.json` is the closed
`legacy-cli-baseline-1.0` contract for all 37 commands present at the
implementation base. The historical v1 run-manifest fixture remains readable
with safe `DRAFT_REFERENCE` defaults. The compatibility boundary preserves
`run`, `resume`, `run-pdf`, `resume-pdf`, Drawing Setup, Dimension Pilot, DXF
and headless review, and Mechanical review/repair behavior.

R0-T6 changes no parser, manifest writer, runtime, dependency lock, CLI,
artifact, AutoCAD, repair, verdict, or publication behavior. New workflows
remain opt-in and locked until separately planned and accepted.

## 7. Architecture-ratchet baseline

R0-T5's `contracts/reuse-integration/architecture-boundaries.json` is anchored
to `db91f3585f20984b7892454b3a5f9a6d2c32a567` and records 24 existing
exceptions. The read-only checker covers these rule groups:

```text
DUPLICATE_PACKAGE_NAME
AUTOCAD_API_OUTSIDE_PLUGIN
AUTOCAD_TRANSPORT_OUTSIDE_APPROVED_BOUNDARY
DIRECT_DXF_WRITE_OUTSIDE_DXF_BUILDER
DIRECT_OCR_IMPORT_OUTSIDE_PRIMITIVE_OWNER
SECOND_TRUTH_STORE_NAME
```

The check passes only when current violations are a subset of the committed
baseline. Removed exceptions are informational; new violations are blockers.
The baseline does not silently approve new architecture debt.

## 8. Risks and rollback

The rebaseline is documentation and governance only. The principal risk is
that a historical VS-T4 through VS-T8 requirement is mistaken for an approved
runtime implementation. The old rollout is retained as evidence and explicitly
superseded after VS-T3. Private drawings, generated CAD, credentials, and live
AutoCAD state are outside this audit.

Rollback is one bounded commit revert. Reverting this audit restores the prior
documentation while leaving the machine-readable R0 contracts and runtime
unchanged. Future implementation must first receive a fresh plan, base SHA,
allowlist, tests, Reuse Declaration, and PO review.

## 9. Locked future plan queue

The dependency-ordered queue is:

```text
R0 Reuse Integration Rebaseline
  -> S1 Codex SDK Windows compatibility spike
  -> S2 AutoCAD-native render/plot evidence spike
  -> S3 Exact-base Xref extraction spike
  -> R1 Source Bundle and Fusion Adapter
  -> R2 Base CAD Adapter
  -> R3 Component/View Registry
  -> R4 Candidate Revision Orchestrator
  -> R5 Visual Supervisor Adapter
  -> R6 Repair Executor Adapter
  -> R7 Verified Publisher
  -> R8 Synthetic and real pilots
```

S1, S2, and S3 may be planned or executed independently only when their write
sets are disjoint. R1 through R8 each require a fresh plan against the then-
current integrated `main`, a complete Reuse Declaration, bounded tests, and
their own acceptance review. Queue names are not implementation
authorization. This audit does not authorize runtime work, Task 7, or the old
VS-T4 through VS-T8 tasks.

## 10. Gates not run

- Private-data/real-drawing acceptance: `NOT RUN`.
- AutoCAD Mechanical live acceptance: `NOT RUN`.
- Codex SDK compatibility spike: `NOT RUN`.
- No runtime capability, visual verdict, repair loop, publisher, or future
  subsystem is promoted by this audit.
- Unavailable-state probes may report `SKIP`; they are not acceptance evidence.
