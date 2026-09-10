# Standalone-DWG Component Extraction with Provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one bounded standalone-DWG component extraction capability that reuses the existing custody, provenance, candidate-revision, File IPC, and AutoCAD owners while producing only a disposable, hash-bound candidate.

**Architecture:** Keep `STANDALONE_DWG_COMPONENT_EXTRACTION_WITH_PROVENANCE` as a thin `cad_agent` orchestration adapter. Add a separate closed File IPC operation family and AutoCAD-side reader for a standalone source; never route the source through the exact-base-Xref reader. Feed the validated result into the existing DARA/R3/R4 authorities, adding one minimal versioned R3 provenance mode only if a failing contract test proves the current native full-drawing rule cannot represent the selected component lineage.

**Tech Stack:** Windows, Python 3.11, the existing `cad_agent` contracts and validators, `mcp_integration_lib.dotnet_ipc`, AutoCAD Mechanical 2027 .NET plugin, JSON File IPC, pytest, and the existing C# test project.

**Spec:** `docs/superpowers/specs/2026-09-10-standalone-dwg-component-extraction-provenance-design.md`

**Status:** planned

**Base SHA:** `4cc6df980a3a78122edcff533de70ae646700b58`

**SOL review:** `VERDICT=PASS`, `MATERIAL_FINDING=NONE`, `HUMAN_GATE=NO`; the review approved creation of this docs-only implementation plan and explicitly forbids implementation or CAD mutation until the plan is reviewed.

**Completion Head SHA:** not applicable at plan creation; record the final implementation/evidence commit here only when implementation is complete.

**Plan-time verification:** `tests/test_reuse_rebaseline_docs.py` — `3 passed`; `git diff --check` — PASS; no runtime, private-data, or live-CAD gate was run for this plan-only change.

**Required gates:** `scripts/verify.ps1` and `git diff --check` before an implementation completion claim. The `autocad_mechanical` File IPC/AutoCAD Mechanical 2027 gate is required for extraction/handle/save behavior; missing prerequisites are `SKIP` or `NOT RUN`, never PASS. Private real-drawing evidence remains outside Git and is required only when the affected acceptance path is exercised.

---

## Global Constraints

- Supported scope is Windows, Python 3.11, AutoCAD Mechanical 2027, the existing Python/File IPC/.NET boundary, and disposable candidate artifacts only.
- The standalone source is opened read-only and its source hash, path identity, and DBMOD are checked before and after inspection/extraction.
- Selection contains only explicit, hash-bound source handles/groups; no handle, component, dimension, or membership may be inferred from proximity, OCR, or visual guesses.
- The source is never treated as an Xref and the exact-base-Xref contract remains unchanged.
- Extraction starts from `EMPTY_NEW_DATABASE`; there is no candidate input path, identity, or hash.
- Only local translation, rotation, and positive uniform scale are allowed; reflection and global deformation fail closed.
- `candidate_output_path` must be absent, inside the approved disposable root, non-aliasing with the source, and re-openable/hash-bound before later review.
- Serialization to the exact `candidate_output_path` is the sole allowed file/document write; source saves, other-document/session saves, production promotion, and accepted-DXF mutation are forbidden.
- `save_performed=true` means only that disposable candidate serialization completed and the output was re-opened/read back and hash-bound; a false value is never a usable success result.
- Candidate cleanup may delete only the exact output whose captured identity still matches the failed operation; cleanup failure is a material failure.
- Existing DARA, component/view registry, candidate-revision, drawing-query, and File IPC/.NET owners remain authoritative; no second transport, writer, registry, manifest, or truth store is introduced.
- `PAGE2_REUSED` groups may enter this capability. Page-1 deltas, text, dimensions, title-block content, and unresolved visual discrepancies remain in the existing page-1 fidelity/review path.
- Real/customer drawings, annotations, credentials, generated private DXF/DWG files, and live AutoCAD state remain workstation-only.
- Human approval remains required for ambiguous recognition, unverified calibration, production mutation, and any promotion beyond the disposable candidate boundary.

## Exact implementation allowlist

The implementation branch may create or modify only the files named in the tasks below. In particular, it must not modify `cad_agent/native_dwg_provenance.py`, `cad_agent/drawing_artifact_reference.py`, `cad_agent/drawing_query.py`, `cad_agent/candidate_revision.py`, `autocad_plugin/CadAgent.AutoCAD2027/Drawing/AutoCadExactBaseXrefReader.cs`, or any exact-base-Xref schema/example. If an existing owner cannot represent a required standalone binding, stop with a named RED and request a new bounded review rather than widening the allowlist silently.

## File and ownership map

| File | Responsibility in this plan |
| --- | --- |
| `cad_agent/standalone_dwg_extraction.py` | New pure validation/orchestration adapter; validates closed packets, binds DARA/R3/R4 evidence, and calls the existing IPC client. It never parses DWG or clones entities. |
| `tests/test_cad_agent_standalone_dwg_extraction.py` | Python RED/GREEN coverage for packet closure, source/candidate identity, transforms, result hashing, cleanup, and DARA/R3/R4 binding. |
| `contracts/autocad-ipc/operations/standalone-dwg-component-inspection.schema.json` | Closed inspection request schema. |
| `contracts/autocad-ipc/operations/standalone-dwg-component-inspection-result.schema.json` | Closed inspection result schema. |
| `contracts/autocad-ipc/operations/standalone-dwg-component-extraction.schema.json` | Closed approved extraction request/plan schema. |
| `contracts/autocad-ipc/operations/standalone-dwg-component-extraction-result.schema.json` | Closed extraction result/evidence schema. |
| `contracts/autocad-ipc/examples/standalone-dwg-component-inspection.request.json` | Non-private schema example. |
| `contracts/autocad-ipc/examples/standalone-dwg-component-inspection.result.json` | Non-private schema example. |
| `contracts/autocad-ipc/examples/standalone-dwg-component-extraction.request.json` | Non-private schema example with `EMPTY_NEW_DATABASE`. |
| `contracts/autocad-ipc/examples/standalone-dwg-component-extraction.result.json` | Non-private success/failure evidence example. |
| `mcp_integration_lib/dotnet_ipc.py` | Thin client methods for the two new allowlisted operations, reusing the existing request/result, lease, path, timeout, and cleanup machinery. |
| `mcp_integration_lib/tests/test_dotnet_ipc.py` | Offline IPC serialization, closed-payload, result-binding, and fail-before-transport tests. |
| `mcp_integration_lib/tests/test_standalone_dwg_component_live.py` | Opt-in `autocad_mechanical` smoke test; it reports explicit SKIP when prerequisites are absent. |
| `mcp_integration_lib/tests/fixtures/standalone-dwg-component-inspection.json` | Synthetic non-customer inspection fixture with `XREF=0` metadata and explicit handles. |
| `autocad_plugin/CadAgent.AutoCAD2027/Drawing/StandaloneDwgComponentModels.cs` | AutoCAD-side closed request/result/evidence model types and JSON names. |
| `autocad_plugin/CadAgent.AutoCAD2027/Drawing/StandaloneDwgComponentPolicy.cs` | Source/destination/path/transform/approval policy and categorical failure codes. |
| `autocad_plugin/CadAgent.AutoCAD2027/Drawing/AutoCadStandaloneDwgComponentReader.cs` | Read-only standalone source inspection, fresh preflight, cloning into a new database, exact candidate serialization, hash/readback, and identity-checked cleanup. |
| `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractModels.cs` | Add the new closed request/result branches without altering exact-base-Xref branches. |
| `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractValidator.cs` | Add operation-specific closed-field/path/approval validation and allowlist entries. |
| `autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs` | Route only the new operation names to the standalone reader and preserve the existing dispatcher boundary. |
| `autocad_plugin/CadAgent.AutoCAD2027.Tests/Drawing/StandaloneDwgComponentReaderTests.cs` | Offline fake-database tests for source invariants, explicit selection, empty candidate, candidate-only serialization, mappings, and cleanup. |
| `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs` | Add routing and closed-result tests for the new operations; existing exact-base-Xref routing tests remain unchanged. |
| `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/ContractTests.cs` | Add schema/example/allowlist tests for the new operations. |
| `cad_agent/component_view_registry.py` | Conditional minimal versioned standalone provenance mode only if the RED in Task 4 proves the current native full-drawing mode cannot carry component bindings. |
| `tests/test_cad_agent_component_view_registry.py` | Conditional RED/GREEN coverage for that minimal mode; no change to existing native full-drawing restrictions. |
| `docs/superpowers/reuse/2026-09-10-standalone-dwg-component-extraction-reuse-dossier.md` | Internal/external reuse evidence, ownership decision, license/security/reproducibility notes, and measured gap record. |
| `docs/superpowers/implementation-records/2026-09-10-standalone-dwg-component-extraction.md` | Final implementation/evidence record only after the implementation gates pass; never store private drawing bytes or paths. |

## Task 0: Freeze the reuse dossier and implementation boundary

**Files:**
- Create: `docs/superpowers/reuse/2026-09-10-standalone-dwg-component-extraction-reuse-dossier.md`
- Test: no runtime test; review the dossier against the approved spec and the exact allowlist above.

**Interfaces:**
- Consumes: the approved spec, current `4cc6df9` tree, existing owner modules, exact-base-Xref contracts, and official File IPC/.NET owners.
- Produces: a truthful classification for every dependency and a measured reason the standalone capability is missing.

- [ ] **Step 1: Record the internal owner map.** Name the exact existing functions/classes in `drawing_artifact_reference.py`, `component_view_registry.py`, `candidate_revision.py`, `drawing_query.py`, and `mcp_integration_lib/dotnet_ipc.py` that will be called or composed. State explicitly that `native_dwg_provenance.py` remains a full-drawing owner and is not copied or widened.

- [ ] **Step 2: Record the AutoCAD/.NET reuse map.** Identify `OperationDispatcher`, `ContractValidator`, the existing JSON File IPC store/lease/path guards, and the existing AutoCAD database cloning pattern in the exact-base reader. Classify the new standalone reader as `EXTEND_WITH_ADAPTER`, not a replacement transport or a modification of the Xref owner.

- [ ] **Step 3: Record the external reuse decision.** Inspect only official AutoCAD/.NET and OpenAI/Codex-adjacent documentation needed for the boundary. Record exact source/revision, license or attribution impact, supported Windows/AutoCAD compatibility, security/reproducibility cost, and the reason no external engine, parser, writer, or transport is selected. The dossier must conclude `NEW_MISSING_CAPABILITY` only for the narrow standalone extraction owner, with the internal alternatives and their measured gaps named.

- [ ] **Step 4: Record the stop conditions.** State that a missing R3 representation, unclear AutoCAD clone semantics, a second transport, a source save, an existing candidate base, or any production target is a plan blocker requiring a fresh bounded review.

- [ ] **Step 5: Commit the dossier separately.**

```text
git add docs/superpowers/reuse/2026-09-10-standalone-dwg-component-extraction-reuse-dossier.md
git commit -m "docs: record standalone DWG extraction reuse dossier"
```

## Task 1: Add closed standalone inspection and extraction contracts

**Files:**
- Create: the four `contracts/autocad-ipc/operations/standalone-dwg-component-*.schema.json` files listed in the allowlist.
- Create: the four corresponding non-private examples.
- Create: `mcp_integration_lib/tests/fixtures/standalone-dwg-component-inspection.json`.
- Test: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/ContractTests.cs` and `tests/test_cad_agent_standalone_dwg_extraction.py`.

**Interfaces:**
- Consumes: explicit source handles/groups and an eligible inspection.
- Produces: schema versions `standalone-dwg-component-inspection-1.0`, `standalone-dwg-component-inspection-result-1.0`, `standalone-dwg-component-extraction-1.0`, and `standalone-dwg-component-extraction-result-1.0`.

- [ ] **Step 1: Write Python RED tests for closed packets.** Add tests with concrete names and expected failure codes: `test_inspection_rejects_unknown_or_missing_fields`, `test_inspection_rejects_duplicate_handles_and_empty_groups`, `test_inspection_rejects_non_hash_bound_or_non_hex_handles`, `test_extraction_plan_requires_empty_new_database_and_no_candidate_input`, `test_extraction_rejects_invalid_transform_or_fabricated_approval`, `test_result_rejects_source_mutation_or_false_save`, and `test_result_hash_and_mapping_are_deterministic`.

- [ ] **Step 2: Write C# schema RED tests.** Extend `ContractTests.cs` with `StandaloneDwgComponentOperationsAreAllowlistedWithClosedSchemaBranches`, `StandaloneDwgComponentExamplesRoundTrip`, `StandaloneDwgComponentRequestsRejectXrefOnlyFields`, and `StandaloneDwgComponentResultsRequireCandidateOnlySerialization`. Run the focused C# test filter and confirm RED because the operation names and schema files do not yet exist.

- [ ] **Step 3: Define the exact request/result fields.** Use the spec's required fields verbatim. The inspection request contains `schema_version`, `request_id`, `run_id`, `source_drawing_path`, `source_drawing_sha256`, `source_setup_audit_sha256`, `selection_groups`, `expected_dbmod`, and `approval=null`. The extraction request contains the bound inspection IDs/hashes, `source_drawing_sha256`, `candidate_output_path`, literal `candidate_base_model=EMPTY_NEW_DATABASE`, `components`, `transform_policy`, and an explicit approval object. The result contains source before/after hashes and DBMOD, `source_mutated`, `save_performed`, candidate identity/hash, one-to-one handle mappings, component evidence, and a result checksum. Do not add `candidate_input_path` or `candidate_input_sha256`.

- [ ] **Step 4: Add examples that exercise refusal as well as success.** Keep all paths synthetic and non-private. Include one `XREF=0` inspection context, one approved selection group, one local transform, `save_performed=true` only on a disposable success, and a failure example showing a non-absent output or forbidden write target. Do not use a real BVTL path or customer artifact.

- [ ] **Step 5: Run the RED tests again and commit the contract boundary.**

```text
.\.venv-py311\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_cad_agent_standalone_dwg_extraction.py
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests/CadAgent.AutoCAD2027.Tests.csproj --filter FullyQualifiedName~StandaloneDwgComponent
git diff --check
git add contracts/autocad-ipc/operations contracts/autocad-ipc/examples mcp_integration_lib/tests/fixtures tests/test_cad_agent_standalone_dwg_extraction.py autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/ContractTests.cs
git commit -m "test: define standalone DWG extraction contracts"
```

Expected result before implementation: the newly added contract tests remain RED until the validators and C# model branches are added; the commit must not be described as runtime support.

## Task 2: Implement the Python validation and existing-owner composition seam

**Files:**
- Create: `cad_agent/standalone_dwg_extraction.py`.
- Modify: `tests/test_cad_agent_standalone_dwg_extraction.py`.
- Conditional modify: `cad_agent/component_view_registry.py` and `tests/test_cad_agent_component_view_registry.py` only under Task 4's measured RED.

**Interfaces:**
- Consumes: closed inspection/result packets and an existing `mcp_integration_lib.dotnet_ipc.DotNetIPCClient`.
- Produces: pure functions `validate_standalone_inspection_request`, `validate_standalone_inspection_result`, `build_standalone_extraction_plan`, `validate_standalone_extraction_result`, and `compose_standalone_candidate_binding`. Each returns a detached normalized mapping or raises one categorical `StandaloneDwgExtractionError` code.

- [ ] **Step 1: Implement only the validator REDs.** Enforce exact top-level keys, lowercase SHA-256 values, uppercase normalized hex handles, unique membership, non-empty groups, explicit entity/layer expectations, `approval=None` for inspection, `EMPTY_NEW_DATABASE`, absent/non-aliasing candidate output, and local finite transforms with positive scale. Reject Xref-only fields and every candidate-input field before any IPC call.

- [ ] **Step 2: Bind the inspection result.** Require source path/hash/setup-audit identity, `source_sha256_before == source_sha256_after`, `dbmod_before == dbmod_after`, `read_only=true`, `changed=false`, no conflicts, exact group coverage, and a matching inspection checksum. Never convert warnings or partial identity into eligibility.

- [ ] **Step 3: Bind the extraction result.** Require `source_mutated=false`, stable source hash/DBMOD, `save_performed=true`, candidate output identity/hash, candidate-only serialization evidence, one-to-one approved source-to-candidate handle mappings, and a deterministic result checksum. Reject a result whose candidate path aliases the source or whose output cannot be re-opened/read back.

- [ ] **Step 4: Compose existing DARA/R3/R4 owners.** Issue source/candidate artifact references through `drawing_artifact_reference`, produce the standalone provenance context, route candidate identity/currentness through the existing candidate-revision builder, and expose only bound candidate handles to `drawing_query`. Do not call `build_native_dwg_r3_inputs` with fabricated full-drawing semantics and do not mutate any existing owner module.

- [ ] **Step 5: Add the IPC call seam without live execution.** The adapter may call only the two new `DotNetIPCClient` methods after all local request validation succeeds. Tests must prove malformed input raises before the dispatcher/transport is triggered.

- [ ] **Step 6: Run focused Python tests, then commit.**

```text
.\.venv-py311\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_cad_agent_standalone_dwg_extraction.py
git diff --check
git add cad_agent/standalone_dwg_extraction.py tests/test_cad_agent_standalone_dwg_extraction.py
git commit -m "feat: validate standalone DWG extraction provenance"
```

## Task 3: Add the standalone AutoCAD-side reader and closed policy

**Files:**
- Create: `autocad_plugin/CadAgent.AutoCAD2027/Drawing/StandaloneDwgComponentModels.cs`.
- Create: `autocad_plugin/CadAgent.AutoCAD2027/Drawing/StandaloneDwgComponentPolicy.cs`.
- Create: `autocad_plugin/CadAgent.AutoCAD2027/Drawing/AutoCadStandaloneDwgComponentReader.cs`.
- Create: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Drawing/StandaloneDwgComponentReaderTests.cs`.
- Modify: `autocad_plugin/CadAgent.AutoCAD2027.Tests/CadAgent.AutoCAD2027.Tests.csproj` only if the new test file is not covered by the existing glob/project configuration.

**Interfaces:**
- Consumes: the standalone request/plan models and the existing AutoCAD `Document`/`Database` boundary.
- Produces: read-only inspection snapshots and disposable extraction snapshots with source-to-candidate handle mappings.

- [ ] **Step 1: Write the fake-database RED tests.** Add `RejectsXrefOnlySourceContract`, `RequiresExactExplicitHandles`, `RejectsSourceHashOrDbmodDrift`, `StartsAnEmptyCandidateDatabase`, `SerializesOnlyThePlannedCandidateOutput`, `RejectsAnyOtherWriteTarget`, `RequiresReopenableHashBoundOutput`, `MapsEveryApprovedHandleExactlyOnce`, and `CleansOnlyWhenCandidateIdentityStillMatches`. Confirm they fail before adding the reader.

- [ ] **Step 2: Implement policy guards.** Reuse the existing normalization and reparse-point protections through the existing `ContractValidator`/policy conventions. Require a regular non-reparse `.dwg`, exact source path/hash, `XREF=0`-compatible standalone handling, an absent disposable output, and a source/output identity distinction. Reject candidate input fields and any accepted/source path as an output.

- [ ] **Step 3: Implement read-only inspection.** Open the standalone source read-only, inspect only the requested handles/groups, verify entity type/layer/bounds and expected identity, capture before/after hash and DBMOD, and return `eligible=false` on any drift, missing handle, conflict, or unexpected entity. Do not enumerate the drawing as a substitute for selection identity.

- [ ] **Step 4: Implement empty-database extraction.** Create a new `Database(true, true)`, clone only the approved source objects, apply only the approved local transform, record exact source/candidate handle mappings, serialize once to the exact output path, capture output identity/hash, reopen/read back, and set `SavePerformed=true` only after all those checks succeed. The source document and every other document remain read-only.

- [ ] **Step 5: Implement fail-closed cleanup.** On post-create failure, compare the captured candidate identity and delete only that exact output. Report cleanup failure as material and never delete/restore a source, accepted drawing, or unrelated candidate.

- [ ] **Step 6: Run offline C# tests and commit.**

```text
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests/CadAgent.AutoCAD2027.Tests.csproj --filter FullyQualifiedName~StandaloneDwgComponentReader
git diff --check
git add autocad_plugin/CadAgent.AutoCAD2027/Drawing/StandaloneDwgComponentModels.cs autocad_plugin/CadAgent.AutoCAD2027/Drawing/StandaloneDwgComponentPolicy.cs autocad_plugin/CadAgent.AutoCAD2027/Drawing/AutoCadStandaloneDwgComponentReader.cs autocad_plugin/CadAgent.AutoCAD2027.Tests/Drawing/StandaloneDwgComponentReaderTests.cs
git commit -m "feat: add standalone DWG disposable reader"
```

## Task 4: Prove or reject the minimal R3 lineage extension

**Files:**
- Test first: `tests/test_cad_agent_component_view_registry.py`.
- Conditional modify: `cad_agent/component_view_registry.py` only if the RED proves the current registry cannot carry standalone component provenance.

**Interfaces:**
- Consumes: the standalone provenance context and candidate handle mappings from Task 2.
- Produces: a versioned, minimal component/view registry context that keeps source handles and candidate handles bound to the standalone source.

- [ ] **Step 1: Write the RED against the current owner.** Assert that a standalone context with non-empty selected components is either accepted by an existing closed mode or is rejected with the current native full-drawing empty-component rule. Record the exact failure code and do not change the registry before this test is RED.

- [ ] **Step 2: If the existing owner is sufficient, keep the file unchanged.** Extend only the adapter tests to prove DARA/R3/R4 and drawing-query all bind the same source/candidate identities. This is the preferred outcome.

- [ ] **Step 3: If the RED proves insufficiency, add one versioned mode.** Add a standalone provenance mode and the smallest new upstream-context fields needed for exact source path/hash, selected source groups, candidate path binding, and provenance checksum. Preserve `NATIVE_DWG_FULL_DRAWING` behavior and its empty-component rule byte-for-byte in intent; do not weaken or bypass its validation.

- [ ] **Step 4: Add adversarial tests.** Reject a full-drawing packet mislabeled as standalone, a standalone packet with `REUSED_FROM_BASE_CAD`, a candidate handle owned by two components, an unbound source handle, stale source/candidate hashes, and a component/view link pointing to a different candidate revision.

- [ ] **Step 5: Commit only the measured extension.**

```text
.\.venv-py311\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_cad_agent_component_view_registry.py tests/test_cad_agent_standalone_dwg_extraction.py
git diff --check
git add tests/test_cad_agent_component_view_registry.py cad_agent/component_view_registry.py
git commit -m "feat: bind standalone extraction lineage in R3"
```

If the current registry passes the RED without a code change, do not create a no-op commit and record `R3_EXTENSION=NOT_NEEDED` in the implementation record.

## Task 5: Wire the existing File IPC/.NET boundary

**Files:**
- Modify: `mcp_integration_lib/dotnet_ipc.py`.
- Modify: `mcp_integration_lib/tests/test_dotnet_ipc.py`.
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractModels.cs`.
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractValidator.cs`.
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs`.
- Modify: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs`.
- Modify: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/ContractTests.cs`.

**Interfaces:**
- Consumes: the four standalone JSON schemas, the Task 3 reader, and the existing request/result/lease protocol.
- Produces: two allowlisted operations named `standalone_dwg_component_inspection` and `standalone_dwg_component_extraction` with no second transport.

- [ ] **Step 1: Add Python IPC RED tests.** Add `test_standalone_inspection_sends_closed_parameters`, `test_standalone_extraction_binds_approval_and_empty_base`, `test_standalone_rejects_candidate_input_before_trigger`, `test_standalone_rejects_source_or_other_write_targets`, `test_standalone_rejects_mismatched_result_identity`, and `test_standalone_cleanup_failure_is_not_success`. Confirm the fake dispatcher is not called for local validation failures.

- [ ] **Step 2: Add the C# contract branches.** Add request/result model branches and exact schema routing in `ContractModels.cs` and `ContractValidator.cs`. Reject unknown fields, Xref-only fields, candidate input fields, non-absolute paths, reparse roots, invalid handles, invalid hashes, invalid transforms, and missing approval on extraction.

- [ ] **Step 3: Add dispatcher routing.** Route only the two new operation names to `AutoCadStandaloneDwgComponentReader`. Preserve the existing operation allowlist, request/result envelope, single-request lease behavior, timeout semantics, and path/hash identity checks. Do not route the new operations through `AutoCadExactBaseXrefReader`.

- [ ] **Step 4: Add dispatcher and schema tests.** Assert that inspection is read-only, extraction uses a fresh preflight, candidate output is returned only after successful serialization/readback, and exact-base-Xref tests still pass unchanged.

- [ ] **Step 5: Run focused Python and C# tests, then commit.**

```text
.\.venv-py311\Scripts\python.exe -m pytest -q -p no:cacheprovider mcp_integration_lib/tests/test_dotnet_ipc.py
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests/CadAgent.AutoCAD2027.Tests.csproj --filter "FullyQualifiedName~ContractTests|FullyQualifiedName~OperationDispatcherTests"
git diff --check
git add mcp_integration_lib/dotnet_ipc.py mcp_integration_lib/tests/test_dotnet_ipc.py autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractModels.cs autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractValidator.cs autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/ContractTests.cs
git commit -m "feat: route standalone DWG extraction through File IPC"
```

## Task 6: Add the opt-in live gate and complete evidence binding

**Files:**
- Create/modify: `mcp_integration_lib/tests/test_standalone_dwg_component_live.py`.
- Modify: `tests/test_cad_agent_standalone_dwg_extraction.py`.
- Create: `docs/superpowers/implementation-records/2026-09-10-standalone-dwg-component-extraction.md` only after all implementation gates pass.

**Interfaces:**
- Consumes: the complete standalone adapter, schemas, IPC branch, reader, and existing approved File IPC environment variables.
- Produces: truthful offline/live evidence and a provenance handoff ready for a separately authorized page-1 candidate workflow.

- [ ] **Step 1: Add the live test as an explicit gate.** Require AutoCAD Mechanical 2027, approved plugin identity, File IPC root, HWND, LISP path, source path/hash/setup audit, and a disposable candidate root. When any prerequisite is absent, emit `SKIP` with the exact missing prerequisite. Never fabricate a live PASS.

- [ ] **Step 2: Bind the live evidence.** On an available run, prove the standalone source is the approved `BVTL.dwg` source, `XREF=0` is handled by the new reader, the requested handles/groups are exact, source hash/DBMOD/read-only state are stable, candidate output is absent before creation, `save_performed=true` only after reopen/hash, and cleanup or retained disposable output is identity-bound. Close AutoCAD without saving the source.

- [ ] **Step 3: Add the final integration assertions.** Prove the result enters DARA/R3/R4 with the same source/candidate identities, `drawing_query` can read only the bound candidate, page-1 delta groups are rejected by the extraction adapter, and no exact-base-Xref or native full-drawing restriction is weakened.

- [ ] **Step 4: Run the complete verification set.**

```text
.\scripts\verify.ps1
.\.venv-py311\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_cad_agent_standalone_dwg_extraction.py tests/test_cad_agent_component_view_registry.py mcp_integration_lib/tests/test_dotnet_ipc.py mcp_integration_lib/tests/test_standalone_dwg_component_live.py -ra
dotnet test autocad_plugin/CadAgent.AutoCAD2027.sln --configuration Release
git diff --check
```

Record exact exit codes, commit SHA, Python/.NET/AutoCAD versions, PASS/FAIL/SKIP/NOT RUN states, and all private/live prerequisites. If the live prerequisites are absent, record `autocad_mechanical=SKIP` or `NOT RUN`; do not promote the result to release evidence.

- [ ] **Step 5: Write the implementation record.** Include the final implementation/evidence commit, exact schemas and operation names, reuse dossier classification, tests, live/private gate states, source immutability result, candidate cleanup result, reviewer findings, and remaining risks. Include hashes and logical artifact references only; never include the private DWG or customer annotation.

- [ ] **Step 6: Commit the record separately.**

```text
git add docs/superpowers/implementation-records/2026-09-10-standalone-dwg-component-extraction.md
git commit -m "docs: record standalone DWG extraction evidence"
```

## Review allocation and acceptance gates

This is an architecture/File IPC/AutoCAD/handle/extraction change, so use three independent first-pass reviews on the exact implementation head:

1. **Requirements/architecture:** confirm the implementation matches the approved spec, exact allowlist, reuse dossier, page-1/page-2 boundary, and minimal R3 extension decision.
2. **Correctness/test:** inspect closed contracts, source/candidate identity binding, mappings, transforms, serialization/readback, cleanup, and test evidence.
3. **Security/operations:** red-team path traversal/reparse points, wrong drawing/session, stale hash/DBMOD, replayed approval, source/accepted mutation, candidate aliasing, cleanup races, transport retries, and false PASS from missing prerequisites.

Acceptance requires all of the following:

- no unresolved P0/P1 finding;
- focused Python and C# tests pass;
- `scripts/verify.ps1` passes on the final exact head;
- `git diff --check` passes and verification leaves repository status clean;
- the exact-base-Xref reader/contracts remain unchanged in behavior;
- `autocad_mechanical` evidence is PASS when the live capability is claimed, otherwise explicitly SKIP/NOT RUN;
- source/accepted drawings and private artifacts remain unchanged and outside Git;
- production promotion remains a separate human-approved boundary.

## Plan self-review

- Spec coverage: source custody/currentness, explicit selection, `EMPTY_NEW_DATABASE`, candidate-only serialization, result hashing, mapping, transforms, fail-closed cleanup, DARA/R3/R4 binding, File IPC ownership, page-1 boundary, and live/private gates each have a named task.
- Reuse coverage: existing Python custody/currentness, component/view, candidate-revision, drawing-query, File IPC, dispatcher, policy, and AutoCAD database boundaries are named; no second engine, writer, transport, or truth store is planned.
- Registry safety: R3 changes are conditional on a concrete failing test and preserve the native full-drawing empty-component restriction.
- Placeholder scan: no unfinished placeholder or unspecified implementation step is used; future file names, operation names, test names, commands, and expected states are explicit.
- Type/interface consistency: the Python adapter calls the two named IPC methods; the IPC methods use the two named operation names; the dispatcher routes those names to the named standalone reader; the reader returns the named inspection/extraction result families consumed by the adapter.
- Mutation boundary: the plan permits only disposable candidate serialization in the future live operation and forbids source, accepted, session-state, production, and private-artifact mutation.
