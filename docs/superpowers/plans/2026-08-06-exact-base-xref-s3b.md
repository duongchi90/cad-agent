# S3B Exact-Base Xref File IPC/.NET Live Inspection and Approved Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bounded, fail-closed File IPC/.NET execution path that live-inspects an exact-base AutoCAD Xref and extracts only inspected, approved components into a disposable candidate drawing, while preserving source provenance and leaving accepted DWG and source data untouched.

**Architecture:** Reuse the S3A Python validator, existing DotNetIPCClient, File IPC envelope, OperationDispatcher, and AutoCadDrawingGateway. Add two explicit operations: exact_base_xref_inspection for read-only evidence and exact_base_xref_extraction for approved disposable-candidate mutation. Keep live AutoCAD evidence behind an environment gate; do not add SourceBundle fusion, registry, repair, verdict, or publication behavior.

**Tech Stack:** Python 3.11, pytest, existing mcp_integration_lib IPC client, C#/.NET AutoCAD Mechanical 2027 plugin, Autodesk Managed .NET API, existing PowerShell verification script.

## Global Constraints

- Exact implementation base: 1ba05ea6d768351fa7106109bcee244e60463527.
- Implementation is not authorized by this planning document. Create an issue and obtain an explicit PO allowlist before changing runtime files.
- Use a new task branch created from the exact base; do not use the personal pilot branch and do not merge, rebase, reset, or switch it without explicit task direction.
- The implementation issue must name the exact base, branch, bounded commit policy, allowlist below, and live AutoCAD gate.
- S3A policy in mcp_integration_lib/exact_base_xref.py and its fixtures are authoritative and must not be weakened, duplicated, or rewritten.
- Caller-provided inspection evidence is expectation data only. The request must exclude live-owned observed, status, eligible, changed, DBMOD, live bounds, and live timestamps; the C# gateway must build a fresh S3A-compatible live result from AutoCAD and the file system.
- Extraction must run a complete fresh live preflight immediately before opening its mutation transaction. Matching run_id, a valid offline plan, or a caller-provided successful inspection never authorizes mutation.
- CommandContext owns the server-side S3B path policy. It loads CAD_AGENT_S3B_DISPOSABLE_ROOT, CAD_AGENT_S3B_ACCEPTED_DWG_PATH, CAD_AGENT_S3B_ACCEPTED_DWG_SHA256, CAD_AGENT_S3B_EXACT_BASE_SOURCE_PATH, CAD_AGENT_S3B_EXACT_BASE_SOURCE_SHA256, and CAD_AGENT_S3B_EXACT_BASE_SOURCE_REVISION. Requests cannot override these values.
- Controlled paths must be canonicalized through Windows file handles and checked by final path and file identity. Reject junctions, symlinks, mount points, other reparse points, aliases, path escapes, source/accepted aliases, and outputs outside the resolved disposable root. Lexical prefix checks are insufficient.
- The source Xref is read-only. Source hash must match the request and remain unchanged before and after every live operation.
- Extraction target must be a disposable candidate under a configured disposable root. It must not be the accepted DWG, an existing accepted path, or the source path.
- Only inspected BLOCK components are supported in the first implementation. An unrecognized component type fails closed.
- Only local translation, rotation, and positive uniform scale are allowed.
- Do not add or call SourceBundle, source-fusion, component registry, revision, repair, verdict, or publication code.
- Do not commit API keys, .env files, private DWG files, source drawings, OCR output, or unapproved live artifacts.
- AutoCAD Mechanical 2027, Autodesk references, approved fixture, and private source data are required for the live gate. If unavailable, record NOT RUN or SKIP; never convert an offline test into a live PASS.
- Every task must add focused tests before implementation changes, run the focused tests, run scripts/verify.ps1, and produce one bounded commit.
- The IPC result semantics are closed: drawing_full_path is the server-canonical active document path; inspection has changed=false and entity_handles=[]; successful extraction has changed=true and sorted native-created candidate handles; failures after cleanup have changed=false and entity_handles=[].
- Extraction evidence must include a source_handle_to_candidate_handle mapping for every native-extracted component, plus source provenance and candidate-only state.
- A session guard must restore the original active document, layout/view/UCS state, and transaction state. Partial candidate output cleanup may remove only the operation-owned newly-created file after canonical identity recheck.

## Allowlist

Create:

- contracts/autocad-ipc/operations/exact-base-xref-inspection.schema.json
- contracts/autocad-ipc/operations/exact-base-xref-inspection-result.schema.json
- contracts/autocad-ipc/operations/exact-base-xref-extraction.schema.json
- contracts/autocad-ipc/operations/exact-base-xref-extraction-result.schema.json
- contracts/autocad-ipc/examples/exact-base-xref-inspection.request.json
- contracts/autocad-ipc/examples/exact-base-xref-inspection.result.json
- contracts/autocad-ipc/examples/exact-base-xref-extraction.request.json
- contracts/autocad-ipc/examples/exact-base-xref-extraction.result.json
- autocad_plugin/CadAgent.AutoCAD2027/Drawing/ExactBaseXrefModels.cs
- autocad_plugin/CadAgent.AutoCAD2027/Drawing/ExactBaseXrefPolicy.cs
- autocad_plugin/CadAgent.AutoCAD2027/Drawing/AutoCadExactBaseXrefReader.cs
- autocad_plugin/CadAgent.AutoCAD2027.Tests/Drawing/ExactBaseXrefPolicyTests.cs
- autocad_plugin/CadAgent.AutoCAD2027.Tests/Drawing/ExactBaseXrefReaderTests.cs
- docs/superpowers/implementation-records/2026-08-06-exact-base-xref-s3b.md

Modify:

- contracts/autocad-ipc/request.schema.json
- contracts/autocad-ipc/result.schema.json
- autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractModels.cs
- autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractValidator.cs
- autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs
- autocad_plugin/CadAgent.AutoCAD2027/Drawing/IDrawingGateway.cs
- autocad_plugin/CadAgent.AutoCAD2027/Drawing/NullDrawingGateway.cs
- autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs
- autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/ContractTests.cs
- autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs
- mcp_integration_lib/dotnet_ipc.py
- mcp_integration_lib/tests/test_dotnet_ipc.py
- mcp_integration_lib/tests/test_dotnet_ipc_live.py

Do not modify:

- mcp_integration_lib/exact_base_xref.py
- mcp_integration_lib/tests/fixtures/exact-base-xref-inspection.json
- cad_agent/source_bundle.py or any SourceBundle consumer
- registry, revision, repair, verdict, publication, OCR, or source-fusion modules
- accepted DWG files, private source drawings, or generated live artifacts

## Task 1: Freeze the two IPC operation contracts

Files:

- Create the four operation and result schemas in the allowlist.
- Create four JSON examples using the existing S3A fixture values and safe placeholder runtime paths that are clearly non-live examples.
- Modify request.schema.json and result.schema.json only where required to allowlist the two operation names and their operation-specific result payloads.
- Modify autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/ContractTests.cs.

Tests first:

- Add tests that accept a valid inspection request with no approval and only the closed inspection_expectations projection.
- Add tests that accept a valid extraction request only with target_role DISPOSABLE_CANDIDATE, extraction_plan.approval.status APPROVED, and exact canonical equality with the envelope approval object.
- Add tests that reject missing run identity, source path, source revision, inspection_expectations, plan, approval reference, or candidate output path.
- Add tests that reject unknown operation parameters and any operation name outside the explicit allowlist.
- Add tests that reject a source path equal to the active target path or candidate output path.
- Add tests that reject caller-supplied observed, status, eligible, changed, DBMOD, live bounds, live hashes, or live timestamps.
- Add tests that require result evidence to define drawing_full_path, changed, entity_handles, source-handle-to-candidate-handle mapping, and accepted-target overwrite state.

Implementation:

- Define the operation names and schemas as explicit contract constants.
- Keep the normal IpcRequest envelope unchanged except for the minimum allowlist and schema discriminator changes.
- Make the result payload distinguish read-only inspection from candidate extraction and define drawing_full_path as the server-canonical active document path.
- Define inspection changed=false/entity_handles=[] and successful extraction changed=true with native-created candidate handles; after cleanup, failures return changed=false/entity_handles=[].
- Define source_handle_to_candidate_handle evidence for every extracted component.
- Use stable error identifiers for missing approval, source identity mismatch, source mutation, target safety failure, component mismatch, and transform policy failure.
- Ensure schema validation does not treat caller-owned live fields, eligible values, approval booleans, target-role booleans, or lexical path containment as authority.

Verification:

    dotnet test autocad_plugin/CadAgent.AutoCAD2027.sln --configuration Release --no-restore --filter FullyQualifiedName~ContractTests

Commit:

    contracts: add S3B exact-base Xref IPC contracts

## Task 2: Bind S3A validation into the Python IPC client

Files:

- Modify mcp_integration_lib/dotnet_ipc.py.
- Modify mcp_integration_lib/tests/test_dotnet_ipc.py.

Tests first:

- Add an inspection-client test that validates the offline S3A record, then sends only inspection_expectations and never the live-owned evidence fields.
- Add an extraction-client test that calls validate_extraction_plan with the inspection payload before sending a request.
- Add tests that reject unsafe relative runtime source paths, source/target path equality, invalid hashes, mismatched revisions, and a plan component not present in the offline inspection.
- Add tests that require extraction_plan.approval.status APPROVED, a non-empty reference, and exact equality with the envelope approval object.
- Add tests that preserve source handle, layer, block, transform, and REUSED_FROM_BASE_CAD fields without renaming them.
- Add result normalization tests for the server-built live inspection, source hash stability, drawing_full_path, changed, entity_handles, candidate output metadata, source_handle_to_candidate_handle, source_mutated=false, and accepted_target_overwrite=false.

Implementation:

- Add exact_base_xref_inspection and exact_base_xref_extraction client methods next to the existing native-render and visual-evidence methods.
- Reuse the existing request-id, full-path, hash, approval, timeout, and File IPC retry behavior.
- Accept persisted S3A records only as offline expectations and require an explicit runtime path that the server-side CommandContext source policy also authorizes.
- Call the existing validators before sending and fail locally when they reject the payload.
- Never send a prior successful inspection as extraction authority; extraction sends the offline plan/expectations and the server performs fresh preflight.
- Do not add a Python-side source-fusion or registry adapter.
- Do not claim live success from a mock response; live result normalization must retain the actual gate state.

Verification:

    .\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_dotnet_ipc.py -q -p no:cacheprovider

Commit:

    ipc: bind S3A exact-base validation to S3B requests

## Task 3: Add C# request models, policy, and dispatcher routing

Files:

- Create autocad_plugin/CadAgent.AutoCAD2027/Drawing/ExactBaseXrefModels.cs.
- Create autocad_plugin/CadAgent.AutoCAD2027/Drawing/ExactBaseXrefPolicy.cs.
- Modify autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractModels.cs.
- Modify autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractValidator.cs.
- Modify autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs.
- Modify autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs.
- Create autocad_plugin/CadAgent.AutoCAD2027.Tests/Drawing/ExactBaseXrefPolicyTests.cs.

Tests first:

- Add dispatcher tests for both operations with the existing fake or null gateway.
- Add policy tests for exact request identity, source hash and revision equality, required PASS controls, read-only Xref state, BLOCK-only component support, exact source handle/layer/block matching, and local transform limits.
- Add policy tests for server-owned environment configuration, canonical final paths, file identity, reparse-point/junction rejection, root containment, source/accepted alias rejection, and new-output nonexistence.
- Add fail-closed tests for wrong active document, source/target aliasing, missing approval, exact plan/envelope approval mismatch, non-disposable target, stale plan, unknown component, duplicate component, non-uniform scale, zero or negative scale, reflection, global transform, source hash changes, and missing fresh preflight.
- Add tests proving the existing operations remain unchanged.

Implementation:

- Model only the S3B request, component, transform, live snapshot, and candidate evidence fields required by the design.
- Centralize all S3B policy checks in ExactBaseXrefPolicy; the dispatcher must not grow duplicated ad hoc checks.
- Route only the two explicit operation names. Unknown operations continue to fail closed.
- Revalidate the offline S3A plan shape at the C# boundary; accept only the closed inspection_expectations projection and build all live-owned inspection fields from AutoCAD.
- Require extraction_plan.approval.status=APPROVED and exact canonical equality with the envelope approval object, including the approval reference.
- Load the S3BPathPolicy once in CommandContext from the six server-side environment values named in the design. Do not trust request booleans or caller paths.
- Require candidate input and output paths to pass handle-based canonicalization, file-identity, reparse-point, root-containment, source-alias, and accepted-alias checks.
- Require extraction to invoke the full live preflight immediately before mutation; a prior inspection result is informational only.
- Define drawing_full_path, changed, entity_handles, and source_handle_to_candidate_handle in the result model exactly as specified by the design.
- Return unsuccessful results with stable error identifiers and no partial acceptance.

Verification:

    dotnet test autocad_plugin/CadAgent.AutoCAD2027.sln --configuration Release --no-restore --filter FullyQualifiedName~OperationDispatcherTests

Commit:

    autocad: route S3B exact-base Xref operations fail closed

## Task 4: Implement read-only live inspection in the drawing gateway

Files:

- Modify autocad_plugin/CadAgent.AutoCAD2027/Drawing/IDrawingGateway.cs.
- Modify autocad_plugin/CadAgent.AutoCAD2027/Drawing/NullDrawingGateway.cs.
- Modify autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs.
- Create autocad_plugin/CadAgent.AutoCAD2027/Drawing/AutoCadExactBaseXrefReader.cs.
- Create or modify autocad_plugin/CadAgent.AutoCAD2027.Tests/Drawing/ExactBaseXrefReaderTests.cs.

Tests first:

- Add gateway tests using deterministic fake database objects for source hash stability, Xref read-only state, identity controls, critical dimensions, component handles, layers, blocks, and DBMOD stability.
- Add tests proving every live-owned field is recomputed from AutoCAD/file-system reads and that caller-supplied observed, status, eligible, changed, DBMOD, live bounds, live hashes, and timestamps are never echoed.
- Add tests that inspect only the named Xref components and do not fall back to an unbounded model-space scan.
- Add tests that an inspection exception produces an unsuccessful result and never invokes a save.
- Add tests that the NullDrawingGateway remains safe and reports the live operation as unavailable.

Implementation:

- Add an explicit gateway method for read-only exact-base Xref inspection.
- Construct the server-owned S3BPathPolicy in CommandContext from the named environment values and use it for every request.
- Use the active AutoCAD document selected by CommandContext and the existing mechanical warning/file IPC setup.
- Resolve the exact-base Xref by the server-authorized source identity and live drawing identity; verify it is an external reference and read-only before reading components.
- Read source handle, layer, block, live bounds, vehicle identity, and critical dimensions from AutoCAD. Compute observed values, PASS/FAIL status, eligibility, changed, DBMOD, and timestamps in the gateway.
- Build a fresh S3A-compatible live_inspection result from those reads, validate that result with the frozen S3A validator, and never copy caller evidence into it.
- Hash the source file before and after the read and compare both with the server-configured source hash.
- Capture target hash and DBMOD before and after; require unchanged values for inspection success.
- Set drawing_full_path to the server-canonical active path, changed=false, and entity_handles=[] for inspection. Never call a save, mutating transaction commit, or accepted-target mutation path.

Verification:

    dotnet test autocad_plugin/CadAgent.AutoCAD2027.sln --configuration Release --no-restore --filter FullyQualifiedName~ExactBaseXrefReaderTests

Commit:

    autocad: add read-only exact-base Xref inspection gateway

## Task 5: Implement approved extraction into a disposable candidate

Files:

- Modify autocad_plugin/CadAgent.AutoCAD2027/Drawing/AutoCadExactBaseXrefReader.cs.
- Modify autocad_plugin/CadAgent.AutoCAD2027/Drawing/ExactBaseXrefPolicy.cs.
- Modify autocad_plugin/CadAgent.AutoCAD2027/Drawing/IDrawingGateway.cs.
- Modify autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs.
- Modify autocad_plugin/CadAgent.AutoCAD2027.Tests/Drawing/ExactBaseXrefReaderTests.cs.
- Modify autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs.

Tests first:

- Add a candidate-only extraction test that copies exactly the inspected BLOCK components.
- Add transform tests for translation, rotation, and positive uniform scale on each component.
- Add tests that reject an uninspected component, source handle/layer/block mismatch, unsupported type, target handle, global transform, non-uniform scale, reflection, a missing approval reference, and an exact plan/envelope approval mismatch.
- Add tests that invoke the full live preflight immediately before mutation and reject extraction when any fresh identity, dimension, Xref, component, hash, or DBMOD check fails, regardless of prior inspection/run_id.
- Add tests that reject source/accepted-target writes, candidate input/output paths outside the server-owned disposable root, existing output paths, reparse points, and candidate/source/accepted aliases.
- Add tests that source hash is stable and source_mutated=false after success and after every failure.
- Add tests that source_handle_to_candidate_handle maps each native-created candidate handle and that result drawing_full_path, changed, and entity_handles follow the closed semantics.
- Add tests that a mid-operation failure closes or discards the candidate, restores the original session, cleans only its own partial output, and does not report a successful extraction.

Implementation:

- Require a freshly revalidated extraction plan and exact plan/envelope approval binding before opening the candidate mutation transaction.
- Run the complete live preflight again immediately before the mutation transaction. A prior inspection result and matching run_id are not authority.
- Resolve only source objects identified by the inspected handle/layer/block triple and matched again by fresh live evidence.
- Use the AutoCAD Managed .NET native database clone boundary for the selected source objects; do not reconstruct geometry or apply a drawing-wide transform.
- Apply each component transform locally, with positive uniform scale only.
- Capture and restore the original active document, layout/view/UCS, and transaction state with a finally-protected session guard.
- Save only a newly created candidate output below the server-owned disposable root. Never save the source Xref or an accepted DWG.
- Return drawing_full_path as the canonical active candidate input, changed=true only for committed candidate mutation, sorted native-created candidate handles in entity_handles, and source_handle_to_candidate_handle mappings.
- Return source provenance for every extracted component: source handle, candidate handle, layer, block, source revision, source hash, and REUSED_FROM_BASE_CAD.
- Return candidate_changed_during_operation and save_performed separately from accepted_target_overwrite. accepted_target_overwrite must always be false.
- Hash the source after extraction. On any policy, transaction, hash, evidence, restoration, or cleanup failure, close/discard the candidate, delete only the own newly-created output after identity recheck, and return changed=false/entity_handles=[].

Verification:

    dotnet test autocad_plugin/CadAgent.AutoCAD2027.sln --configuration Release --no-restore --filter FullyQualifiedName~ExactBaseXrefReaderTests

Commit:

    autocad: extract approved exact-base components to disposable candidate

## Task 6: Add the gated AutoCAD live acceptance harness and evidence record

Files:

- Modify mcp_integration_lib/tests/test_dotnet_ipc_live.py.
- Add or update the S3B implementation record only after implementation is authorized and executed: docs/superpowers/implementation-records/2026-08-06-exact-base-xref-s3b.md.
- Do not commit live DWG files or private artifacts.

Tests first:

- Add a live test marker and make it skip unless all required environment variables and AutoCAD Mechanical 2027 prerequisites are present.
- Require server-owned source/accepted/root configuration, explicit candidate input/output paths, expected source hash, canonical path checks, and a disposable-root check.
- Exercise inspection first and assert a fresh server-built live_inspection with source hash stability, identity PASS, critical dimensions PASS, read-only Xref, unchanged DBMOD, and no caller-owned live field echo.
- Exercise extraction with a plan whose approval object exactly matches the IPC envelope and assert the full live preflight runs immediately before mutation.
- Assert candidate output is new and disposable, drawing_full_path is canonical, changed/entity_handles have the closed semantics, accepted_target_overwrite=false, source_mutated=false, source-to-candidate mappings exist, session state is restored, and cleanup is complete.
- Assert missing AutoCAD, missing Autodesk references, unavailable fixture, or missing approved private source records NOT RUN or SKIP instead of PASS.

Implementation:

- Reuse the existing live test harness and File IPC directory.
- Do not synthesize a live success from fixture-only data.
- Record the exact source revision/hash, candidate path policy, request IDs, operation results, and AutoCAD/plugin versions without storing private drawing contents.
- Keep the live test opt-in and non-destructive. A failed live attempt must clean up only its own disposable candidate output.

Verification:

    $env:CAD_AGENT_S3B_LIVE = "1"
    .\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_dotnet_ipc_live.py -m autocad_mechanical -k s3b -ra -p no:cacheprovider

Commit:

    test: add gated S3B AutoCAD live acceptance

## Task 7: Run the complete offline gate and hand off for PO review

Files:

- No additional runtime files.
- Update only the authorized S3B implementation record if the implementation and gates actually ran.

Checks:

    .\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_exact_base_xref.py mcp_integration_lib/tests/test_dotnet_ipc.py mcp_integration_lib/tests/test_dotnet_ipc_live.py -q -p no:cacheprovider

    dotnet test autocad_plugin/CadAgent.AutoCAD2027.sln --configuration Release --no-restore

    .\scripts\verify.ps1

Review:

- Confirm git diff contains only the approved allowlist.
- Confirm no SourceBundle, source-fusion, registry, revision, repair, verdict, or publication files changed.
- Confirm accepted main remains at 1ba05ea6d768351fa7106109bcee244e60463527 as the implementation base.
- Confirm all live gates are labeled PASS, NOT RUN, or SKIP with evidence; never infer PASS from offline tests.
- Produce one final bounded implementation commit or a small, explicitly bounded series if the issue permits it.
- Stop and request PO review. Do not open S3C or R1C from this plan.

## Completion criteria

The implementation is complete only when:

- Both S3B operations are allowlisted and covered by contract tests.
- Python requests are validated by the frozen S3A policy before transport.
- C# policy and dispatcher fail closed for every safety condition in the design.
- Live inspection is server-authoritative: every observed/status/eligible/changed/DBMOD/bounds/hash/timestamp field is freshly computed and caller evidence is never echoed.
- Inspection is demonstrably read-only and preserves source hash and target DBMOD.
- Extraction performs the full live preflight immediately before mutation and copies only inspected, approved BLOCK components into a new disposable candidate.
- CommandContext-owned path policy proves canonical root containment, reparse-point rejection, source/accepted alias rejection, and new-output safety.
- extraction_plan.approval exactly matches the APPROVED IPC envelope approval object.
- drawing_full_path, changed, entity_handles, source_handle_to_candidate_handle, session restoration, and partial-output cleanup are evidenced according to the closed contract.
- Only local translation, rotation, and positive uniform scale are accepted.
- Source provenance includes handle, layer, block, revision, hash, and REUSED_FROM_BASE_CAD.
- Accepted DWG is unchanged and never overwritten.
- Offline tests and scripts/verify.ps1 pass.
- AutoCAD live acceptance is reported accurately as PASS, NOT RUN, or SKIP.
- No scope has opened R1C, S3C, registry, revision, repair, verdict, or publication.
