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
- The source Xref is read-only. Source hash must match the request and remain unchanged before and after every live operation.
- Extraction target must be a disposable candidate under a configured disposable root. It must not be the accepted DWG, an existing accepted path, or the source path.
- Only inspected BLOCK components are supported in the first implementation. An unrecognized component type fails closed.
- Only local translation, rotation, and positive uniform scale are allowed.
- Do not add or call SourceBundle, source-fusion, component registry, revision, repair, verdict, or publication code.
- Do not commit API keys, .env files, private DWG files, source drawings, OCR output, or unapproved live artifacts.
- AutoCAD Mechanical 2027, Autodesk references, approved fixture, and private source data are required for the live gate. If unavailable, record NOT RUN or SKIP; never convert an offline test into a live PASS.
- Every task must add focused tests before implementation changes, run the focused tests, run scripts/verify.ps1, and produce one bounded commit.

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

- Add tests that accept a valid inspection request with no approval.
- Add tests that accept a valid extraction request only with target_role DISPOSABLE_CANDIDATE and approval status APPROVED.
- Add tests that reject missing run identity, source path, source revision, inspection, plan, approval reference, or candidate output path.
- Add tests that reject unknown operation parameters and any operation name outside the explicit allowlist.
- Add tests that reject a source path equal to the active target path or candidate output path.
- Add tests that require result evidence to report source hash before and after, source mutation state, candidate state, and accepted-target overwrite state.

Implementation:

- Define the operation names and schemas as explicit contract constants.
- Keep the normal IpcRequest envelope unchanged except for the minimum allowlist and schema discriminator changes.
- Make the result payload distinguish read-only inspection from candidate extraction.
- Use stable error identifiers for missing approval, source identity mismatch, source mutation, target safety failure, component mismatch, and transform policy failure.
- Ensure schema validation does not treat a caller-provided eligible value or approval boolean as sufficient authority.

Verification:

    dotnet test autocad_plugin/CadAgent.AutoCAD2027.sln --configuration Release --no-restore --filter FullyQualifiedName~ContractTests

Commit:

    contracts: add S3B exact-base Xref IPC contracts

## Task 2: Bind S3A validation into the Python IPC client

Files:

- Modify mcp_integration_lib/dotnet_ipc.py.
- Modify mcp_integration_lib/tests/test_dotnet_ipc.py.

Tests first:

- Add an inspection-client test that calls validate_xref_inspection before sending a request.
- Add an extraction-client test that calls validate_extraction_plan with the inspection payload before sending a request.
- Add tests that reject unsafe relative runtime source paths, source/target path equality, invalid hashes, mismatched revisions, and a plan component not present in the inspection.
- Add tests that require extraction approval status APPROVED and a non-empty approval reference.
- Add tests that preserve source handle, layer, block, transform, and REUSED_FROM_BASE_CAD fields without renaming them.
- Add result normalization tests for source hash stability, candidate output metadata, source_mutated=false, and accepted_target_overwrite=false.

Implementation:

- Add exact_base_xref_inspection and exact_base_xref_extraction client methods next to the existing native-render and visual-evidence methods.
- Reuse the existing request-id, full-path, hash, approval, timeout, and File IPC retry behavior.
- Accept persisted S3A relative source paths only as input metadata; require an explicit absolute runtime path for the live request.
- Call the existing validators before sending and fail locally when they reject the payload.
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
- Add fail-closed tests for wrong active document, source/target aliasing, missing approval, non-disposable target, stale plan, unknown component, duplicate component, non-uniform scale, zero or negative scale, reflection, global transform, and source hash changes.
- Add tests proving the existing operations remain unchanged.

Implementation:

- Model only the S3B request, component, transform, live snapshot, and candidate evidence fields required by the design.
- Centralize all S3B policy checks in ExactBaseXrefPolicy; the dispatcher must not grow duplicated ad hoc checks.
- Route only the two explicit operation names. Unknown operations continue to fail closed.
- Revalidate the S3A inspection and plan shape at the C# boundary or through a shared contract representation; do not trust eligible, approved, or read-only flags supplied without matching live evidence.
- Require extraction approval.status=APPROVED with an approval reference.
- Require a candidate output path under the configured disposable root and reject an existing accepted path.
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
- Add tests that inspect only the named Xref components and do not fall back to an unbounded model-space scan.
- Add tests that an inspection exception produces an unsuccessful result and never invokes a save.
- Add tests that the NullDrawingGateway remains safe and reports the live operation as unavailable.

Implementation:

- Add an explicit gateway method for read-only exact-base Xref inspection.
- Use the active AutoCAD document selected by CommandContext and the existing mechanical warning/file IPC setup.
- Resolve the exact-base Xref by the request and live drawing identity; verify it is an external reference and read-only before reading components.
- Read source handle, layer, block, and live bounds for each requested component, plus vehicle identity and critical dimensions from the already approved inspection controls.
- Hash the source file before and after the read and compare both with the requested source hash.
- Capture target hash and DBMOD before and after; require unchanged values for inspection success.
- Set changed=false for inspection and never call a save, transaction commit that mutates the source, or accepted-target mutation path.

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
- Add tests that reject an uninspected component, source handle/layer/block mismatch, unsupported type, target handle, global transform, non-uniform scale, reflection, and a missing approval reference.
- Add tests that reject source/accepted-target writes, candidate output paths outside the disposable root, existing output paths, and candidate/source path aliases.
- Add tests that source hash is stable and source_mutated=false after success and after every failure.
- Add tests that a mid-operation failure closes or discards the candidate and does not report a successful extraction.

Implementation:

- Require a successful associated inspection and a freshly revalidated extraction plan before opening the candidate mutation transaction.
- Resolve only source objects identified by the inspected handle/layer/block triple.
- Use the AutoCAD Managed .NET native database clone boundary for the selected source objects; do not reconstruct geometry or apply a drawing-wide transform.
- Apply each component transform locally, with positive uniform scale only.
- Save only a newly created candidate output below the configured disposable root. Never save the source Xref or an accepted DWG.
- Return source provenance for every extracted component: source handle, layer, block, source revision, source hash, and REUSED_FROM_BASE_CAD.
- Return candidate_changed_during_operation and save_performed separately from accepted_target_overwrite. accepted_target_overwrite must always be false.
- Hash the source after extraction and close or discard the candidate when any policy, transaction, hash, or evidence step fails.

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
- Require explicit source and candidate paths, expected source hash, and a disposable-root check.
- Exercise inspection first and assert source hash stability, identity PASS, critical dimensions PASS, read-only Xref, and unchanged DBMOD.
- Exercise extraction only after the inspection result succeeds and an APPROVED plan is supplied.
- Assert candidate output is new and disposable, accepted_target_overwrite=false, source_mutated=false, and all component provenance fields are present.
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
- Inspection is demonstrably read-only and preserves source hash and target DBMOD.
- Extraction copies only inspected, approved BLOCK components into a new disposable candidate.
- Only local translation, rotation, and positive uniform scale are accepted.
- Source provenance includes handle, layer, block, revision, hash, and REUSED_FROM_BASE_CAD.
- Accepted DWG is unchanged and never overwritten.
- Offline tests and scripts/verify.ps1 pass.
- AutoCAD live acceptance is reported accurately as PASS, NOT RUN, or SKIP.
- No scope has opened R1C, S3C, registry, revision, repair, verdict, or publication.
