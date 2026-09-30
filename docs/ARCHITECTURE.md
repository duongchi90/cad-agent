# CAD Agent Current Architecture

## Product path and responsibility

Fresh [#291](https://github.com/duongchi90/cad-agent/issues/291) defines the product;
[#461](https://github.com/duongchi90/cad-agent/issues/461#issuecomment-5915471764)
records the accepted cumulative BVTL run. This map describes existing owners. It
does not claim that all eight accepted modifications have a generic one-command API.

```text
modified source PDF + ORIGINAL native BASE
  -> source inspection + native BASE reconciliation
  -> source-bound scope/delta + protected invariants
  -> disposable native candidate + bounded existing native operations
  -> geometry/visual + applicable dimensions/text
  -> native editability/readback + save/reopen/readback
  -> deterministic protected-state/evidence verification
```

| Owner | Responsibility and current entry point |
| --- | --- |
| `cad_agent.pdf`, `primitive_ir_lib.run_pdf`, `cad_agent.source_bundle`, `cad_agent.source_integrity` | PDF rendering, source identity and supported observation artifacts; `run_pdf_stages`, `build_source_bundle`, source validation. |
| `cad_agent.source_fusion`, `cad_agent.source_fusion_proposal`, `cad_agent.source_support_verifier`, `cad_agent.source_verified_geometry` | Source reconciliation, proposed/verified source geometry; `compose_verified_native_line_delta` reuses native readback and source-supported geometry. |
| `cad_agent.native_dwg_provenance`, `cad_agent.base_cad_adapter` | Native file/readback binding (`build_native_dwg_provenance`, `compose_native_dwg_query_binding`) and reusable exact-base extraction/handoff validation. |
| `cad_agent.file_integrity`, `cad_agent.drawing_artifact_reference`, `cad_agent.component_view_registry`, `cad_agent.candidate_revision` | File identity and stage-specific source/currentness/R3/R4 bindings. Derived hash-bound artifacts are not independent authority databases. |
| `cad_agent.cad_read_facade`, `cad_agent.drawing_query`, `mcp_integration_lib.exact_base_xref`, `mcp_integration_lib.dotnet_ipc` | Native query/exact-base inspection and typed requests; `DotNetIPCClient.exact_base_xref_inspection`, `validate_xref_inspection`. |
| `mcp_integration_lib.mcp_client`, `mcp_integration_lib.mcp_dispatch.lsp` | FileIPC client/root/claim validation and existing LISP-to-.NET dispatch; `FileIPCLiveMCPClient`. Legacy fixture/raw-LISP paths still have callers and regressions. |
| `autocad_plugin/CadAgent.AutoCAD2027` | `CADAGENT_DISPATCH`, operation dispatcher, native exact-base reader, visual reader, bounded native LINE edit, command-context transactions and candidate SaveAs custody. |
| Authorized local Windows executor + native COM/AutoLISP | #461 source reasoning and bounded native geometry, dimension/annotation, and HATCHEDIT operations. The exact run helpers/scopes/readbacks live in its protected evidence packet outside Git. |
| `cad_agent.dimension_observer_run`, `cad_agent.fidelity`, `primitive_ir_lib.dimension_observer`, `dxf_builder_lib.builder` | Dimension inspection and separately approved staged DIMENSION/TEXT/HATCH reconstruction. Native #461 edits preserve native entity semantics. |
| `cad_agent.live` | Exclusive recoverable backup copying; staged DXF review/repair and save/reopen attestation. `repair_live` is a distinct, approval-gated staged path, not the accepted BVTL native executor. |
| `cad_agent.geometry_comparison_run`, `cad_agent.visual_evidence`, `mcp_integration_lib.autocad_render_evidence`, `.NET` native readback | Geometry, render and native evidence. #461 additionally preserves whole protected-native fingerprints and applicable source/native region comparisons. |
| `cad_agent.cli`, `cad_agent.manifest` | Staged command orchestration and resumable manifests; `python -m cad_agent`. No manifest or cached status may override fresh GitHub authority. |
| `agent_lib.run`, `agent_lib.batch_agent`, `primitive_ir_lib.vision_client` | Optional advisory vision/provider integration; paid/private prerequisites are explicit. Advice is not mutation/acceptance authority. |
| `agent_lib.codex_worker`, `cad_agent.vision_handoff`, `cad_agent.visual_supervisor_adapter`, `mcp_integration_lib.m3_live_harness` | Retained optional M3/provider custody and regression infrastructure. #461 did not require a paid repository provider; unmerged Responses PR #340 remains frozen. |

## Retained staged and safety infrastructure

`primitive_ir_lib`, `semantic_ir_lib`, `agent_lib`, `dxf_builder_lib`, and
`mcp_integration_lib` remain separate package owners. The staged path uses
`primitive_ir.schema.json`, `semantic_ir.schema.json`, and `agent_ir.schema.json`.
Native reuse, staged reconstruction, synthetic fixtures, and source inference
have different authority and acceptance conditions; they are not interchangeable.

The Drawing Initialization Gate, R3/R4 candidate contracts, Visual Supervisor,
and approved repair/publication validators remain reachable through library APIs
or tests. Historical proposed mission/envelope modules are absent from main;
the existing local-executor workflow retains its own bounded command allowlist.
Their presence does not make their historical implementation plans active work.
No duplicate owner or abstraction is removed without caller/supersession proof.

The hosted workflow calls `scripts/verify.ps1`; it does not simulate native CAD
acceptance. Existing local-executor/watchdog workflows still reference historical
#131/#294. Closing a ledger does not disable those workflow paths. Any runtime
retirement requires a separately evidenced and appropriately reviewed write-set.

## Navigation and historical boundaries

- Product scope: `docs/PROJECT.md`; acceptance and preservation: `docs/STATUS.md`
- Verification and environment: `docs/QUALITY.md`
- Current authority: latest #305/#429; material review protocol #392
- Prior detailed architecture: [historical ARCHITECTURE](history/architecture-before-bvtl-consolidation.md)
- Prior reuse inventory: `docs/superpowers/reuse/2026-08-04-reuse-inventory.json`

The archived architecture preserves historical VS-T0, setup and rollout contracts
without asserting that their old implementation state or future queue is current.
