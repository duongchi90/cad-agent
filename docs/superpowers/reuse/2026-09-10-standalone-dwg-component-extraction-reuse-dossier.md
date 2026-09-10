# Reuse dossier: standalone-DWG component extraction with provenance

Status: Task 0 complete; docs-only reuse decision for the approved implementation plan.

Date: 2026-09-10

Reviewed base: `400686ce8cc6c191b121b5ba11ab964dbfc521d4`

Approved design: `docs/superpowers/specs/2026-09-10-standalone-dwg-component-extraction-provenance-design.md`

Execution plan: `docs/superpowers/plans/2026-09-10-standalone-dwg-component-extraction-provenance.md`

This dossier contains repository-level reuse evidence only. It contains no
private drawing bytes, customer annotations, live CAD paths, generated DXF/DWG
files, or production approval.

## Decision

`NEW_MISSING_CAPABILITY` applies only to the narrow standalone-DWG component
extraction owner. The implementation must reuse the existing custody,
currentness, provenance, R3/R4, query, File IPC, dispatcher, path-policy, and
AutoCAD database authorities. No second parser, geometry engine, writer,
transport, registry, manifest, or truth store is selected.

The required measured extension is bounded to:

- `cad_agent/component_view_registry.py`: versioned
  `component-view-registry-standalone-dwg-1.0` with
  `STANDALONE_DWG_COMPONENTS` provenance.
- `cad_agent/candidate_revision.py`: explicit R4 recognition/binding for that
  exact R3 schema and mode.
- `tests/test_cad_agent_component_view_registry.py` and
  `tests/test_cad_agent_candidate_revision.py`: RED-first and GREEN/adversarial
  coverage.

Existing `NATIVE_DWG_FULL_DRAWING`, generated, base-CAD, and exact-base-Xref
behavior remains unchanged in intent and acceptance rules.

## Internal owner map

| Existing owner | Reuse decision and exact seam |
| --- | --- |
| `cad_agent/native_dwg_provenance.py` | `REFERENCE/REGRESSION_ONLY` for this capability. Its `validate_native_dwg_provenance`, `build_native_dwg_provenance`, `build_native_dwg_r3_inputs`, and `compose_native_dwg_query_binding` remain callable only for the existing full-drawing path and regression coverage; the standalone subset path must not call or copy them. Their `NATIVE_DWG_FULL_DRAWING` mode and empty R3 inputs remain unchanged. |
| `cad_agent/drawing_artifact_reference.py` | Reuse `issue_drawing_artifact_reference`, `validate_drawing_artifact_reference`, `observe_drawing_artifact_currentness`, `validate_drawing_artifact_current_observation`, and `require_current_drawing_artifact_reference` in two stages: source `BASELINE` reference/currentness before R3, then candidate `R3_CANDIDATE` reference/currentness only after the exact standalone `r3_provenance_binding` exists. Before R3, retain only raw hash-bound candidate output identity and the standalone inspection/extraction result checksum; do not fabricate a candidate DARA reference or create a second artifact-reference format. |
| `cad_agent/component_view_registry.py` | Reuse `build_component_view_registry`, `validate_component_view_registry`, `component_view_registry_sha256`, `component_view_registry_provenance_evidence`, `finalize_component_view_correspondence`, and `project_linked_view_impacts`. The measured gap is the required versioned standalone mode for non-empty selected components. |
| `cad_agent/candidate_revision.py` | Reuse `build_candidate_revision`, `validate_candidate_revision`, `build_candidate_revision_state`, `validate_candidate_revision_state`, and `transition_candidate_revision_state`. The measured gap is the explicit `_normalize_registry` branch for the exact standalone R3 schema/mode; unknown modes must not fall through to base-CAD. |
| `cad_agent/drawing_query.py` | Reuse `validate_entity_query`, `validate_drawing_observation`, `observe_drawing`, `validate_entity_query_result`, and `query_entities` only after candidate handles are bound. It is not a source extraction owner and is not changed by Task 0. |
| `mcp_integration_lib/dotnet_ipc.py` | Reuse `DotNetIPCClient.request`, `atomic_write_json`, `read_json_bounded`, `cleanup_request_files`, `_validate_operation`, `_validate_parameters`, `_poll_result`, path normalization, disposable leases, and closure validation. Add only thin methods for the two new operation names; do not add a second transport or polling model. |
| AutoCAD `.NET` IPC | Reuse `OperationDispatcher.Dispatch`, `ContractValidator`, `ContractModels`, existing request/result envelopes, leases, path normalization, and reparse-point guards. Route the new operations to a separate standalone reader; do not route them through `AutoCadExactBaseXrefReader`. |
| Existing exact-base-Xref owner | Reuse only as a boundary and regression oracle: `ExactBaseXrefPolicy`, `AutoCadExactBaseXrefReader`, exact-base schemas, and their tests remain unchanged. A standalone source with `XREF=0` is not relabeled as Xref. |

## AutoCAD/.NET reuse map

The new reader is an adapter over the existing AutoCAD `Database` boundary.
It does not call the full-drawing native-DWG provenance builders:

- `native_dwg_provenance.py` requires full-drawing custody, equal source and
  candidate entity counts/signatures, and a DXF candidate.
- `build_native_dwg_r3_inputs` intentionally emits empty components and views.
- Those contracts are correct for the existing full-drawing path but are not
  source/candidate provenance seams for selected-component extraction.
- Standalone currentness is therefore staged: the pre-R3 context binds the
  DARA source `BASELINE` reference/currentness plus raw hash-bound candidate
  output identity and the standalone inspection/extraction result checksum;
  after the required R3 registry/provenance evidence exists, the adapter
  issues and observes the candidate `R3_CANDIDATE` DARA reference with the
  exact `r3_provenance_binding`, then feeds that reference into R4 and
  `drawing_query`.

The AutoCAD-side reuse boundary is:

1. Open the standalone source read-only and validate its path/hash/currentness
   through the closed operation policy.
2. Select only explicit source handles/groups supplied by the closed packet.
3. Clone approved objects into a new disposable database using the existing
   AutoCAD database object model. Autodesk documents `Database.WblockCloneObjects`
   as the cross-database cloning API and requires an explicit destination owner;
   this matches the planned source-to-empty-candidate boundary.
4. Serialize only the disposable candidate to `candidate_output_path`, reopen
   it, hash/read back the result, and bind cleanup to the exact created-file
   identity. Autodesk documents `Database.SaveAs` as the database serialization
   operation; source and other-document saves remain forbidden by the closed
   policy.

The project already targets `net10.0-windows` and declares the AutoCAD
Mechanical 2027 product boundary. No new NuGet package, native DLL, parser,
transport, or external CAD engine is required by this reuse decision.

## External reuse decision

| Candidate | Source/revision | Decision | License/security/reproducibility impact |
| --- | --- | --- | --- |
| Autodesk AutoCAD .NET `Database.WblockCloneObjects` and `Database.SaveAs` | Official Autodesk Managed/ObjectARX documentation for AutoCAD 2027/2026 API surface, read 2026-09-10 | `EXTEND_WITH_ADAPTER`; use the already referenced Autodesk assemblies and existing database boundary | No source is vendored. The existing Autodesk runtime/reference boundary remains the compatibility owner. The implementation must prove explicit selection, destination ownership, candidate-only serialization, reopen/hash, and identity-bound cleanup. |
| .NET BCL file/path APIs | Official Microsoft `System.IO.FileOptions`/`FileStream` documentation, read 2026-09-10 | Reuse existing repository path, handle, hash, and reparse protections; no new library | No added package or license surface. Existing Windows file identity and reparse checks remain authoritative; no weaker path-only alias check is acceptable. |
| External DWG parser, writer, geometry engine, or second CAD transport | No external source selected | `NOT_SELECTED` | Introducing one would duplicate the AutoCAD authority, increase licensing/security/reproducibility cost, and violate the operating model. The missing capability is orchestration plus explicit lineage, not a new CAD engine. |
| OpenAI/Codex transport or provider | No runtime dependency selected | `NOT_SELECTED` | ChatGPT/SOL review is governance evidence only. File IPC remains the sole live CAD transport; no custom production Codex transport is introduced. |

Official references used for this decision:

- [Autodesk: Copy Objects Between Databases (.NET)](https://help.autodesk.com/view/ACD/2027/ENU/?caas=caas%2Fdocumentation%2FACD%2F2014%2FENU%2Ffiles%2FGUID-E02A8AAF-61FF-4C72-8960-0AEEBBEC2594-htm.html)
- [Autodesk: Database.SaveAs](https://help.autodesk.com/cloudhelp/2024/ENU/OARX-ManagedRefGuide/files/OARX-ManagedRefGuide-Autodesk_AutoCAD_DatabaseServices_Database_SaveAs_string__MarshalAsUnmanagedType_U1__bool_DwgVersion_Autodesk_AutoCAD_DatabaseServices_SecurityParameters.html)
- [Microsoft: FileOptions](https://learn.microsoft.com/en-us/dotnet/api/system.io.fileoptions?view=net-10.0)

## Measured gap and compatibility boundary

The current source tree proves the following gap without changing production
behavior:

- `component_view_registry.py` has explicit generated and native full-drawing
  modes. Native full-drawing validation rejects non-empty component lineage;
  its empty-component rule is intentional.
- `candidate_revision.py::_normalize_registry` explicitly recognizes the
  generated and native full-drawing schema versions. An unrecognized standalone
  registry falls through to the base-CAD handoff path, which cannot bind the
  standalone source identity.
- Therefore R3 and R4 must be extended together and version-bound. An R3-only
  extension would be an integration dead-end and is forbidden by this plan.
- The native-DWG full-drawing provenance module is not a callable subset
  extraction seam; it remains a reference/regression owner only.

Compatibility invariants:

- `NATIVE_DWG_FULL_DRAWING` keeps its full-drawing custody, equal-entity
  readback, empty-component R3 behavior, and existing R4 binding.
- Generated mode and base-CAD handoff keep their current schemas and failure
  behavior.
- Exact-base-Xref contracts and reader behavior remain unchanged.
- File IPC remains the only live transport and the disposable candidate is the
  only permitted serialization target.

## Stop conditions and measured reasons

Stop implementation and request a fresh bounded review if any of these occur:

1. The new R3 mode cannot be represented without weakening native full-drawing
   validation or adding unbounded fields.
2. The R4 branch cannot bind the same source identity, candidate identity,
   selected handles, and registry checksum without changing existing modes.
3. AutoCAD clone semantics are unclear for the selected object/group shape or
   the result cannot be reopened and hash-bound.
4. A second transport, parser, writer, provider, or truth store is proposed.
5. A source, accepted drawing, other document, or production target would be
   written.
6. An existing candidate base, candidate input identity, or candidate input
   hash is introduced; the approved model is `EMPTY_NEW_DATABASE`.
7. Private/live prerequisites are missing. Record `SKIP` or `NOT RUN`; never
   report a pass.

## Task 0 validation record

- Spec/plan review: SOL `VERDICT=PASS`, `MATERIAL_FINDING=NONE`,
  `HUMAN_GATE=NO` on commit `400686ce8cc6c191b121b5ba11ab964dbfc521d4`.
- Owner inspection: fresh `rg` inspection of the named Python, File IPC, and
  AutoCAD owner files at the reviewed base; the full-drawing native-DWG
  preconditions and empty R3 inputs were checked; no source files changed.
- Focused docs test: `tests/test_reuse_rebaseline_docs.py` — `3 passed`.
- Formatting: `git diff --check` — `PASS`.
- Private/live CAD gate: `NOT RUN` for Task 0; no live or private drawing
  evidence is claimed.
- Mutation boundary: docs-only dossier creation; no production code, CAD,
  source drawing, candidate, or DXF mutation.
