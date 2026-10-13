# CAD_AGENT_OWNER_MAP: Bulge and Polyline Integration

## Existing Production Owners Mapping
- **Primary Generation Owner:** `dxf_builder_lib/builder.py`
  - Current Capability: Constructs DXF documents using `ezdxf`. Currently emits polylines primarily as 2D point arrays with default bulge 0.0.
  - Required Enhancement: Support tuple points `(x, y, [bulge])` or dedicated `add_lwpolyline(points, bulges=...)` method.
- **Primary Extraction Owner:** `primitive_ir_lib/geometry_extraction.py`
  - Current Capability: Extracts straight lines and discrete circles/arcs from raster or vector primitives.
  - Required Enhancement: When sequential points are co-circular, group them into a single arc segment and calculate bulge instead of separate straight chord segments.
- **Plugin Database Owner:** `autocad_plugin/CadAgent.AutoCAD2027`
  - Current Capability: Inspects native `Polyline` entities.
  - Native AutoCAD SDK Method: `Polyline.GetBulgeAt(int index)` and `Polyline.SetBulgeAt(int index, double bulge)`. Fully supported by official managed assembly `acdbmgd.dll` without any native C++ P/Invoke!

## What NOT to Build:
- Do NOT build an external C++ curve fitting DLL or native P/Invoke bridge.
- Do NOT replace `ezdxf` with an external DXF parser.
- Do NOT create a custom polyline serialization subsystem.
- Reusing existing owners preserves 100% architectural cohesion.
