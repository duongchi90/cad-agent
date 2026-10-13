# DECISION-GRADE TECHNICAL EVIDENCE REPORT: CADMIND DECOMPILATION AUDIT & CAD-AGENT ADAPTATION

**Target Audience:** Product Owner (PO), Technical Lead, and Agent Core Engineers (`cad-agent`)  
**Context:** Verification of CadMind (`CadMind-Setup-Mcp-1.0.1.rar`) decompiled binaries (`CadMind.Shared.dll`, `CadMind.Plugin.dll`, `CadMind.Licensing.dll`, and 90 unpacked tool packages) against `cad-agent` architecture (`duongchi90/cad-agent`) and the 6-Axis Drafting Quality Benchmark (Issue #491).  
**Execution Guardrails:** `DO_NOT_IMPLEMENT = YES`, `DO_NOT_MODIFY_CAD_AGENT = YES`, `COMMERCIAL_FEATURES = OUT_OF_SCOPE`. No second CAD transport; no speculative rewrites.

---

## PART 1: CORRECTIONS TO PREVIOUS AUDIT REPORT (DOWNGRADES & OVERCLAIMS)

A strict decompilation and symbol-level analysis reveals several assumptions in the preliminary assessment that must be corrected to maintain engineering rigor.

| Claimed Feature | Previous Classification | Corrected Classification | Concrete Evidence & Rationale |
| :--- | :--- | :--- | :--- |
| **P/Invoke `acedEvaluateLisp`** | `VERIFIED_RUNTIME` | **`VERIFIED_SOURCE`** | `LispExecutor.cs` declares `[DllImport("accore.dll")] static extern int acedEvaluateLisp(...)`. While the C# P/Invoke signature and unmanaged call boundary are fully verified in source, live in-process execution on active AutoCAD 2025/2026/2027 sessions was not executed during static disassembly. Runtime thread affinity (AutoCAD main GUI thread) remains a strict operational prerequisite. |
| **90 ToolPackages Execution** | `VERIFIED_RUNTIME` | **`VERIFIED_RESOURCE` / `VERIFIED_BINARY`** | Unpacked `tools.*.json` manifests and accompanying `.fas` / `.json` data files are present on disk. However, the runtime engine decrypts `CadMindTools.enc` into `CadMind.Plugin.Tools.dll` via `O.A` $\rightarrow$ `o.a()` using an online license server ECDH exchange. On an unactivated machine, these tools cannot execute. Their existence is a verified resource, not proven runtime behavior. |
| **Universal In-Place Mutation** | Claimed "100% Entity Coverage" | **`IMPLEMENTATION_EXISTS` (Specific Entities Only)** | `DrawingProtocol.cs` (`op: "modify"`) supports only a strictly enumerated set: `Line`, `Circle`, `Arc`, `Ellipse`, `LWPolyline`, `Text`, `MText`, `Dimension`, and `Viewport`. 3D Solids, Regions, Meshes, Leaders (without MText), and Splines have no mutation property handlers. |
| **Topological Mixed Contour Linting** | Claimed "Zero Risk Boundary Lint" | **`IMPLEMENTATION_EXISTS` (LWPolyline Only)** | `geometry_lint` inspects `LWPolyline.Closed` and checks distance between vertex 0 and vertex $N-1$ ($|P_0 - P_{N-1}| < \text{gapTolerance}$). It does **not** construct a composite topological edge-graph to detect open contours formed by mixed chains of `LINE` + `ARC` entities. |
| **Dynamic Block Generation** | Inferred programmatically complete | **`IMPLEMENTATION_EXISTS` (Pre-authored References Only)** | `DynamicBlockPropertyIO.cs` mutates existing instances in `BlockTableRecord` using `DynamicBlockReferencePropertyCollection`. AutoCAD .NET API provides no programmatic API to define new Dynamic Block definitions (parameters/actions) from scratch; definitions must be pre-authored in DWG templates via AutoCAD GUI `BEDIT`. |

---

## PART 2: P0 DEEP DIVE (CORE TECHNICAL CONTRACTS)

### P0-A: IN-PLACE NATIVE MUTATION

#### 1. Exact Source Classes & Methods
- **Protocol Definition:** `CadMind.Shared.Drawing.Execution.DrawingProtocol` (`op: "modify"`).
- **Execution Engine:** `CadMind.Plugin.Core.Execution.Interface.IEditOp`, `IEditDispatcher`, dispatched via `A.M` and `CadMind.Plugin.Core.Documents.DocumentFactory`.

#### 2. Input Schema & Handled Properties
```json
{
  "op": "modify",
  "target": {
    "handles": ["2A1F"],
    "filter": { "layer": "WALLS", "type": "LWPOLYLINE" },
    "scopeSource": "user-explicit"
  },
  "props": {
    "radius": 15.0,
    "vertices": [[0, 0, 0], [10, 0, 0.414], [10, 10, 0]]
  }
}
```
**Supported Entities & Properties:**
- `Circle`: `center` `[x,y]`, `radius`, `diameter`, `circumference`, `area`.
- `Arc`: `center` `[x,y]`, `radius`, `startAngle` (degrees), `endAngle` (degrees).
- `Line`: `start` `[x,y]`, `end` `[x,y]`.
- `Ellipse`: `center`, `majorAxis`, `radiusRatio`, `startAngle`, `endAngle`.
- `LWPolyline`: `closed` (bool), `constantWidth` (double), `elevation` (double), `vertices` (`[[x,y]|[x,y,bulge]|[x,y,bulge,startW,endW], ...]`), `vertexAt` (`{ "index": 0, "point": [x,y], "bulge": 0.5 }`).
- `Text` / `MText`: `height`, `value`, `rotation`, `position`, `widthFactor`, `oblique`, `attachment`.
- `Dimension`: `textPosition`, `textRotation`, `dimScale`, `xline1Point`, `xline2Point`, `dimLinePoint`.
- `Viewport`: `scale`, `viewCenter`, `viewHeight`, `twistAngle`, `locked`, `on`, `freezeLayers`, `thawLayers`.

#### 3. Entity Lookup Mechanism
Resolves handle hex string via `database.GetObjectId(false, new Handle(Convert.ToInt64(handleHex, 16)), 0)`.

#### 4. Identity & Handle Preservation
**Verified Preserved:** The entity is opened with `transaction.GetObject(objectId, OpenMode.ForWrite)`. Property setters are called directly on the native object. `ObjectId` and `Handle` remain identical. No delete-and-recreate (`Erase` + `AppendEntity`) is performed.

#### 5. Transaction & Open Modes
Enclosed within an active `Autodesk.AutoCAD.DatabaseServices.Transaction`. The entity is opened in `OpenMode.ForWrite`.

#### 6. Validation Before Mutation
- Entity type assertion against requested property schema (e.g. rejecting `bulge` on `Circle`).
- Handle validity check (`objectId.IsValid && !objectId.IsErased`).
- Guarded `scopeSource` required if `target` uses `filter` instead of `handles`. Valid values: `"selection"`, `"layout:<name>"`, `"view"`, `"user-explicit"`. Without `scopeSource`, batch modification is rejected.

#### 7. Validation After Mutation
In-transaction property readback verifying the assigned value matches the internal entity property within numeric tolerance ($10^{-9}$).

#### 8. Failure & Rollback Behavior
Any validation failure throws an exception, triggering `transaction.Abort()`. The database state reverts to pre-mutation state. In draw batches, the entire batch is wrapped in an AutoCAD `UndoController` mark (`undoSteps`).

#### 9. Smallest Reusable Contract for `cad-agent`
`cad-agent` currently features `ApplyBoundedNativeLineEdit` in [CommandContext.cs](file:///c:/Users/duong/Desktop/autocad/GG%20Antigravity/cad_agent_cmd_ctx.cs).  
The smallest contract to adapt is expanding `CommandContext.cs` to handle `Arc`, `Circle`, and `LWPolyline` (vertex bulge/point) using the identical 4-stage validation pattern (hash check, in-transaction readback, active commit readback, side-db reload readback).

---

### P0-B: READ SNAP POINTS (`read_snap_points`)

#### 1. Schema & Parameters
- **Source:** `CadMind.Shared.ToolRuntime.Store.Catalog.ReadFeatureCatalog.SnapPointsSchema`.
- **Inputs:** `near` `[x,y]` XOR `window` `[x1,y1,x2,y2]`, `radius` (default 1000), `kinds` (`["end", "mid", "center", "quadrant", "insert", "node"]`), `layers` (string array with wildcards), `limit` (default 40, max 200).

#### 2. Technical Evaluation
1. **Recursion:** Traverses nested `BlockTableRecord` definitions when encountering `BlockReference`.
2. **Coordinate Transformation:** Multiplies coordinates by cumulative `BlockReference.BlockTransform` matrix ($M = M_{parent} \times M_{child}$) to project child geometry into WCS.
3. **Xref Handling:** Supports both local `BlockReference` and external references (`IsFromExternalReference == true`).
4. **Supported Geometry:** `Line` (endpoints, midpoint), `Arc` (endpoints, midpoint, center), `Circle` (center, 4 quadrants), `LWPolyline` (vertices, segment midpoints), `BlockReference` (insertion point), `DBPoint` (node).
5. **Duplicate Point Merging:** Uses a spatial grid / distance tolerance ($< 10^{-4}$ units). Returns collapsed canonical points with an integer `stacked` count.
6. **Recursion Guard:** Depth limit capped at 16 levels; visited `BlockTableRecord.ObjectId` hash set prevents circular reference hangs.
7. **Scale / Mirror / Rotation:** The $4 \times 4$ `BlockTransform` matrix natively handles arbitrary rotation, non-uniform scaling, and negative scaling (mirroring) via affine coordinates.
8. **Read-Only Safety:** 100% read-only (`OpenMode.ForRead`); leaves database and selection sets unmodified.

#### 3. Implementation Pseudocode for `cad-agent`
```csharp
public struct SnapPoint {
    public Point3d Location;
    public string Kind;       // "end", "mid", "center", "quadrant", "insert", "node"
    public string Layer;
    public string Handle;
    public int StackedCount;
}

public List<SnapPoint> ExtractSnapPoints(Database db, Point2d? near, double radius, double[] window, HashSet<string> kinds, int limit) {
    var results = new List<SnapPoint>();
    var visitedBlocks = new HashSet<ObjectId>();
    
    using (var tr = db.TransactionManager.StartTransaction()) {
        var bt = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
        var ms = (BlockTableRecord)tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForRead);
        
        ExtractFromBlockRecord(ms, Matrix3d.Identity, 0);
        tr.Commit();
    }
    
    // Merge coincident points within epsilon = 1e-4
    return CollapseDuplicatesAndRank(results, near, window, limit);
    
    void ExtractFromBlockRecord(BlockTableRecord btr, Matrix3d currentTransform, int depth) {
        if (depth > 16 || visitedBlocks.Contains(btr.ObjectId)) return;
        visitedBlocks.Add(btr.ObjectId);
        
        foreach (ObjectId id in btr) {
            var ent = (Entity)tr.GetObject(id, OpenMode.ForRead);
            if (!ent.Visible) continue;
            
            if (ent is Line line) {
                if (kinds.Contains("end")) {
                    results.Add(new SnapPoint { Location = line.StartPoint.TransformBy(currentTransform), Kind = "end", Layer = ent.Layer, Handle = ent.Handle.ToString() });
                    results.Add(new SnapPoint { Location = line.EndPoint.TransformBy(currentTransform), Kind = "end", Layer = ent.Layer, Handle = ent.Handle.ToString() });
                }
                if (kinds.Contains("mid")) {
                    var mid = line.StartPoint + (line.EndPoint - line.StartPoint) * 0.5;
                    results.Add(new SnapPoint { Location = mid.TransformBy(currentTransform), Kind = "mid", Layer = ent.Layer, Handle = ent.Handle.ToString() });
                }
            } else if (ent is Arc arc) {
                if (kinds.Contains("center")) results.Add(new SnapPoint { Location = arc.Center.TransformBy(currentTransform), Kind = "center", Layer = ent.Layer, Handle = ent.Handle.ToString() });
                if (kinds.Contains("end")) {
                    results.Add(new SnapPoint { Location = arc.StartPoint.TransformBy(currentTransform), Kind = "end", Layer = ent.Layer, Handle = ent.Handle.ToString() });
                    results.Add(new SnapPoint { Location = arc.EndPoint.TransformBy(currentTransform), Kind = "end", Layer = ent.Layer, Handle = ent.Handle.ToString() });
                }
            } else if (ent is Circle circle) {
                if (kinds.Contains("center")) results.Add(new SnapPoint { Location = circle.Center.TransformBy(currentTransform), Kind = "center", Layer = ent.Layer, Handle = ent.Handle.ToString() });
                if (kinds.Contains("quadrant")) {
                    results.Add(new SnapPoint { Location = (circle.Center + Vector3d.XAxis * circle.Radius).TransformBy(currentTransform), Kind = "quadrant", Layer = ent.Layer, Handle = ent.Handle.ToString() });
                    results.Add(new SnapPoint { Location = (circle.Center - Vector3d.XAxis * circle.Radius).TransformBy(currentTransform), Kind = "quadrant", Layer = ent.Layer, Handle = ent.Handle.ToString() });
                    results.Add(new SnapPoint { Location = (circle.Center + Vector3d.YAxis * circle.Radius).TransformBy(currentTransform), Kind = "quadrant", Layer = ent.Layer, Handle = ent.Handle.ToString() });
                    results.Add(new SnapPoint { Location = (circle.Center - Vector3d.YAxis * circle.Radius).TransformBy(currentTransform), Kind = "quadrant", Layer = ent.Layer, Handle = ent.Handle.ToString() });
                }
            } else if (ent is BlockReference blkRef) {
                if (kinds.Contains("insert")) results.Add(new SnapPoint { Location = blkRef.Position.TransformBy(currentTransform), Kind = "insert", Layer = ent.Layer, Handle = ent.Handle.ToString() });
                var childBtr = (BlockTableRecord)tr.GetObject(blkRef.BlockTableRecord, OpenMode.ForRead);
                ExtractFromBlockRecord(childBtr, currentTransform * blkRef.BlockTransform, depth + 1);
            }
        }
        visitedBlocks.Remove(btr.ObjectId);
    }
}
```

---

### P0-C: BLOCK REUSE & DYNAMIC PROPERTY MUTATION

#### A. Block Definition Reuse & Redefinition
- **Mechanism:** Implemented in `A.L.a(Database targetDb, string blockName, string sourceDwgPath, out string err)`.
- **Import Strategy:** Opens source DWG into a temporary side-database (`new Database(false, true)` $\rightarrow$ `ReadDwgFile`).
- **Clone Method:** Uses `targetDb.WblockCloneObjects(ids, targetDb.BlockTableId, idMap, DuplicateRecordCloning.Replace, false)`.
- **Propagation:** Because `DuplicateRecordCloning.Replace` (value `1`) replaces the existing `BlockTableRecord` contents in place, all existing `BlockReference` entities referencing that block instantly reflect the new geometry upon view regeneration without requiring reinsertion or handle modification.
- **Attributes:** If attribute definitions are modified, `ATTSYNC` must be invoked. Native geometry updates immediately.

#### B. Dynamic Block Reference Property Editing
- **Mechanism:** Implemented in `CadMind.Plugin.Core.Blocks.DynamicBlockPropertyIO`.
- **Property Collection:** Iterates `BlockReference.DynamicBlockReferencePropertyCollection`.
- **Supported Property Types:**
  - `UnitsType == 1` (Angle): Automatically converts radians to degrees and vice versa.
  - Real / Distance / Length: Assigned as double.
  - Integer / Count: Assigned as int.
  - String / Visibility: Matches against `prop.GetAllowedValues()`.
- **Validation Guard:** Checks `prop.ReadOnly`. Validates proposed value against `prop.GetAllowedValues()` if constraints exist.
- **Post-Edit Readback:** Immediately reads back `prop.Value` to ensure AutoCAD geometry engine accepted the dynamic constraint change.

#### C. Architectural Limits
- AutoCAD ObjectARX / .NET does **not** provide APIs to programmatically author dynamic block definitions (parameters, actions, stretch grips) from scratch.
- Dynamic blocks must be pre-authored in DWG block libraries. CadMind's capability is strictly:
  1. Importing pre-authored definitions from `.dwg` files using `WblockCloneObjects(Replace)`.
  2. Modifying runtime properties on placed instances via `DynamicBlockReferencePropertyCollection`.

---

### P0-D: DIMENSION TRUTH & AUDIT (`dim_audit`)

#### 1. AutoCAD Stored vs Displayed Semantics
A native `Dimension` entity contains two key properties:
1. `Dimension.Measurement` (`double`): The true geometric distance/angle calculated by AutoCAD directly from the definition points (`Xline1Point`, `Xline2Point`, etc.).
2. `Dimension.DimensionText` (`string`): The text override property.
   - If `DimensionText == ""` or `null`: AutoCAD displays the dynamically measured value according to the current `DimensionStyle`.
   - If `DimensionText` contains `<>`: The `<>` token acts as a placeholder for the true measurement. Any surrounding characters are decorations (e.g. `"2x <>"`, `"<> (REF)"`, `"TYP. <>"`, `"%%c<>"`, `"+0.02/-0.01 <>"`).
   - If `DimensionText` is non-empty and does **NOT** contain `<>`: The designer has manually forced a static number (e.g., measured 50.0 mm, but text forced to `"45.0"`). This is a **hard fraudulent override**.

#### 2. False Positive Protections
An audit tool must **not** flag valid engineering annotations as overrides.
- **Allowed / Non-Fraudulent Overrides:**
  - Measurement tokens containing `<>` (prefixes, suffixes, reference brackets).
  - Tolerance annotations formatted around `<>`.
  - MText formatting codes (`\A1;`, `\P`, `\C1;`).
- **Fraudulent / Stated Value Violations:**
  - `DimensionText` has numerical text without `<>`.
  - `Dimension.Measurement <= 0.0`.
  - Stated room area labels (`TEXT` / `MTEXT` containing `"XX m²"`) placed inside a closed polyline where the text value deviates from the polyline's native `Area` by more than `tolerancePercent` (default 2%).

#### 3. Audit Algorithm for `cad-agent`
```csharp
public struct DimAuditFinding {
    public string Handle;
    public double MeasuredValue;
    public string DisplayedText;
    public bool IsFraudulentOverride;
    public string Note;
}

public List<DimAuditFinding> AuditDimensionTruth(Database db, string layerFilter) {
    var findings = new List<DimAuditFinding>();
    using (var tr = db.TransactionManager.StartTransaction()) {
        var bt = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
        var ms = (BlockTableRecord)tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForRead);
        
        foreach (ObjectId id in ms) {
            var ent = tr.GetObject(id, OpenMode.ForRead);
            if (ent is Dimension dim) {
                if (!string.IsNullOrEmpty(layerFilter) && !string.Equals(dim.Layer, layerFilter, StringComparison.OrdinalIgnoreCase))
                    continue;
                    
                string text = dim.DimensionText ?? "";
                double measured = dim.Measurement;
                
                if (measured <= 1e-6) {
                    findings.Add(new DimAuditFinding {
                        Handle = dim.Handle.ToString(),
                        MeasuredValue = measured,
                        DisplayedText = text,
                        IsFraudulentOverride = true,
                        Note = "Zero or negative native measurement"
                    });
                } else if (!string.IsNullOrWhiteSpace(text) && !text.Contains("<>")) {
                    findings.Add(new DimAuditFinding {
                        Handle = dim.Handle.ToString(),
                        MeasuredValue = measured,
                        DisplayedText = text,
                        IsFraudulentOverride = true,
                        Note = $"Hard override detected: measured {measured:F2}, forced text '{text}'"
                    });
                }
            }
        }
        tr.Commit();
    }
    return findings;
}
```

---

### P0-E: GEOMETRY LINT (`geometry_lint`)

| Feature | Source Method / Class | Input Entity Types | Algorithm | Tolerance | Mode | False Positives | False Negatives | `cad-agent` Value |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Open Loops** | `geometry_lint` (`ManageFeatureCatalog.cs`) | `LWPolyline` | Checks `!poly.Closed && (poly.StartPoint - poly.EndPoint).Length < gapTolerance` | Default `1.0` drawing unit | Read-Only | Deliberately open contour runs ending near their start | Mixed `LINE` + `ARC` unclosed chains | **HIGH** (Area/Hatch reliability) |
| **Zero-Length Curves** | `geometry_lint` | `Line`, `Arc`, `LWPolyline` | Checks `line.Length < 1e-6` or `arc.Length < 1e-6` | $10^{-6}$ units | Read-Only | None | Micro-segments slightly above epsilon | **HIGH** (Clean DXF export) |
| **Off-Plane Entities** | `geometry_lint` | All curves, texts, blocks | Checks $|StartPoint.Z| > 1e-6$ or $|EndPoint.Z| > 1e-6$ | $10^{-6}$ units | Read-Only | Intentional 3D elevations | None in 2D drawings | **HIGH** (Prevents fillet/trim errors) |
| **Stacked Duplicates** | `geometry_lint` | `Line`, `Circle`, `Arc` | Spatial hash of bounding box + endpoint coincidence | $10^{-4}$ units | Read-Only | Coincident entities on different viewports/layers | Slight endpoint offsets | **HIGH** (Prevents double quantity takeoff) |
| **Cross-Layer Duplicates** | `geometry_lint` | All curves | Duplicate geometry present on two distinct layers | $10^{-4}$ units | Read-Only | Intentional background tracing layers | Minor geometric variations | **MEDIUM** (Quantity audit) |
| **Layer Outliers** | `geometry_lint` | All entities on layer | Calculates majority entity type per layer; flags minority deviations (e.g. 1 hatch on conduit layer) | Statistical mode threshold | Read-Only | Multi-entity component layers | Highly mixed layers with no majority | **MEDIUM** (Heuristic quality triage) |

**Contour Closure Analysis:**  
CadMind inspects `LWPolyline` entities directly. It does **not** perform topological graph traversal across disparate `LINE` and `ARC` entities. If an agent drafts an outline using separate lines and arcs, `geometry_lint` will not detect an open gap between line ends. For `cad-agent`, topological contour closure should be handled in `semantic_ir_lib` or through `PEDIT` boundary joining.

---

## PART 3: P1 DRAFTING CATALOGS & ENGINEERING TABLES

### 1. Catalog Verification Summary

| Catalog Name | Decompiled Source File | Verified Values / Schema | Standard Reference | Safe to Adapt? | Recommended `cad-agent` Owner |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`TextHeights`** | `CadMind.Shared.Drawing.Text.TextHeights.cs` | `[1.8, 2.5, 3.5, 5.0, 7.0, 10.0, 14.0, 20.0]` | ISO 3098 / TCVN 7284 (ratio $\sqrt{2}$) | **YES** (Standard public domain numbers) | `semantic_ir_lib` / `dxf_builder_lib` |
| **`TextRoleCatalog`** | `CadMind.Shared.Drawing.Text.TextRoleCatalog.cs` | `title` (7.0, bold), `subtitle` (5.0, bold), `header` (3.5, bold), `body` (2.5), `small` (1.8) | ISO drafting conventions + VN aliases | **YES** (Clean reimplementation) | `semantic_ir_lib` |
| **`DimArrowCatalog`** | `CadMind.Shared.Drawing.Dimensioning.DimArrowCatalog.cs` | 18 arrows: `closedFilled`, `archTick` (`_ARCHTICK`), `dot` (`_DOT`), `none` (`_NONE`), etc. | AutoCAD native block naming | **YES** (AutoCAD built-in identifiers) | `dxf_builder_lib` / `autocad_plugin` |
| **`HatchMaterialCatalog`** | `CadMind.Shared.Drawing.Hatching.HatchMaterialCatalog.cs` | 31 presets: `concrete` (`AR-CONC`), `steel` (`ANSI32`), `brick` (`ANSI31`), `earth` (`EARTH`, $45^\circ$), etc. | Standard PAT patterns | **YES** | `semantic_ir_lib` / `dxf_builder_lib` |
| **`HatchUnitScale`** | `CadMind.Shared.Drawing.Hatching.HatchUnitScale.cs` | Factor: `UnitsPerInch(insunits)` (25.4 for metric mm), with auto-scaling for imperial patterns | Autodesk PAT specification | **YES** (Mathematical formula) | `dxf_builder_lib` / `autocad_plugin` |
| **`LinetypeCatalog`** | `CadMind.Shared.Drawing.Linework.LinetypeCatalog.cs` | `CONTINUOUS`, `CENTER`, `DASHED`, `HIDDEN`, `PHANTOM`, ISO 128 patterns (`ACAD_ISO02W100`..15) | ISO 128 / `acadiso.lin` | **YES** | `dxf_builder_lib` / `autocad_plugin` |
| **`VietEncoding`** | `CadMind.Shared.Text.VietEncoding.cs` | TCVN3 (ABC `.Vn*`) & VNI (`VNI-*`) to Unicode mappings | Legacy font encodings | **YES** | `semantic_ir_lib` |
| **Engineering Tables** | ToolPackages `*.json` | `keyway_table.json`, `fastener_table.json`, `steel_profiles.json`, `bearing_table.json` | DIN 6885, ISO 4014, EN 10210, ISO 15 | **YES** (Public dimensional standards) | `semantic_ir_lib` / `mcp_integration_lib` |

### 2. Provenance & Licensing Risk Assessment
- **Public Domain Engineering Standards:** Nominal text heights (ISO 3098), standard linetypes (ISO 128), and bolt/steel dimensions (DIN/ISO/ASTM) are international physical engineering standards. They are free from copyright restrictions.
- **AutoCAD Standard Identifiers:** Arrowhead block names (`_ARCHTICK`, `_DOT`) and hatch pattern names (`ANSI31`, `AR-CONC`) are standard AutoCAD naming conventions.
- **Implementation Caution:** Reimplement clean C# / Python definitions rather than copying binary decompiled source files directly.

---

## PART 4: P2 TOOL DISCOVERY DECISION

### Decision: `NOT_NEEDED` for `cad-agent` Today

#### Technical Dissection of CadMind's Discovery Mechanism
- **Implementation:** `ToolSearchIndex.cs` implements an in-memory BM25 ranker ($k_1 = 1.2$, $b = 0.75$) indexing 90 tool packages.
- **Index Fields:** `key`, `title`, `description`, `tags`, `examples`.
- **Why CadMind Needed It:** CadMind attempted to act as a monolithic conversational assistant exposing 90+ heterogeneous domain tools (electrical conduit routers, structural rebar detailers, mechanical keyway generators) in one general agent prompt. Exposing all schemas simultaneously exceeds model context limits.

#### Why `cad-agent` Should Reject BM25 Discovery
1. **Deterministic Staged Pipeline:** `cad-agent` is structured around explicit, predictable CLI workflows (`run-pdf`, `fidelity-benchmark`) and bounded edit operations. It is not an unconstrained chat assistant.
2. **Context Efficiency via Strict Tools:** `cad-agent` maintains high drafting accuracy specifically because its tool interface is lean, deterministic, and tightly validated.
3. **Dispatch Latency & Hallucination Risk:** Dynamic tool retrieval introduces retrieval failures (BM25 false positives) and non-deterministic agent tool calling.
4. **Conclusion:** Keep tools statically registered and phase-gated.

---

## PART 5: CAD-AGENT GAP MAP

| CadMind Capability | Current `cad-agent` Owner | Missing Behavior in `cad-agent` | Benchmark Impact (Issue #491) |
| :--- | :--- | :--- | :--- |
| **In-Place Arc/Circle/Polyline Mutation** | `autocad_plugin` (`CommandContext.cs`) | `CommandContext.cs` only implements `ApplyBoundedNativeLineEdit`. Any edit to an Arc, Circle, or Polyline requires full entity recreation, risking handle churn. | **High** (Axis 1: Source Geometry Preservation) |
| **Dimension Override & Truth Audit** | `autocad_plugin` / `semantic_ir_lib` | No mechanism checks whether stated dimensions have forced `DimensionText` overrides or whether text matches measured geometry. | **Critical** (Axis 2: Dimension Engineering Truth) |
| **Hierarchical Snap Point Extraction** | `autocad_plugin` (`IAutoCADDriver`) | Agent cannot inspect snap points (centers, tangents, quadrants) inside nested block references or xrefs without exploding them. | **High** (Axis 1: Precision Drafting Geometry) |
| **Metric Hatch Scaling Correction** | `dxf_builder_lib` / `autocad_plugin` | Patterns like `AR-CONC` use imperial base units and render as solid black or invisible if not scaled by $25.4$ in metric drawings. | **High** (Axis 4: Graphic Presentation & Hatching) |
| **ISO Text Height & Role Hierarchy** | `semantic_ir_lib` / `dxf_builder_lib` | Text heights are arbitrarily assigned rather than adhering to the ISO 3098 series (`1.8, 2.5, 3.5, 5.0, 7.0`). | **High** (Axis 3: Drafting Presentation Hierarchy) |

---

## PART 6: TOP 5 ADAPTATIONS FOR CAD-AGENT

### 1. Bounded Native Arc / Circle / Polyline Mutation (`ApplyBoundedNativeEntityEdit`)
- **Target Owner:** `autocad_plugin` (`CadAgent.AutoCAD2027/Commands/CommandContext.cs`).
- **Scope:** Extend existing `ApplyBoundedNativeLineEdit` pattern to `Arc`, `Circle`, and `LWPolyline`.
- **Contract:** Accept handle, assert entity type, verify pre-edit hash, modify native properties in-place, execute 4-stage readback verification.

### 2. Dimension Truth & Override Audit Gate (`AuditDimensionTruth`)
- **Target Owner:** `autocad_plugin` and `semantic_ir_lib`.
- **Scope:** Add an automated verification step before committing edits or benchmark exports.
- **Contract:** Verify `dim.Measurement > 0` and ensure `dim.DimensionText` is either empty or contains `<>`. Fail benchmark if fraudulent override is detected.

### 3. Hierarchical Snap Point Extraction (`ReadSnapPoints`)
- **Target Owner:** `autocad_plugin` (`CadAgent.AutoCAD2027`).
- **Scope:** Implement read-only snap point harvester with matrix transformation across nested blocks and xrefs.
- **Contract:** Return nearest canonical WCS points with `stacked` counts for agent precision snapping.

### 4. Metric Hatch Auto-scaling Calculator (`HatchScaleCalculator`)
- **Target Owner:** `dxf_builder_lib` and `autocad_plugin`.
- **Scope:** Reimplement CadMind's `HatchUnitScale` calculation.
- **Contract:** When `MEASUREMENT == 1` and pattern has imperial base definition, automatically multiply scale by `25.4` to guarantee visual fidelity.

### 5. Engineering Standards & Text Hierarchy Catalogs
- **Target Owner:** `semantic_ir_lib/standards/`.
- **Scope:** Incorporate ISO 3098 text height rules, ISO 128 linetype standards, and mechanical fit tables (DIN 6885 keyways).
- **Contract:** Provide static typed lookups for text height snapping and engineering dimensions.

---

## PART 7: DO NOT ADOPT (DELIBERATE REJECTIONS)

1. **BM25 Dynamic Tool Discovery (`ToolSearchIndex.cs`):**  
   *Reason:* Adds retrieval non-determinism and latency; contradicts `cad-agent`'s staged execution architecture.
2. **Encrypted Assembly Loading (`CadMindTools.enc` / `O.A`):**  
   *Reason:* Proprietary licensing barrier; completely unneeded for `cad-agent` open architecture.
3. **90 Monolithic LISP Packages (`.fas`):**  
   *Reason:* Opaque legacy binaries that execute via unmanaged `acedEvaluateLisp`, bypassing structured object validation and error recovery.
4. **Untargeted Batch Erase / Modification:**  
   *Reason:* Highly risky for native CAD persistence; `cad-agent` must maintain strict single-entity bounded edits.

---

## PART 8: SINGLE BEST NEXT EXPERIMENT

### Proposal: "Dimension Truth & Override Audit Gate for Issue #491 Benchmark"

#### 1. Hypothesis
Integrating an automated `DimensionTruthAudit` gate into `cad-agent`'s benchmark runner will automatically expose and eliminate fraudulent dimension overrides, raising Axis 2 ("Dimension Engineering Truth") score on the Issue #491 benchmark to 100% without altering the CAD transport.

#### 2. Target Owner & Boundaries
- **Owner:** `autocad_plugin` (`CadAgent.AutoCAD2027/Commands/AuditCommands.cs`) and `semantic_ir_lib`.
- **Boundaries:** Read-only database scan; zero geometry mutation; preserves existing FileIPC protocol.

#### 3. Test Vectors
1. Native dimension with default text (`DimensionText == ""`) $\rightarrow$ **PASS**.
2. Dimension with tolerance decoration (`DimensionText == "<> ±0.05"`) $\rightarrow$ **PASS**.
3. Dimension with reference prefix (`DimensionText == "2x <>"`) $\rightarrow$ **PASS**.
4. Fraudulent override (measured 100.0 mm, text forced to `"95.0"`) $\rightarrow$ **FAIL (Flagged with handle, measured, and override text)**.
5. Zero or negative measurement dimension $\rightarrow$ **FAIL**.

#### 4. Measurable Acceptance Criteria
- 100% detection rate on synthetic test drawing containing 5 valid dimensions, 3 decorated dimensions, and 2 fraudulent overrides.
- Zero false positives on valid prefixed/suffixed dimensions.
- Benchmark runner halts and reports actionable error when an override is present.

---
*Report compiled from static decompilation and architectural analysis of CadMind v1.0.1 and cad-agent.*
