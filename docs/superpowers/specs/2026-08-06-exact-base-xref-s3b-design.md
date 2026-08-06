# S3B Exact-Base Xref File IPC/.NET Live Inspection and Approved Extraction Design

Status: Proposed for PO review. This document authorizes planning only; it does not authorize production implementation or a live AutoCAD run.

Date: 2026-08-06

Governance base: 1ba05ea6d768351fa7106109bcee244e60463527

Governance record: PR #62, formal PO review 4870827849, merged from reviewed head a7fa3f4cdf63f0f36887d0fc26d5580487747520.

## 1. Purpose

S3B establishes the first real AutoCAD Mechanical 2027 execution path for exact-base Xref inspection and approved component extraction. It carries the closed Python contracts from S3A through the existing File IPC, dispatcher, and drawing-gateway boundary, then proves the required checks against a live drawing.

The exact-base source remains read-only throughout the operation. Inspection must establish source identity, source revision, source hash, vehicle identity, critical dimensions, Xref state, component provenance, and database stability. Extraction may mutate only a disposable candidate drawing and may apply only local translation, rotation, and positive uniform scale to components that were already inspected and approved by the S3A extraction plan.

S3B is an execution and evidence boundary. It does not turn the result into a SourceBundle, a fusion decision, a registry record, a repair verdict, or a published drawing.

## 2. Scope and non-goals

In scope:

- A closed File IPC request and result contract for exact-base Xref inspection.
- A closed File IPC request and result contract for approved exact-base extraction.
- Binding the existing S3A validator and extraction-plan builder to the Python IPC client.
- C# request validation, dispatcher routing, and drawing-gateway methods.
- Read-only inspection of the active drawing and its exact-base Xref.
- Native extraction of approved inspected components into a disposable candidate drawing.
- Evidence containing source handle, layer, block, source revision, source hash, transform, and REUSED_FROM_BASE_CAD provenance.
- Fail-closed behavior for identity, dimensions, hashes, component eligibility, target safety, and transform policy.
- Offline tests and a separately gated AutoCAD Mechanical 2027 live acceptance test.

Out of scope:

- R1C source-fusion runtime or SourceBundle consumption.
- Component registry, revision management, repair, verdict, or publication.
- OCR, geometric inference, global stretch, global warp, reflected transforms, or non-uniform scale.
- Mutation of an accepted DWG or mutation of the exact-base source.
- New transport, a second dispatcher, or an alternate AutoCAD integration path.
- Any claim that S3B live evidence passed before the AutoCAD gate has actually run.

## 3. Existing contracts and architecture to reuse

S3A remains the authoritative offline policy layer. The implementation must call the existing functions in mcp_integration_lib/exact_base_xref.py:

- validate_xref_inspection
- validate_extraction_plan
- build_extraction_plan

The existing constants remain authoritative:

- exact-base-xref-inspection-1.0
- exact-base-xref-extraction-plan-1.0
- REUSED_FROM_BASE_CAD
- LOCAL_TRANSLATION_ROTATION_UNIFORM_SCALE_ONLY

The implementation must reuse:

- mcp_integration_lib.dotnet_ipc.DotNetIPCClient
- the existing File IPC directory and request/result envelope
- autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs
- autocad_plugin/CadAgent.AutoCAD2027/Drawing/IDrawingGateway.cs
- the live AutoCadDrawingGateway created by CommandContext

The S3A validator and fixture are not weakened or copied into a second policy implementation. Runtime-only absolute paths may be added to the IPC request because the persisted S3A contract deliberately stores safe relative paths.

## 4. Design decision

Three approaches were considered.

1. Reuse mechanical_bom or review. This would be rejected because those operations do not establish exact-base Xref identity, component eligibility, or approved extraction authority.
2. Add one multi-mode operation with inspection and extraction flags. This would be rejected because a read-only evidence path and a candidate-mutating path need separate approval, safety checks, and result semantics.
3. Add two narrowly scoped operations on the existing IPC and gateway path. This is selected because it makes the read-only gate independently testable and requires explicit approval before candidate mutation.

The selected operations are:

- exact_base_xref_inspection: read-only inspection of the active target drawing and its exact-base Xref.
- exact_base_xref_extraction: extraction of only the components named by a validated and approved S3A plan into a disposable candidate.

No generic mutation operation is introduced. No operation is allowed to overwrite an accepted target.

## 5. Runtime flow

The normal flow is:

1. A caller loads an S3A inspection payload and validates it with validate_xref_inspection.
2. The caller loads or builds the S3A extraction plan and validates it with validate_extraction_plan, including the inspection payload.
3. The caller sends exact_base_xref_inspection with the active target drawing path and hash, the runtime absolute source path, and the validated inspection payload.
4. The dispatcher confirms the active document matches the request, then the gateway inspects the read-only Xref and critical dimensions.
5. The gateway hashes the source before and after inspection, verifies database stability, and returns live evidence. Inspection success requires source hash stability and changed=false.
6. Only after inspection evidence is successful does the caller send exact_base_xref_extraction. The extraction request must carry the same source hash and revision, the validated plan, and an explicit APPROVED approval reference.
7. The dispatcher confirms that the active target is a disposable candidate. The gateway extracts the selected native components using a native database clone transaction and applies each component's local transform.
8. The candidate may be saved only to a new disposable output path. The source Xref is never opened for write and is never saved. An accepted DWG path is never an extraction target.
9. The result contains candidate-only evidence and source provenance. It is not a verdict and cannot be consumed as R1C source-fusion input by this PR.

Inspection and extraction are separate requests. A successful inspection does not imply approval to extract.

## 6. Request contracts

Both operations use the existing IpcRequest envelope. The operation-specific fields are in parameters.

Inspection requires:

- run_id: non-empty request/run identity.
- source_full_path: absolute runtime path to the exact-base source.
- source_revision: exact revision from the S3A source record.
- inspection: the complete S3A inspection payload.
- target_role: INSPECTION_HOST.

Inspection requires approval to be absent. The target drawing is matched by the normal envelope drawing_full_path and drawing_sha256 fields. The source path must not equal the target path.

Extraction requires:

- run_id: the same run identity as the associated inspection evidence.
- source_full_path: the same absolute source path used for inspection.
- source_revision: the exact revision from the validated plan.
- inspection: the complete S3A inspection payload.
- extraction_plan: the complete S3A extraction plan.
- target_role: DISPOSABLE_CANDIDATE.
- candidate_output_path: a new path below the configured disposable root.

Extraction requires approval.status=APPROVED and a non-empty approval reference. The implementation must validate the inspection and plan again at the C# boundary; a caller-provided eligible flag is not authority.

The first S3B implementation supports only inspected BLOCK components whose source handle, layer, and block name can be matched exactly in the live Xref. Unknown component types fail closed.

## 7. Result and evidence contracts

Inspection success returns:

- the validated inspection payload with live-captured values;
- source_sha256_before and source_sha256_after, which must be equal;
- target_sha256_before and target_sha256_after;
- dbmod_before and dbmod_after, which must be equal;
- live Xref name, read_only=true, and status=INSPECTED;
- per-component source handle, layer, block, bounding evidence, and REUSED_FROM_BASE_CAD;
- changed=false and no mutation handles in the IPC envelope.

Extraction success returns:

- plan_id and source revision;
- source_sha256_before and source_sha256_after, which must be equal;
- candidate input and output hashes;
- candidate_output_path under the disposable root;
- per-component source handle, layer, block, provenance, and the applied local transform;
- candidate_changed_during_operation=true only when a candidate mutation occurred;
- save_performed=true only for the new disposable candidate output;
- accepted_target_overwrite=false;
- source_saved=false and source_mutated=false.

The extraction result is candidate evidence only. It must not contain a verdict, publication state, registry identifier, revision assignment, or accepted-DWG status.

## 8. Safety and fail-closed policy

The operation fails closed with a stable error code when any of the following occurs:

- the active document does not exactly match drawing_full_path or drawing_sha256;
- source_full_path is not absolute, cannot be safely opened read-only, or equals any target path;
- source hash before or after differs from the requested hash or from itself;
- source revision differs between request, inspection, and plan;
- vehicle identity, model identity, or any critical dimension is missing, unknown, or not PASS;
- the Xref is absent, not INSPECTED, or not read-only;
- a requested component is absent, duplicated, uninspected, ineligible, or has a source handle/layer/block mismatch;
- a component type is not supported by this S3B implementation;
- a transform has non-positive scale, non-uniform scale, reflection, global scope, or any value outside the S3A policy;
- extraction approval is missing, not APPROVED, or has no reference;
- target_role is not DISPOSABLE_CANDIDATE for extraction;
- candidate_output_path is outside the configured disposable root, already exists, or resolves to an accepted DWG;
- any source or accepted target write/save is attempted;
- a native transaction, hash check, restoration step, or evidence serialization fails.

Failures are returned as unsuccessful IPC results. No partial candidate is accepted, no source is saved, and no retry is allowed to bypass a failed safety check.

## 9. Candidate and transaction rules

Inspection may open and inspect the source through the active read-only Xref but must leave the target drawing and source unchanged.

Extraction operates on a disposable candidate only. The gateway must:

- verify source and candidate identities before opening a transaction;
- resolve source objects from the inspected Xref, not by an unbounded model-space scan;
- clone only the approved source components through the AutoCAD Managed .NET database API;
- apply translation, rotation, and positive uniform scale locally per component;
- keep the source database and Xref read-only;
- save only a newly created candidate output below the disposable root;
- hash the source after the operation and report source_mutated=false;
- close or discard the candidate on any failure before publishing evidence.

The accepted DWG is identified by path and hash, not by a caller-supplied boolean. A path or request that could overwrite it is rejected.

## 10. Acceptance gates

Offline gate:

- S3A validator tests remain green without modification to their policy.
- Python IPC tests cover request construction, schema rejection, path safety, and result evidence.
- C# contract and dispatcher tests cover operation allowlisting, approval, identity, candidate safety, and fail-closed errors.
- No source-fusion, registry, repair, verdict, or publication code is imported by the S3B path.
- scripts/verify.ps1 passes from a clean worktree.

Live gate:

- AutoCAD Mechanical 2027 is running with the approved disposable fixture.
- Autodesk references resolve and the existing File IPC dispatcher is reachable.
- The exact-base source is present at the approved runtime path and its expected hash is independently confirmed.
- Inspection returns successful live evidence with source hash stability, identity PASS, critical dimensions PASS, read-only Xref, and dbmod stability.
- Extraction succeeds only after an APPROVED plan and writes only a new disposable candidate.
- The source hash is unchanged after extraction; the accepted DWG is unchanged and not overwritten.
- Each extracted component has the expected source handle, layer, block, revision, hash, transform, and REUSED_FROM_BASE_CAD provenance.
- The live run records PASS only when all checks execute. Missing AutoCAD, references, fixture, or approved private data is recorded as NOT RUN or SKIP.

## 11. Evidence and governance

The implementation record must identify the exact implementation base, issue, branch, bounded commit, offline test commands, and live gate result. It must explicitly distinguish:

- PASS: the gate actually ran and all assertions passed;
- NOT RUN: the gate was required but its environment was unavailable;
- SKIP: the gate was intentionally excluded by the approved allowlist.

The current governance state remains:

- S3B planning unlocked;
- S3B implementation/live locked until this design and a bounded implementation issue are approved;
- S3C, R1C, registry, revision, repair, verdict, and publication locked.

This design does not unlock any of those items.
