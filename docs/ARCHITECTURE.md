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
