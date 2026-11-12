# CAD Agent Project

## Product baseline

CAD Agent is a Windows engineering workflow for reading modified source drawings,
reusing the ORIGINAL native CAD BASE, applying only source-supported changes to a
disposable candidate, and proving an editable persisted result in AutoCAD Mechanical
2027. Fresh GitHub wins over cached status, historical plans, and local checkouts.

The product roadmap is [#291](https://github.com/duongchi90/cad-agent/issues/291).
The authorized cumulative BVTL product run is accepted and closed in
[#461](https://github.com/duongchi90/cad-agent/issues/461#issuecomment-5915471764).
This acceptance covers eight modifications on one candidate copied from ORIGINAL
BASE, including native geometry, dimensions/annotations, hatch representation,
protected-state comparison, editability, and save/reopen/readback. Historical target
DXFs and prior candidates are evidence, never generation inputs.

## What is packaged and what is orchestrated

Current main contains source/provenance validators, geometry and dimension
inspection, native CAD query/edit interfaces, FileIPC/.NET dispatch, staged DXF
tools, and regression infrastructure. The accepted cumulative run also uses the
authorized local executor's source reasoning and bounded native COM/AutoLISP
operations. It is not evidence of a single unattended CLI that solves arbitrary
drawings. New drawings require source-specific scope and acceptance evidence.

The image/PDF -> Primitive IR -> Semantic IR -> staged DXF pipeline remains
available for inspection, reconstruction experiments, and regression. Its output
does not acquire the native workflow's acceptance merely by being generated.
Optional provider experiments are separate; PR #340 remains frozen. A completed
BVTL run does not authorize another product phase or provider/billing work.

## Native operator workflow

Start with ORIGINAL native CAD and the modification PDF/image. Bind each exact
input by absolute path and SHA-256, inspect the source, and keep a source-supported
plan outside Git. Do not use a completed target DWG/DXF, answer manifest, or prior
accepted candidate to derive edits. Evaluator access starts only after candidate
generation is complete and its persisted bytes and plan are frozen. The controlled
holdout [#463](https://github.com/duongchi90/cad-agent/issues/463) adds a
`SAME_BASE_NEW_DELTA_SIGNAL_ONLY` result; it does not prove unseen-drawing support.

Use the existing owners below. There is no native modification subcommand in
`python -m cad_agent`; `run` and `run-pdf` are the staged reconstruction path.

| Step | Existing interface and required evidence |
| --- | --- |
| Prepare | Run the README bootstrap/verification commands and `python -m cad_agent doctor --json`. Read the [runtime inventory](operations/runtime_environment_inventory.md) before any live request; doctor does not prove a loaded plugin or correct active drawing. |
| Bind and inspect | `mcp_integration_lib.dotnet_ipc.DotNetIPCClient.exact_base_xref_inspection(drawing_full_path, drawing_sha256=..., source_full_path=..., inspection=...)` validates an existing `mcp_integration_lib.exact_base_xref.validate_xref_inspection` packet. Direct-native inspection uses `xref=None`, exact same source/active path, current hash and read-only evidence; do not invent an Xref name or use direct-native extraction. |
| Read bounded facts | `cad_agent.drawing_query.observe_drawing` and `query_entities` consume existing reference/current-observation, registry and candidate-state bindings. `cad_agent.native_dwg_provenance.compose_native_dwg_query_binding` composes the supported full-DWG/staged-DXF readback profile; its candidate format is DXF, so it is not a generic DWG-to-DWG binding recipe. See the [native provenance examples](../tests/test_cad_agent_native_dwg_provenance.py) and [bounded query examples](../tests/test_cad_agent_drawing_query.py). |
| Infer the bounded delta | Align evidenced target observations to native BASE anchors; preserve unobserved geometry. `cad_agent.source_fusion_proposal.compose_verified_native_line_delta` takes verified target materialization, exact render/support/calibration bindings, base line observations, units, tolerances and verified alignment anchors. Its output is `PROPOSAL_ONLY`, with no CAD mutation; ambiguous matches yield no deltas. [Examples](../tests/test_external_visual_primitive_ir_admission.py) exercise translated sheets and reject unproven scale changes. |
| Prepare a candidate | Copy ORIGINAL BASE exclusively into a disposable directory under `D:\Cad agent temp`; `cad_agent.live._copy_to_exclusive_backup` is the existing exclusive-copy owner. Preserve source/BASE/accepted bytes. The native edit requires protected Windows directory/file custody; an arbitrary writable temp directory is insufficient. Bind the actual candidate with the existing `cad_agent.drawing_artifact_reference` owner and fresh native observation evidence. |
| Request an existing edit | `DotNetIPCClient.bounded_native_line_edit(candidate_path, candidate_reference=..., current_observation=..., parameters=...)` accepts the current R3 candidate reference and observation. [Parameters](../contracts/autocad-ipc/operations/bounded-native-line-edit.schema.json) contain `targets` (native handle, observed `before`, evidenced `after`) and `protected` (handle, observed `before`); LINE endpoints are native 3D drawing coordinates. Resolve handles from the current candidate, never the evaluator. This packaged operation edits existing ModelSpace LINEs only. |
| Verify persistence | Inspect the result's `durable_state`, saved hash, native targets and protected readback. Re-read, save, close and reopen the exact same disposable candidate through its existing native owner, then collect fresh persisted geometry, applicable dimension/text/visual evidence and write-enabled native-object probes. The [native save regression](../mcp_integration_lib/tests/test_bounded_native_line_edit_live.py) documents the operation's opt-in oracle; it mutates only an explicitly admitted disposable fixture. |
| Decide PASS | Require source-supported scope, no unsupported/outside-scope delta, native geometry/visual evidence, applicable dimension/text/representation evidence, editability, exact save/reopen identity and deterministic protected-state verification. A successful request or `SAVED` response alone is insufficient. Preserve the plan, corrections, inputs, results and hashes together, as in #461/#463. |

Native dimensions, annotations and hatch corrections in #461 used authorized
bounded COM/AutoLISP operations. They are not covered by the LINE edit interface;
their scopes, helpers and native/persisted readbacks remain in the accepted evidence
packet routed by [STATUS](STATUS.md). Reuse those operations only when current
source evidence requires them; no drawing-specific packaged capability is implied.

On interruption, classify the first failed boundary before another action. In
#461, an immediate file-hash sharing lock and a post-close null COM Documents
getter interrupted observation, while native save and persisted identity remained
valid. Inspect the existing disk/session result, wait for the specific transient
read prerequisite or reacquire the same session, and confirm full-path identity
before continuing. Never replay an edit because an acknowledgement, hash read, or
COM getter failed. A failed/uncertain rollback is terminal non-PASS; retain the
backup and evidence and use the existing recovery owner.

Path/session/custody changes require fresh bindings even when bytes and engineering
facts are unchanged. Alternate DPI, margins or render placement require new
render/ROI/calibration/support evidence before use; an old raster binding is not
portable. Calculated native cache differences require a causal read-only witness,
as in #463, rather than blanket protected-field exclusions. Missing or unrun
evidence remains `SKIP`/`NOT RUN`, never PASS.

## Supported environment

- Windows
- Python 3.11
- AutoCAD Mechanical 2027
- Tesseract 5.4.0.20240606

## Product principles

- Incremental hardening: existing owner plus the smallest necessary surface.
- Source and ORIGINAL BASE identity precede candidate mutation.
- Preserve source, BASE, accepted DWGs, manifests, hashes, and audit evidence.
- Geometry/visual evidence precedes applicable dimension/text checks; finish
  editability/readback, save/reopen, and deterministic verification on the same candidate.
- Missing prerequisites, uncertainty, `SKIP`, and `NOT RUN` never become PASS.
- Runtime changes need causal/reachability evidence and the applicable independent
  exact-head Security and Integration review under #305/#392/#429.
- No GUI, web service, or VPS is part of this supported baseline.

## Canonical references and history

- Current owners: `docs/ARCHITECTURE.md`
- Accepted product/evidence routing: `docs/STATUS.md`
- Verification: `docs/QUALITY.md`; `scripts/bootstrap.ps1`; `scripts/verify.ps1`
- Execution authority: latest #305/#429 and `docs/AI_OPERATING_MODEL.md`
- Historical design/plan policy: `docs/superpowers/README.md`
- Prior project snapshot: [historical PROJECT](history/project-before-bvtl-consolidation.md)

The historical Drawing Initialization Gate and M0-M8/R0-R8 plans remain records of
their own contracts and tests. Unchecked tasks and old frontier statements are not
the current product queue. Fresh #291 and accepted #461 define this closure.
