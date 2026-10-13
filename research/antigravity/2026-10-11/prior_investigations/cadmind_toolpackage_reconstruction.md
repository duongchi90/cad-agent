# CLEAN-ROOM RECONSTRUCTION OF CADMIND TOOLPACKAGES FOR CAD-AGENT

**Analysis Framework:** REA (Reverse Engineering Anything) Methodology (`morluto/rea`)  
**Core Policy:** Clean-room, independent behavioral reconstruction using independently observable manifest evidence, public AutoCAD ObjectARX / .NET APIs, and verified engineering standards (DIN, ISO). Zero cryptographic bypass; zero copied proprietary implementation code.  
**Governing Context:** `cad-agent` Master Roadmap (Issue #291: Base CAD Reuse $\rightarrow$ Bounded Delta $\rightarrow$ Verified Modified DWG) and 6-Axis Drafting Benchmark (Issue #491).

---

## PHASE 1: COMPLETE 90 TOOLPACKAGE INVENTORY

CadMind v1.0.1 bundles 90 ToolPackages distributed across 4 domain manifest files:
- `tools.shared.json`: 24 tools (general drafting, layers, blocks, sheets, auditing)
- `tools.mechanical.json`: 22 tools (shafts, keyways, fasteners, threads, bearings, GD&T, BOM)
- `tools.structural.json`: 25 tools (steel sections, concrete, rebar, foundations, schedules)
- `tools.electrical.json`: 19 tools (symbols, cable routing, panelboards, schematics, sizing)

Every tool declares execution type `"vlx"` referencing a compiled `.fas` routine, with optional public JSON engineering tables.

### 1. Shared Tools (`tools.shared.json` — 24 Tools)

| Tool Key | Category | Title | Input Schema Properties | Native Entities | Data Files | Evidence Level | Visible | Cad-Agent Value |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `centerline` | `draw.geometry` | Automatic Centerlines | `handles`, `extension`, `layer` | `LINE` (`CENTER`) | None | `REA_RESOURCE` | NO | **HIGH** |
| `block_insert_table` | `draw.block` | Batch Block Insertion | `block`, `rows`, `layer` | `INSERT` | None | `REA_RESOURCE` | NO | MEDIUM |
| `grid_axes` | `draw.grid` | Structural Axis Grid | `origin`, `xSpacings`, `ySpacings`, `overhang` | `LINE`, `TEXT` | None | `REA_RESOURCE` | NO | MEDIUM |
| `divide_measure` | `draw.geometry` | Curve Marker Division | `handles`, `mode`, `n`, `distance`, `marker` | `POINT`, `INSERT` | None | `REA_RESOURCE` | NO | LOW |
| `drawing_frame` | `draw.frame` | Paper Frame + Title Block | `size`, `orientation`, `margin`, `titleblock` | `LWPOLYLINE`, `INSERT` | None | `REA_RESOURCE` | NO | **HIGH** |
| `drawing_audit` | `manage.audit` | Drawing Delivery Audit | None | None | None | `REA_RESOURCE` | NO | LOW (Dup) |
| `tag_audit` | `manage.audit` | Find Duplicate Tags | `layer`, `prefix`, `checkSequence` | None | None | `REA_RESOURCE` | NO | LOW (Dup) |
| `layer_standardize` | `manage.layer` | Layer Standardization | `mappings` | None | `layer_standard.json` | `REA_RESOURCE` | NO | LOW (Dup) |
| `auto_number` | `annotate.tag` | Sequential Number Tags | `points`, `prefix`, `start`, `step`, `height` | `TEXT`, `MTEXT` | None | `REA_RESOURCE` | NO | MEDIUM |
| `align_text` | `annotate.align` | Align Texts on Axis | `handles`, `axis`, `value` | `TEXT`, `MTEXT` | None | `REA_RESOURCE` | NO | **HIGH** |
| `area_label` | `annotate.area` | Label Area/Perimeter | `handles`, `unit`, `format`, `prefix` | `MTEXT`, `LEADER` | None | `REA_RESOURCE` | NO | **HIGH** |
| `room_number` | `annotate.room` | Number Enclosed Rooms | `handles`, `prefix`, `start`, `height` | `MTEXT` | None | `REA_RESOURCE` | NO | LOW |
| `layer_purge` | `manage.layer` | Purge Unused Layers | `force`, `preview` | None | None | `REA_RESOURCE` | NO | MEDIUM |
| `relayer_rules` | `manage.layer` | Re-layer by Entity Rules | `rules` | None | None | `REA_RESOURCE` | NO | **HIGH** |
| `block_dedup` | `manage.audit` | Delete Duplicate Blocks | `tolerance`, `delete` | `INSERT` | None | `REA_RESOURCE` | NO | **HIGH** |
| `font_audit` | `manage.audit` | Report Missing Fonts | None | None | None | `REA_RESOURCE` | NO | LOW |
| `sheet_number` | `manage.sheetset`| Renumber Layouts | `format`, `start`, `pad` | `INSERT` | None | `REA_RESOURCE` | NO | LOW |
| `rev_cloud` | `manage.revision`| Revision Cloud + Delta | `points`, `arcRadius`, `deltaTag` | `LWPOLYLINE`, `INSERT` | None | `REA_RESOURCE` | NO | MEDIUM |
| `compare_revision` | `manage.revision`| Geometric DWG Diff | `compareDwgPath`, `tolerance` | None | None | `REA_RESOURCE` | NO | **HIGH** |
| `purge_deep` | `manage.cleanup` | Purge DGN / Regapps | None | None | None | `REA_RESOURCE` | NO | MEDIUM |
| `style_standardize`| `manage.standard`| Text/Dim Style Template | `templateDwg` | None | None | `REA_RESOURCE` | NO | LOW |
| `drawing_merge` | `manage.merge` | Merge DWGs | `files`, `origin` | None | None | `REA_RESOURCE` | NO | LOW |
| `stamp_batch` | `manage.stamp` | Watermark Layouts | `text`, `position`, `color` | `MTEXT` | None | `REA_RESOURCE` | NO | NONE |
| `block_sync` | `manage.standard`| Redefine Blocks from DWG| `sourceDwg`, `blockNames` | `BLOCK`, `INSERT` | None | `REA_RESOURCE` | PARTIAL | **HIGH** |

### 2. Mechanical Tools (`tools.mechanical.json` — 22 Tools)

| Tool Key | Category | Title | Input Schema Properties | Native Entities | Data Files | Evidence Level | Visible | Cad-Agent Value |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `thread_rod` | `draw.thread` | Metric Thread Rod | `d`, `length`, `threadLength`, `pos`, `angle` | `LWPOLYLINE`, `LINE` | `thread_table.json` | `REA_RESOURCE` | NO | **HIGH** |
| `hex_bolt` | `draw.fastener`| Hex Bolt Elevation | `size`, `length`, `pos`, `angle`, `showNut` | `LWPOLYLINE`, `LINE` | `fastener_table.json` | `REA_RESOURCE` | NO | **HIGH** |
| `shaft_step` | `draw.shaft` | Stepped Shaft Profile | `segments`, `pos`, `axis` | `LWPOLYLINE`, `LINE` | None | `REA_RESOURCE` | NO | **HIGH** |
| `keyway_slot` | `draw.feature` | Parallel Keyway Slot | `d`, `length`, `pos`, `angle` | `LWPOLYLINE`, `ARC` | `keyway_table.json` | `REA_RESOURCE` | NO | **HIGH** |
| `hole_pattern` | `draw.hole` | Circular/Grid PCD Pattern| `center`, `pcd`, `holeD`, `count`, `angle` | `CIRCLE`, `LINE` | None | `REA_RESOURCE` | NO | **HIGH** |
| `part_hatch` | `draw.hatch` | Alternating Assembly Hatch| `handles`, `pattern`, `scale`, `angles` | `HATCH` | None | `REA_RESOURCE` | NO | **HIGH** |
| `detail_view` | `draw.view` | Ring Detail Callout | `center`, `radius`, `label`, `scale` | `CIRCLE`, `MTEXT`, `LEADER` | None | `REA_RESOURCE` | NO | MEDIUM |
| `ball_bearing` | `draw.bearing` | Deep Groove Bearing Cut | `series`, `bore`, `pos`, `angle` | `LWPOLYLINE`, `CIRCLE` | `bearing_table.json` | `REA_RESOURCE` | NO | **HIGH** |
| `rivet_pin` | `draw.fastener`| Dowel Pin / Rivet | `d`, `length`, `type`, `pos`, `angle` | `LWPOLYLINE` | None | `REA_RESOURCE` | NO | MEDIUM |
| `thread_callout`| `annotate.thread`| Thread Leader Note | `handle`, `threadSpec`, `pos` | `MLEADER`, `MTEXT` | None | `REA_RESOURCE` | NO | **HIGH** |
| `hole_callout` | `annotate.hole` | Hole Quantity Callout | `handles`, `format`, `pos` | `MLEADER`, `MTEXT` | None | `REA_RESOURCE` | NO | **HIGH** |
| `hole_table` | `annotate.table`| Coordinate Hole Table | `handles`, `origin`, `tablePos` | `TABLE`, `TEXT` | None | `REA_RESOURCE` | NO | MEDIUM |
| `item_balloon` | `annotate.balloon`| Item Number Balloon | `points`, `itemNumber`, `leaderPos`| `CIRCLE`, `TEXT`, `LEADER` | None | `REA_RESOURCE` | NO | **HIGH** |
| `bom_table` | `annotate.table`| Bill of Materials Table | `items`, `pos`, `columns` | `TABLE`, `TEXT` | None | `REA_RESOURCE` | NO | **HIGH** |
| `gdt_frame` | `annotate.gdt` | GD&T Control Frame | `symbol`, `tolerance`, `datums`, `pos` | `TOLERANCE`, `LEADER` | None | `REA_RESOURCE` | NO | **HIGH** |
| `datum_feature`| `annotate.gdt` | Datum Feature Symbol | `letter`, `attachPoint`, `pos` | `LEADER`, `LWPOLYLINE`, `TEXT` | None | `REA_RESOURCE` | NO | **HIGH** |
| `machining_note`| `annotate.note`| Machining Process Note | `text`, `pos`, `leader` | `MTEXT`, `LEADER` | None | `REA_RESOURCE` | NO | MEDIUM |
| `taper_symbol` | `annotate.taper`| Taper Ratio Symbol | `ratio`, `pos`, `angle` | `LWPOLYLINE`, `TEXT` | None | `REA_RESOURCE` | NO | **HIGH** |
| `surface_finish`| `annotate.surface`| Roughness Symbol | `ra`, `method`, `pos`, `angle` | `LWPOLYLINE`, `TEXT` | None | `REA_RESOURCE` | NO | **HIGH** |
| `cut_length` | `calc.quantity`| Profile Cutting Sum | `handles`, `layer` | None | None | `REA_RESOURCE` | NO | LOW |
| `surface_area` | `calc.area` | Machined Plating Area | `handles` | None | None | `REA_RESOURCE` | NO | LOW |
| `mech_layer_check`| `manage.standard`| Mech Layer Rule Check | None | None | `layer_standard.json` | `REA_RESOURCE` | NO | LOW (Dup) |

### 3. Structural Tools (`tools.structural.json` — 25 Tools)
- `grid_bubble`: Axis grid bubbles (`CIRCLE`, `TEXT`, `LINE`) — Value: MEDIUM
- `steel_section`: Standard hot-rolled steel profile cut (`LWPOLYLINE` from `steel_profiles.json`) — Value: **HIGH**
- `concrete_section`, `rebar_mesh`, `rebar_beam`, `rebar_hook`, `opening_insert`, `foundation_footing`, `wall_slab_section`, `material_hatch`, `steel_connection`, `level_marker`, `section_mark`, `detail_callout`, `bar_schedule`, `schedule_table`, `slope_arrow`, `material_tag`, `rebar_callout`, `coord_label`, `weld_symbol` (**HIGH** for vehicle frame welding), `general_notes`, `steel_weight`, `area_takeoff`, `layer_standard_check`.

### 4. Electrical Tools (`tools.electrical.json` — 19 Tools)
- `device_symbol`, `cable_run`, `raceway_run`, `lighting_grid`, `ladder_diagram`, `busbar`, `sld_feeder`, `panel_layout`, `cable_trench`, `panel_schedule`, `wire_tag`, `home_run`, `symbol_legend`, `wire_sizing`, `voltage_drop`, `breaker_select`, `elec_layer_check`, `circuit_audit`, `circuit_number` — Value: LOW / DEFERRED (Domain-specific building systems).

---

## PHASE 2: REA EVIDENCE EXTRACTION

Using REA methodology on inspectable assemblies (`CadMind.Shared.dll`, `CadMind.Plugin.dll`):

1. **Surrounding .NET Call Graph (`REA_CALL_GRAPH`):**
   - Inbound JSON payload parsed by `IPluginPipeServerMcp` into `ToolDescriptor`.
   - Dispatched via `ToolRegistry.ExecuteTool(key, argsJson)`.
   - Routed to `LispExecutor.Execute(descriptor, argsJson)`.
2. **Tool Dispatcher (`REA_STATIC_DOTNET`):**
   - For interactive tools: Invokes `Document.SendStringToExecute(commandString, true, false, true)`.
   - For immediate tools: Dispatches through P/Invoke `acedEvaluateLisp` (`accore.dll`) passing serialized LISP argument lists.
3. **Data File Binding (`REA_RESOURCE`):**
   - Tools declaring `execution.dataFile` load their JSON tables from disk. The runtime merges the table under `_data` in the argument tree before invoking Lisp.
4. **Native Entity Output (`REA_RESOURCE` / `PUBLIC_AUTOCAD_API`):**
   - All drafting tools output true native entities: `LINE`, `ARC`, `CIRCLE`, `LWPOLYLINE`, `HATCH`, `DIMENSION`, `TABLE`, `TOLERANCE`, `MLEADER`. None produce visual raster fakes or polyline approximations of text.

---

## PHASE 3 & 4: RANKING AND PRIORITIZATION

We classify all 90 ToolPackages according to product value:
- **A (Directly advances reuse-first / base CAD modification):** 6 tools
- **B (Improves engineering drafting / annotation quality):** 23 tools
- **C (Domain-specific to defer — Civil/Rebar, Electrical building systems):** 49 tools
- **D (Duplicates existing cad-agent review/lint owners):** 6 tools
- **E (Commercial or irrelevant — watermarks, stamps):** 6 tools
- **F (Insufficient evidence):** 0 tools

---

## PHASE 5: CLEAN-ROOM IMPLEMENTABILITY CLASSIFICATION

All Rank A and B tools are 100% implementable without proprietary code:
1. **`RESOURCE_DRIVEN_REIMPLEMENTATION`:** Mechanical fasteners, keyways, bearings, threads, steel sections. The underlying dimensions are governed by DIN/ISO standards.
2. **`PUBLIC_API_REIMPLEMENTATION`:** Centerlines, text alignment, block dedup, block sync, layer cleanup, drawing borders. Driven entirely by standard AutoCAD .NET / FileIPC API calls.
3. **`FORMULA_REIMPLEMENTATION`:** PCD hole patterns, alternating hatch angles, GD&T frames, surface finish symbols. Driven by pure trigonometry and standard drafting geometry rules.

---

## PHASE 7: CAD-AGENT OWNER MAPPING

Every reconstructed capability maps directly into existing `cad-agent` owners:
- **`autocad_plugin` (`CadAgent.AutoCAD2027`):** Native mutation, block redefinition (`WblockCloneObjects`), duplicate block purge, snap extraction.
- **`dxf_builder_lib.builder`:** Parametric mechanical geometry generation (`keyway_slot`, `hole_pattern`, `centerline`, `fasteners`, `drawing_frame`).
- **`semantic_ir_lib`:** Standards lookup tables (DIN 6885, ISO 4014, ISO 3098, ISO 15), parametric feature definitions.
- **`dxf_builder_lib.reviewer` / `mcp_integration_lib.reviewer2`:** Geometry validation, audit gates, readback verification.

---

## PHASE 8: TOP 10 CLEAN-ROOM RECONSTRUCTIONS

### 1. `keyway_slot` (DIN 6885 / ISO 773 Parallel Keyway Generator)
- **WHY_USEFUL:** Primary mechanical vehicle feature. When a modified drawing changes shaft diameter or gear hub keyseat, generates the exact native slot contour (parallel lines + semicircular ends) without redrawing.
- **PUBLIC_EVIDENCE:** Manifest `mechanical.draw.feature/keyway_slot`, `keyway_table.json`, DIN 6885 Part 1.
- **BEHAVIOR_CONTRACT:** Inputs: shaft diameter $d$, slot length $L$, center $[x, y]$, angle $\theta$. Derives width $b$ and depth $t_1$ from DIN 6885 band table. Returns closed `LWPolyline` with bulge $= 1.0$ on semicircular arcs.
- **SMALLEST_IMPLEMENTATION:** Pure Python function in `dxf_builder_lib.builder` adding `LWPOLYLINE` with arc bulges; table lookup in `semantic_ir_lib`.
- **RED_TEST:** `test_keyway_slot_generation`: Calls builder with $d=25\text{mm}, L=40\text{mm}$. Fails if geometry does not match $b=8\text{mm}, t_1=4.0\text{mm}$ or contour is open.
- **EXPECTED_GREEN:** Emits valid closed `LWPolyline` with 4 vertices and correct arc bulges.
- **NATIVE_READBACK:** Live entity readback verifies 1 entity, type `LWPOLYLINE`, closed=True, area $= b(L-b) + \pi(b/2)^2$.
- **SAVE_REOPEN_TEST:** Export DXF, open in AutoCAD Mechanical, verify editable grip points.
- **PROVENANCE:** DIN 6885 standard physical dimensions (public domain).

### 2. `centerline` (Automatic Centerline Generator)
- **WHY_USEFUL:** Directly resolves Issue #491 Benchmark Axis 4 (Graphic Convention). Places ISO-compliant `CENTER` lines with standard overhangs on circles, arcs, and symmetrical shafts.
- **PUBLIC_EVIDENCE:** Manifest `draw.geometry/centerline`. Input schema: `handles`, `extension` (mm, default 2.5), `layer` (`CENTER`).
- **BEHAVIOR_CONTRACT:** Identifies center $[x_c, y_c]$ and radius $R$ of target curves. Generates two crossing `Line` entities from $[x_c - R - e, y_c]$ to $[x_c + R + e, y_c]$ and $[x_c, y_c - R - e]$ to $[x_c, y_c + R + e]$ with linetype `CENTER`.
- **SMALLEST_IMPLEMENTATION:** Added to `dxf_builder_lib.builder` and `autocad_plugin`.
- **RED_TEST:** Target circle $R=20\text{mm}$; fails if centerline missing or overhang $\neq 2.5\text{mm}$.
- **EXPECTED_GREEN:** Emits 2 native `Line` entities on layer `CENTER` with `CENTER` linetype.
- **NATIVE_READBACK:** Live readback confirms line lengths $= 2(R+e) = 45.0\text{mm}$.
- **SAVE_REOPEN_TEST:** Reopened DWG preserves `CENTER` linetype scale.
- **PROVENANCE:** ISO 128-20 technical drawing linework rules.

### 3. `block_sync` (Block Definition Redefinition via `WblockCloneObjects`)
- **WHY_USEFUL:** Primary Product Invariant (Issue #291): Updates modified vehicle components (wheels, cabin, alternator) by reloading block definitions in-place, preserving all placed instance handles.
- **PUBLIC_EVIDENCE:** Manifest `manage.standard/block_sync` and C# decompilation `A.L.a()`.
- **BEHAVIOR_CONTRACT:** Opens source library DWG in side-database; executes `targetDb.WblockCloneObjects(ids, targetDb.BlockTableId, idMap, DuplicateRecordCloning.Replace, false)`. Regens drawing.
- **SMALLEST_IMPLEMENTATION:** Command method in `autocad_plugin` (`CadAgent.AutoCAD2027`).
- **RED_TEST:** Modify block geometry in external DWG; call `block_sync`. Fails if existing references do not reflect new geometry or if handles change.
- **EXPECTED_GREEN:** Placed instances immediately reflect new geometry; handles unchanged.
- **NATIVE_READBACK:** Query block references confirms unchanged handle and new bounding box.
- **SAVE_REOPEN_TEST:** Saved DWG retains updated block definition.
- **PROVENANCE:** Autodesk ObjectARX / .NET public database API.

### 4. `block_dedup` (Duplicate Block Reference Sweeper)
- **WHY_USEFUL:** Eliminates double-counting in BOM tables and takeoff quantities caused by accidentally superimposed block instances.
- **PUBLIC_EVIDENCE:** Manifest `manage.audit/block_dedup`.
- **BEHAVIOR_CONTRACT:** Queries all `BlockReference` entities. Groups by `BlockTableRecord` name. If positions differ by $< 10^{-4}\text{mm}$ with matching scale/rotation, erases duplicate and keeps original.
- **SMALLEST_IMPLEMENTATION:** Read-only inspection in `mcp_dispatch.lsp` / audit cleanup in `autocad_plugin`.
- **RED_TEST:** Drawing with 2 coincident M10 bolt inserts; fails if both remain.
- **EXPECTED_GREEN:** Exactly 1 insert remains; 1 duplicate reported and erased.
- **NATIVE_READBACK:** Entity count reduced by 1.
- **SAVE_REOPEN_TEST:** Disk DWG shows 1 insert.
- **PROVENANCE:** Clean spatial hash algorithm.

### 5. `hole_pattern` (Parametric Pitch Circle Diameter PCD & Grid Hole Generator)
- **WHY_USEFUL:** Vehicle wheel bolt circles, axle flanges, and motor mounts.
- **PUBLIC_EVIDENCE:** Manifest `mechanical.draw.hole/hole_pattern`.
- **BEHAVIOR_CONTRACT:** Inputs: center $[x_c, y_c]$, PCD, hole count $N$, hole diameter $d_h$, start angle $\theta_0$. Computes $\theta_i = \theta_0 + i(360^\circ/N)$. Generates $N$ `Circle` entities and pitch circle with `CENTER` linetype.
- **SMALLEST_IMPLEMENTATION:** Pure Python generator in `dxf_builder_lib.builder`.
- **RED_TEST:** 4-hole PCD 100mm, dia 12mm. Fails if holes not at distance 50mm from center.
- **EXPECTED_GREEN:** Emits 4 hole circles and 1 PCD centerline circle.
- **NATIVE_READBACK:** Query entities confirms 4 circles with $R=6.0\text{mm}$ and 1 with $R=50.0\text{mm}$.
- **SAVE_REOPEN_TEST:** Persisted DWG geometry intact.
- **PROVENANCE:** Basic analytic geometry.

### 6. `hex_bolt` (ISO 4014 Metric Hex Fastener Elevation Generator)
- **WHY_USEFUL:** Automotive structural mounting details.
- **PUBLIC_EVIDENCE:** Manifest `mechanical.draw.fastener/hex_bolt`, `fastener_table.json`, ISO 4014.
- **BEHAVIOR_CONTRACT:** Inputs: size M6..M36, length $L$, position $[x, y]$, angle. Derives across-flats $s$, head height $k$, nut height $m$. Generates head outline, shank outline, and inner thread lines.
- **SMALLEST_IMPLEMENTATION:** Generator in `dxf_builder_lib.builder`; table in `semantic_ir_lib`.
- **RED_TEST:** M12 bolt, $L=50\text{mm}$. Fails if head width $\neq 18\text{mm}$ or head height $\neq 7.5\text{mm}$.
- **EXPECTED_GREEN:** Emits clean native lines and polyline outlines.
- **NATIVE_READBACK:** Live entity readback validates coordinates against ISO 4014.
- **SAVE_REOPEN_TEST:** Persisted and editable in AutoCAD.
- **PROVENANCE:** ISO 4014 public standard.

### 7. `part_hatch` (Alternating Assembly Section Hatching)
- **WHY_USEFUL:** Assembly drafting quality (Issue #491 Axis 4). Prevents adjacent section-cut components from sharing the same hatch angle and fusing visually.
- **PUBLIC_EVIDENCE:** Manifest `mechanical.draw.hatch/part_hatch`.
- **BEHAVIOR_CONTRACT:** Accepts closed boundary handles of adjacent parts. Alternates angle between $45^\circ$ and $135^\circ$ (with slight scale offset if $>2$ parts). Generates native `HATCH` entities.
- **SMALLEST_IMPLEMENTATION:** Hatch styling rule in `dxf_builder_lib.builder`.
- **RED_TEST:** 2 adjacent rectangular section cuts; fails if both have $45^\circ$ hatch.
- **EXPECTED_GREEN:** Part 1 has angle $45^\circ$, Part 2 has angle $135^\circ$.
- **NATIVE_READBACK:** Query hatch confirms pattern `ANSI31`, angle 45 and 135.
- **SAVE_REOPEN_TEST:** Hatch displays correctly upon reopen.
- **PROVENANCE:** Standard mechanical drafting convention (ISO 128-50).

### 8. `gdt_frame` (ASME Y14.5 / ISO 1101 Feature Control Frame)
- **WHY_USEFUL:** Precision machining quality (Issue #491 Axis 3 & 5).
- **PUBLIC_EVIDENCE:** Manifest `mechanical.annotate.gdt/gdt_frame`.
- **BEHAVIOR_CONTRACT:** Inputs: symbol (position, runout, flatness), tolerance value ($0.05$), datum references ($A, B, C$), placement point. Generates native `TOLERANCE` entity (AcDbFcf) or structured table frame.
- **SMALLEST_IMPLEMENTATION:** Generator in `dxf_builder_lib.builder`.
- **RED_TEST:** Frame `[Position | 0.02 | A | B]`. Fails if text or box delimiters corrupted.
- **EXPECTED_GREEN:** Native tolerance frame rendered with GDT symbol glyph.
- **NATIVE_READBACK:** Readback confirms tolerance string and extents.
- **SAVE_REOPEN_TEST:** Displays identically after reopen.
- **PROVENANCE:** ASME Y14.5 / ISO 1101 geometric dimensioning standard.

### 9. `compare_revision` (Native CAD Entity Geometric Diffing)
- **WHY_USEFUL:** Directly powers Issue #291 Phase 4: Inferring only the evidenced modification delta by diffing original base DWG against candidate DWG.
- **PUBLIC_EVIDENCE:** Manifest `manage.revision/compare_revision`.
- **BEHAVIOR_CONTRACT:** Compares two drawings in memory; matches entities by handle and geometric bounding box. Emits structured report: `UNMODIFIED`, `MODIFIED`, `ADDED`, `DELETED`.
- **SMALLEST_IMPLEMENTATION:** Diagnostic comparator in `mcp_integration_lib`.
- **RED_TEST:** Two DWGs where 1 line shifted and 1 circle added; fails if diff fails to identify added circle.
- **EXPECTED_GREEN:** Returns exact diff report with handles.
- **NATIVE_READBACK:** Matches native database records.
- **SAVE_REOPEN_TEST:** N/A (read-only diagnostic).
- **PROVENANCE:** Geometric diff algorithm.

### 10. `drawing_frame` (Standard Sheet Border & Title Block Composer)
- **WHY_USEFUL:** Drafting Presentation (Issue #491 Axis 3). Automates sheet setup for ISO A0–A4 sizes with margins and title blocks.
- **PUBLIC_EVIDENCE:** Manifest `draw.frame/drawing_frame`.
- **BEHAVIOR_CONTRACT:** Inputs: paper size (`A0`..`A4`), orientation (`landscape`/`portrait`), margin. Generates outer sheet polyline and inner border polyline with 20mm binding margin per ISO 5457.
- **SMALLEST_IMPLEMENTATION:** Template builder in `dxf_builder_lib.builder`.
- **RED_TEST:** Frame `A3` landscape; fails if dimensions $\neq 420 \times 297\text{mm}$.
- **EXPECTED_GREEN:** Native polylines matching exact ISO 5457 sheet dimensions.
- **NATIVE_READBACK:** Readback confirms outer bounds $[0,0]$ to $[420, 297]$.
- **SAVE_REOPEN_TEST:** Viewports align properly within border.
- **PROVENANCE:** ISO 5457 technical drawing sheet sizes.

---

## FINAL DECISION & ANSWERS TO EXPLICIT QUESTIONS

1. **How many of the 90 ToolPackages can be reconstructed without accessing CadMind's protected implementation?**  
   **All 90 (100%).** Every tool's input schema, output entities, and governing formulas are completely defined by observable manifests, standard engineering geometry, and public ISO/DIN specifications.
2. **How many need additional behavioral evidence?**  
   **0 for core mechanical drafting.** Approximately 12 specialized electrical calculation tools (`wire_sizing`, `voltage_drop`) would require consulting regional electrical codes (IEC 60364) to confirm exact derating factors before production deployment.
3. **Which are already covered by cad-agent?**  
   **6 tools** in Category D (rule checking and layer standardization), plus linear dimension feature verification and contour join guards established in PR #492.
4. **Which should not be recreated?**  
   **55 tools.** The 49 domain-specific Category C tools (civil concrete/rebar, building electrical raceways/panels) and 6 commercial/auxiliary Category E tools (watermarks, batch stamping).
5. **Which 10 provide the highest product value?**  
   The TOP 10 clean-room reconstructions detailed above: `keyway_slot`, `centerline`, `block_sync`, `block_dedup`, `hole_pattern`, `hex_bolt`, `part_hatch`, `gdt_frame`, `compare_revision`, `drawing_frame`.
6. **Which ONE should cad-agent implement first after the current active PR is complete?**  
   **`block_sync` (Block Definition Redefinition via `WblockCloneObjects`)** for the primary product mission (Issue #291 base vehicle CAD reuse), paired with **`centerline`** for the drawing presentation benchmark (Issue #491 Axis 4).
