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

1. A caller loads the S3A offline inspection and extraction plan and validates them with validate_xref_inspection and validate_extraction_plan. These records provide expectations and component selection; they are not live authority.
2. The caller projects only the whitelisted immutable expectations into the IPC request. The request must not contain live-owned observed values, status, eligible, changed, DBMOD, live bounds, or live timestamps.
3. The caller sends exact_base_xref_inspection with the active target drawing path and hash, the runtime source expectation, and the expectation projection.
4. The dispatcher confirms the active document and server-owned path policy. The gateway reads AutoCAD and builds a new S3A-compatible live inspection result from scratch.
5. The gateway computes every live-owned field, including observed values, PASS/FAIL status, eligibility, DBMOD, bounds, Xref state, and before/after hashes. It does not echo caller evidence into the result. The fresh result is validated with the S3A validator before success is returned.
6. An extraction request carries the validated offline plan and expectations, but a prior successful inspection payload or run_id does not authorize mutation. Immediately before opening any mutation transaction, extraction runs the complete live preflight again and builds a fresh inspection result bound to the current source hash, target identity, plan, and server path policy.
7. Only a successful fresh preflight and exact approval binding allow the gateway to extract selected native components using a native database clone transaction and apply each component's local transform.
8. The candidate may be saved only to a new disposable output path. The source Xref is never opened for write and is never saved. An accepted DWG path is never an extraction target.
9. The result contains candidate-only evidence and source provenance. It is not a verdict and cannot be consumed as R1C source-fusion input by this PR.

Inspection and extraction are separate requests. A previous inspection result, matching run_id, caller-provided eligible flag, or validated offline payload can never bypass the extraction preflight.

## 6. Request contracts

Both operations use the existing IpcRequest envelope. The operation-specific fields are in parameters. The request is an assertion of expectations; the server owns all live observations and safety decisions.

Inspection requires:

- run_id: non-empty request/run identity.
- source_full_path: absolute runtime source expectation, checked against the server-owned source configuration.
- source_revision: exact revision expectation from the S3A source record.
- inspection_expectations: a closed projection containing source identity, vehicle/model expectations, critical-dimension nominal values and tolerances, Xref name, and the selected component source handle/layer/block identities.
- target_role: INSPECTION_HOST, treated as an assertion and not as authority.

Inspection requires approval to be absent. The target drawing is matched by the normal envelope drawing_full_path and drawing_sha256 fields. The source path must not equal the target path.

inspection_expectations must reject and never accept these live-owned fields from the caller: observed, status, eligible, changed, dbmod_before, dbmod_after, live bounds, live hashes, and live timestamps. The server creates those fields from AutoCAD and the file system.

Extraction requires:

- run_id: the same run identity as the associated offline planning record.
- source_full_path: absolute runtime source expectation, checked against the server-owned source configuration.
- source_revision: the exact revision expectation from the validated plan.
- inspection_expectations: the same closed expectation projection used for inspection.
- extraction_plan: the complete S3A extraction plan.
- target_role: DISPOSABLE_CANDIDATE, treated as an assertion and not as authority.
- candidate_output_path: a new path below the configured disposable root.

Extraction requires envelope approval.status=APPROVED and a non-empty approval reference. extraction_plan.approval must also be exactly APPROVED and must be byte-for-byte equal to the envelope approval object after canonical JSON normalization, including status, reference, and any permitted approval fields. The implementation must validate the offline plan again at the C# boundary; a caller-provided live inspection, eligible flag, or approval boolean is not authority.

The first S3B implementation supports only BLOCK components whose source handle, layer, and block name are expectations that can be matched exactly in the fresh live Xref. Unknown component types fail closed.

For both operations, drawing_full_path in the request identifies the active document only. The server canonicalizes it and confirms the active AutoCAD document has the same final path and file identity. It is not a caller-selected output authority.

## 7. Trusted path authority

The trusted path policy is created once by CommandContext from server-side process configuration. The request cannot supply or override these values. The required configuration is:

- CAD_AGENT_S3B_DISPOSABLE_ROOT: the only allowed root for the active candidate input and new candidate output.
- CAD_AGENT_S3B_ACCEPTED_DWG_PATH: the accepted DWG path that extraction must never overwrite.
- CAD_AGENT_S3B_ACCEPTED_DWG_SHA256: the expected hash of the accepted DWG.
- CAD_AGENT_S3B_EXACT_BASE_SOURCE_PATH: the approved exact-base source path.
- CAD_AGENT_S3B_EXACT_BASE_SOURCE_SHA256: the approved exact-base source hash.
- CAD_AGENT_S3B_EXACT_BASE_SOURCE_REVISION: the approved exact-base source revision.

Missing, malformed, unreadable, or contradictory configuration fails closed before AutoCAD inspection. The server records the configuration identity in evidence without exposing private drawing contents.

Canonicalization is handle-based, not a lexical prefix check. For every existing root, source, target, accepted path, and candidate parent, the server resolves the final path from an open Windows file handle, compares paths case-insensitively, and compares volume/file identity where the path exists. Any junction, symlink, mount-point, or other reparse point in a controlled path is rejected. A new output path is canonicalized through its existing parent handle, must remain beneath the resolved disposable root, must not already exist, and must not resolve to the source or accepted file identity. Candidate input and output must both be canonically contained by the disposable root. Source and accepted paths are rejected even when an alias or case variant is used.

## 8. Result and evidence contracts

Inspection success returns:

- a fresh S3A-compatible live_inspection payload built by the server, never the caller's inspection_expectations;
- source_sha256_before and source_sha256_after, which must be equal;
- target_sha256_before and target_sha256_after;
- dbmod_before and dbmod_after, which must be equal;
- live Xref name, read_only=true, and status=INSPECTED;
- per-component source handle, layer, block, bounding evidence, and REUSED_FROM_BASE_CAD;
- drawing_full_path set to the server-canonical active target path;
- changed=false and entity_handles=[] in the IPC envelope because inspection does not mutate a drawing.

Extraction success returns:

- plan_id and source revision;
- the fresh live preflight inspection digest and current source/target identity;
- source_sha256_before and source_sha256_after, which must be equal;
- candidate input and output hashes;
- candidate_output_path under the disposable root;
- per-component source handle, layer, block, provenance, and the applied local transform;
- source_handle_to_candidate_handle mappings for every extracted component;
- drawing_full_path set to the server-canonical active candidate input path;
- changed=true exactly when the candidate mutation was committed to the new disposable output;
- entity_handles containing the sorted candidate handles created by native extraction, never source handles;
- candidate_changed_during_operation=true only when a candidate mutation occurred;
- save_performed=true only for the new disposable candidate output;
- accepted_target_overwrite=false;
- source_saved=false and source_mutated=false.

If extraction fails or cleanup removes a partial candidate, changed=false and entity_handles=[] are returned. Source handles are never placed in the envelope entity_handles field. The extraction result is candidate evidence only. It must not contain a verdict, publication state, registry identifier, revision assignment, or accepted-DWG status.

## 9. Safety and fail-closed policy

The operation fails closed with a stable error code when any of the following occurs:

- the active document does not exactly match drawing_full_path or drawing_sha256;
- source_full_path is not the server-configured source, cannot be safely opened read-only, or equals any target path after final-path/file-identity comparison;
- source hash before or after differs from the requested hash or from itself;
- source revision differs between request, inspection, and plan;
- vehicle identity, model identity, or any critical dimension is missing, unknown, or not PASS;
- the Xref is absent, not INSPECTED, or not read-only;
- a requested component is absent, duplicated, uninspected, ineligible, or has a source handle/layer/block mismatch;
- a component type is not supported by this S3B implementation;
- a transform has non-positive scale, non-uniform scale, reflection, global scope, or any value outside the S3A policy;
- extraction approval is missing, not APPROVED, or has no reference;
- extraction_plan.approval is not an exact canonical match for the envelope approval;
- extraction begins without a fresh full live preflight immediately before the mutation transaction;
- target_role is not DISPOSABLE_CANDIDATE for extraction;
- server path configuration is missing or candidate input/output is outside the resolved disposable root, already exists, crosses a reparse point, or resolves to the source or accepted file identity;
- drawing_full_path, changed, or entity_handles does not follow the operation semantics;
- source_handle_to_candidate_handle evidence is missing or does not match native-created candidate handles;
- any source or accepted target write/save is attempted;
- a native transaction, hash check, session restoration, partial-output cleanup, or evidence serialization fails.

Failures are returned as unsuccessful IPC results. No partial candidate is accepted, no source is saved, and no retry is allowed to bypass a failed safety check.

## 10. Candidate, session, and transaction rules

Inspection may open and inspect the source through the active read-only Xref but must leave the target drawing and source unchanged.

Extraction operates on a disposable candidate only. The gateway must:

- capture the active document final path/file identity, active layout, current view/UCS state, and open transaction state before the operation;
- verify source and candidate identities before opening a transaction;
- run the complete live preflight again immediately before the mutation transaction;
- resolve source objects from the inspected Xref, not by an unbounded model-space scan;
- clone only the approved source components through the AutoCAD Managed .NET database API;
- apply translation, rotation, and positive uniform scale locally per component;
- keep the source database and Xref read-only;
- save only a newly created candidate output below the disposable root;
- hash the source after the operation and report source_mutated=false;
- close or discard the candidate on any failure before publishing evidence;
- in a finally-protected session guard, close transactions, restore the original active document and layout/view/UCS state, and fail the operation if restoration cannot be proven;
- delete only the operation's own newly-created partial candidate output after closing it, after rechecking its canonical path and file identity; never perform recursive cleanup or delete an existing accepted/source file.

The accepted DWG is identified by path and hash, not by a caller-supplied boolean. A path or request that could overwrite it is rejected.

## 11. Acceptance gates

Offline gate:

- S3A validator tests remain green without modification to their policy.
- Python IPC tests cover request construction, schema rejection, path safety, and result evidence.
- C# contract and dispatcher tests cover operation allowlisting, caller/live field separation, exact approval binding, identity, server-owned path safety, candidate safety, result semantics, and fail-closed errors.
- No source-fusion, registry, repair, verdict, or publication code is imported by the S3B path.
- scripts/verify.ps1 passes from a clean worktree.

Live gate:

- AutoCAD Mechanical 2027 is running with the approved disposable fixture.
- Autodesk references resolve and the existing File IPC dispatcher is reachable.
- The exact-base source is present at the approved runtime path and its expected hash is independently confirmed.
- Inspection returns successful fresh live evidence with source hash stability, identity PASS, critical dimensions PASS, read-only Xref, and DBMOD stability; no caller-owned observed/status/eligible/changed/DBMOD field is echoed.
- Extraction performs the same full live preflight immediately before mutation, even when a prior inspection succeeded, and succeeds only after an exact APPROVED plan/envelope binding.
- Candidate input/output path authority is server-side, canonicalized, reparse-safe, and proven separate from source and accepted DWG.
- The source hash is unchanged after extraction; the accepted DWG is unchanged and not overwritten.
- Each extracted component has the expected source handle, candidate handle mapping, layer, block, revision, hash, transform, and REUSED_FROM_BASE_CAD provenance.
- Active-document/session restoration and partial-output cleanup are evidenced.
- The live run records PASS only when all checks execute. Missing AutoCAD, references, fixture, or approved private data is recorded as NOT RUN or SKIP.

## 12. Evidence and governance

The implementation record must identify the exact implementation base, issue, branch, bounded commit, offline test commands, and live gate result. It must explicitly distinguish:

- PASS: the gate actually ran and all assertions passed;
- NOT RUN: the gate was required but its environment was unavailable;
- SKIP: the gate was intentionally excluded by the approved allowlist.

The current governance state remains:

- S3B planning unlocked;
- S3B implementation/live locked until this design and a bounded implementation issue are approved;
- S3C, R1C, registry, revision, repair, verdict, and publication locked.

This design does not unlock any of those items.
