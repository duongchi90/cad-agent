# Standalone DWG Component Extraction — Task 6 Implementation Record

Date: 2026-09-11
Branch: `codex/audit-text-style-compat-20260910`
Implementation/evidence commits: `a1fece80b1efae831d442626c6454a0ae23533d0`,
`94719ca3e854dd3bb6b668217924c85e3d07c214`, and
`a17032275a628328dcad0fd15166e413faee3663`

## Scope and boundary

Task 6 adds an opt-in `autocad_mechanical` gate for the approved standalone
`BVTL.dwg` source. The gate consumes an operator-prepared private fixture and
never stores the source DWG, customer annotations, candidate DWG, or private
evidence in Git.

The live path is candidate-only and read-only with respect to the source:

1. Open the approved source through the existing File IPC client.
2. Verify the loaded `AutoCAD Mechanical 2027` host and exact plugin binary
   identity through `health`.
3. Run `drawing_setup_audit` and require stable DBMOD/read-only setup evidence.
4. Run `standalone_dwg_component_inspection` and require `XREF=0`, exact
   inspection groups/handles, unchanged source hash/DBMOD, and eligibility.
5. Require an absent disposable output, then run
   `standalone_dwg_component_extraction` with `EMPTY_NEW_DATABASE`.
6. Reopen and hash the candidate before accepting `save_performed=true`.
7. Compose the detached source BASELINE, `R3_CANDIDATE`, registry, and root
   `R4` candidate revision. Query only the candidate-bound handles through
   `drawing_query`.
8. Close the candidate without saving and remove it only after the returned
   candidate hash and identity match. Reopen/check/close the source without
   saving.

The page-1 delta regression uses the existing inspection-backed allowlist:
`cargo-side-frame` is rejected by `build_standalone_extraction_plan` when it
has not been inspected. No native full-drawing or exact-base-Xref restriction
was changed.

The candidate identity boundary was then remediated after independent review
found that the real .NET cleanup identity (`path|length|creation ticks|write
ticks`) was being exposed as the schema `file_id`. The raw filesystem identity
is now retained only as the internal cleanup recheck, while the public result
exposes `candidate-file-<sha256(raw identity)>`, which satisfies the frozen
schema grammar. C# reader/dispatcher coverage and the Python result validator
now exercise this real-like raw identity end to end.

The layer-name boundary was then remediated after the live read-only setup
probe established that the approved source legitimately uses the AutoCAD layer
name `Duong manh`. The previous identifier-only validator rejected that name
before File IPC, so a truthful fixture could not reach the inspection gate.
Commit `a17032275a628328dcad0fd15166e413faee3663` changes only
`source_layer_expectations` and observed `layers` to a closed safe-text
contract: 1-512 printable characters, with empty, control-character,
malformed-array, and unknown-field inputs rejected. Group IDs, component IDs,
handles, and entity-type tokens remain identifier-strict. Python, JSON schema,
and C# validators now share the boundary, with `Duong manh` regression tests.

## Interfaces and fixture contract

The gate reuses the existing `DotNetIPCClient`, `FileIPCLiveMCPClient`, Windows
trigger helpers, standalone adapter, DARA, component-view registry, candidate
revision, and drawing-query owners. It adds no transport or truth store.

The private fixture must contain exactly these logical fields:

- `project_id`, `drawing_id`, `candidate_id`;
- `inspection_request`, `extraction_plan`;
- `source_upstream_evidence`, `observation_evidence_sha256`;
- `candidate_upstream_evidence`, `candidate_observation_evidence_sha256`;
- `query`.

The opt-in environment additionally supplies the File IPC roots, AutoCAD HWND
and LISP path, fixture path, approved source path/hash/setup-audit hash, and
disposable candidate root. The gate reports each absent or invalid prerequisite
as `SKIP`; it does not turn an unavailable live session into a PASS.

## Evidence and verification

Evidence captured on the layer-name remediation head
`a17032275a628328dcad0fd15166e413faee3663`:

- `scripts/verify.ps1`: exit `0`, all checks passed.
- Full offline Python suite: `3278 passed`, `21 deselected`, `74 subtests`.
- Offline IPC JUnit: `134` tests, `0` failures, `0` errors, `0` skipped.
- Full C# solution: `238 passed`, `0` failed, `0` skipped.
- Layer-name remediation focused set: Python/C# cross-language contract tests
  passed (`97` Python tests in the focused owner set; `49` C# contract tests).
- Read-only live preparation: approved `BVTL.dwg` opened with source hash
  `78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8`, .NET
  `health` and `drawing_setup_audit` succeeded with `changed=false` and
  `DBMOD=0`. The standalone live gate remained `NOT RUN` because the truthful
  private fixture was absent; no inspection, extraction, candidate creation,
  source save, or accepted-drawing mutation occurred. The detailed private
  preparation record is outside Git at
  `C:\temp\cad-agent-task6-live-20260911\task6-live-prep-20260911.txt`.
- `autocad_mechanical` unavailable-state probe: `17 skipped`; live marker
  `NOT RUN` because the AutoCAD/File IPC session was not prepared.
- Real-data/private gates: `2 skipped` because their private inputs were not
  supplied.
- Causal trigger RED oracle: `1 expected failing negative test`, retained as
  an intentional oracle and not counted as a product failure.
- Python 3.11.9, .NET SDK 10.0.302, and repository Ruff checks passed.
- `git diff --check`: pass; verification left the repository clean.

The preceding hash-binding and candidate-identity remediations had SOL status
`VERDICT=PASS`, with `MATERIAL_FINDING=NONE` and `HUMAN_GATE=NO`. SOL's fresh
review then identified the real layer-name incompatibility and requested this
single contract remediation; the remediation is now locally verified and
awaits fresh SOL review. No live CAD verdict is inferred from these offline
results.

## Reuse dossier classification

Classification: reuse-first, thin orchestration test gate. Existing owners
remain responsible for request/result schemas, source freshness, candidate
serialization/readback, cleanup policy, DARA custody/currentness, R3 registry
binding, R4 candidate revision state, and bounded entity reads. The new file
only coordinates those owners and records truthful live availability.

## State and remaining risk

Source and accepted drawings were not modified. No private artifact was added
to Git. No production candidate was promoted.

The remaining risk is explicitly live-gated: the approved `BVTL.dwg` source,
AutoCAD Mechanical 2027 session, operator fixture, and File IPC prerequisites
were not available in this run. Therefore this record is implementation and
offline-contract evidence, not live CAD acceptance or release evidence.
