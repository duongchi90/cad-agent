# CAD Agent Architecture

## Current data flow

```text
Image/PDF
  -> primitive_ir_lib       (geometry, text, tables, calibration -> Primitive IR)
  -> semantic_ir_lib        (parts, compounds, constraints, pruning, solving)
  -> agent_lib              (optional audited advice for ambiguous cases)
  -> dxf_builder_lib        (DXF build -> headless review -> headless repair)
  -> mcp_integration_lib    (AutoCAD LT live review/repair through File IPC)
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
single-primitive parts, compound parts, and detected constraints only.
`prune_constraints()` returns a separate `PruneResult`; `solve_constraints()`
returns a separate `SolveResult` with `solved_primitives`. Neither result is
automatically written back into `SemanticIRDocument`.

### `agent_lib`

Consumes ambiguous Primitive/Semantic IR plus optional image evidence.
`run_agent()` produces an `AgentReport` without mutating the IR, and
`apply_agent_report()` is the separate mutation API. The existing
`agent_lib.run` automatically calls `apply_agent_report()` for all returned actions without a human approval prompt; the demo entry points do the same. They are not an approved production mutation path. This foundation records that boundary and
does not change the behavior.

### `dxf_builder_lib`

Consumes Primitive IR, optional solved coordinates, and Semantic IR. Builds DXF
with handles and semantic layers/components. Reviewer #1 checks translation from
intended IR/build output to DXF; Repair #1 fixes confirmed translation defects
and is followed by another review.

### `mcp_integration_lib`

Connects the built DXF to AutoCAD LT through a live client or File IPC. Reviewer
#2 and Repair #2 operate on AutoCAD-side entities by handle. Live tests require
an explicit local AutoCAD LT session and never run silently in ordinary CI.

## Contracts

- `primitive_ir.schema.json`: primitive geometry/text/calibration contract.
- `semantic_ir.schema.json`: semantic parts and constraints contract.
- `agent_ir.schema.json`: proposed actions and audit-trail contract.
- DXF entity handles connect build evidence to headless and AutoCAD LT review.

Each phase writes or accepts a stable artifact so a later phase can be rerun
without reprocessing the original image.

## Safety boundaries

- Unverified calibration or ambiguous recognition stops at a human approval
  boundary.
- Headless review/repair completes before AutoCAD LT mutation.
- Production DXF repair requires a backup and explicit user approval.
- Real drawings, private annotations, credentials, and API keys stay outside
  Git.

## Planned orchestrator boundary

A thin `cad_agent` package will eventually own environment checks, run
manifests, checkpoints, approvals, resumability, and evidence reports. It will
call the package APIs above and contain no recognition or CAD algorithms. It is
not implemented in this slice.

## Historical reference

`CAD-Agent-Kien-Truc-v1_3.md` and `HANDOFF.md` preserve detailed implementation
history. They are evidence, not the current status ledger.
