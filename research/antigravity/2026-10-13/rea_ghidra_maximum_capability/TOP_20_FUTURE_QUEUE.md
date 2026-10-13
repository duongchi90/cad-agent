# TOP_20_FUTURE_QUEUE: High-ROI Proactive REA Precompute Targets

| # | Capability | Why Product Relevant | Current Catalog Status | Best External Prior | Source / Binary | Ghidra Needed? | Expected Luna Discovery Saved | Risk | Priority |
| :---: | :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **1** | `POLYLINE_BULGE_AND_ARC_RECONSTRUCTION` | Native DXF LWPOLYLINE arc/fillet representation | Proposal (`REA-020`) | `ezdxf.math.bulge` / DXF Group 42 | Source-First | No | 12h | Low | **P0** |
| **2** | `DIMENSION_ARROWHEAD_WITNESS_ASSOCIATION` | Associates recognized dimension text with arrowheads | Unmapped | LibreCAD dimension engine / QCAD | Source-First | No | 16h | Low | **P0** |
| **3** | `IMAGE_TO_CAD_CONTOUR_SIMPLIFICATION` | Simplifies noisy raster vectorized contours | Unmapped | Visvalingam-Whyatt / RDP line simplification | Source-First | No | 10h | Low | **P1** |
| **4** | `LEADER_MLEADER_RECONSTRUCTION` | Reconstructs multi-segment leaders and annotations | Unmapped | OpenDWG / ezdxf leader structures | Source-First | No | 14h | Med | **P1** |
| **5** | `HATCH_REGION_BOUNDARY_RECOGNITION` | Identifies hatch boundaries while filtering hatch lines | Unmapped | OpenCV connected components / BricsCAD hatch | Binary / Prior | Yes | 20h | Med | **P1** |
| **6** | `REPEATED_COMPONENT_GRAPH_MATCHING` | Identifies repeated symbols/blocks across drawings | Prior (`REA-007`) | NetworkX VF2 / Geometric Invariant Hashing | Source-First | No | 24h | Med | **P1** |
| **7** | `CAD_TOPOLOGY_WATERTIGHT_REPAIR` | Closes micro-gaps and resolves near-intersections | Unmapped | CGAL 2D Polygon Repair / Clipper2 | Source-First | No | 16h | Low | **P1** |
| **8** | `TABLE_GRID_CELL_STRUCTURE_EXTRACTION` | Parses drawing title blocks and revision tables | Unmapped | OpenCV table morphology / PaddleOCR tables | Source-First | No | 12h | Low | **P2** |
| **9** | `LAYER_STYLE_METADATA_RECONSTRUCTION` | Maps geometry to standard CAD layers (Outline, Center) | Unmapped | ISO 128 / ASME Y14 CAD standards | Spec-First | No | 8h | Low | **P2** |
| **10**| `NATIVE_DIMENSION_PERSISTENCE_SEMANTICS` | AutoCAD 2027 DimAssoc persistence edge cases | Prior (`REA-010`) | AutoCAD 2027 Database Engine | Binary-Only | Yes | 16h | High | **P2** |
| **11**| `GEOMETRIC_HASHING_2D_SYMBOLS` | Fast O(1) candidate lookup for standard symbols | Unmapped | Wolfson Geometric Hashing (1997) | Source-First | No | 18h | Med | **P2** |
| **12**| `TEXT_ROTATION_ESTIMATION_MOMENTS` | Sub-degree text orientation prior to Tesseract | Prior (`REA-003`) | OpenCV minAreaRect / PCA image moments | Source-First | No | 8h | Low | **P2** |
| **13**| `ELLIPSE_AND_SPLINE_DECOMPOSITION` | Converts cubic splines to biarc approximations | Unmapped | ezdxf `fit_spline_to_biarc` | Source-First | No | 14h | Med | **P2** |
| **14**| `DWG_R2018_SPEC_ENCODING_RULES` | Reverse engineers packed bitstreams in native DWG | Unmapped | LibreDWG spec / OpenDesign Specification | Spec-First | No | 30h | High | **P3** |
| **15**| `AUTOCAD_EXTDICT_PERSISTENCE_LIFECYCLE`| Verifies ExtensionDictionary reactor survival | Prior (`REA-009`) | `acdbmgd.dll` object graph | Binary-Only | Yes | 10h | Med | **P3** |
| **16**| `LINE_WEIGHT_ISO_NORMALIZATION` | Calibrates physical line weight from pixel stroke | Unmapped | ISO 128-20 line widths standard | Spec-First | No | 6h | Low | **P3** |
| **17**| `BLOCK_TRANSFORM_NESTED_COMPOUNDING` | Flattens multi-level nested BLOCK insertions | Unmapped | Affine matrix stack / SVG transform tree | Source-First | No | 10h | Low | **P3** |
| **18**| `RADIAL_DIMENSION_CENTER_SOLVER` | Finds center mark coordinates from radius text | Unmapped | Taubin fit center + radial ray intersection | Source-First | No | 8h | Low | **P3** |
| **19**| `CHAMFER_AND_FILLET_DETECTOR` | Recognizes corner modifications automatically | Unmapped | 2D Medial Axis Transform / Voronoi graph | Source-First | No | 16h | Med | **P3** |
| **20**| `ACAD_PROXY_ENTITY_FALLBACK` | Safe handling of unread ObjectARX custom entities | Unmapped | AutoCAD `ProxyEntity.Erase()` contract | Binary-Only | Yes | 12h | Med | **P3** |
