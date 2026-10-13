# TARGETS: Maximum REA + Ghidra Capability Evaluation Targets

## Target Summary Across All 4 Tiers

| Tier | Target Name | Primary Role & Capabilities | Language / Compiler | Binary Details | PDB / Symbols | Ground Truth Source |
| :---: | :--- | :--- | :--- | :--- | :---: | :--- |
| **Tier 1** | `libcadgeom_core` | 2D CAD Computational Geometry Kernel (Orientation, Area, PIP, RDP Decimation, Convex Hull) | C99 / MSVC 19.51 (x64) `/O2 /GS-` | `cadgeom_core.exe`<br>6,656 bytes<br>`2f4d499d3dfd...` | Completely Stripped | Pre-frozen expectation model (`SOURCE_EXPECTATION_HASH.txt`) |
| **Tier 2** | `libcadstream_format` | Binary CAD Stream Parser, Opcode Dispatcher, Extent Accumulator & State Machine | C99 / MSVC 19.51 (x64) `/O2 /GS-` | `cadstream_format.exe`<br>4,608 bytes | Completely Stripped | Delayed source reveal (`cadstream_format.c`) |
| **Tier 3 (A)** | `tolerance_guard_v1` | Baseline Geometric Tolerance & Vector Normalization Engine | C99 / MSVC 19.51 (x64) `/O2 /GS-` | `tolerance_guard_v1.exe`<br>3,072 bytes<br>`773616ee44eb...` | Completely Stripped | Baseline source (`tolerance_guard_v1.c`) |
| **Tier 3 (B)** | `tolerance_guard_v2` | Modified Engine with Degenerate Vector Guard ($10^{-12}$) & Error Propagation | C99 / MSVC 19.51 (x64) `/O2 /GS-` | `tolerance_guard_v2.exe`<br>3,072 bytes<br>`6cc4a7304410...` | Completely Stripped | Modified source (`tolerance_guard_v2.c`) |
| **Tier 4** | `dxf_lwpolyline_bulge` | DXF Group 42 LWPOLYLINE Bulge ($b = \tan(\theta/4)$) and 3-Point Circular Arc Fitting | C99 / Python Mathematical Oracle | Specification & Python Oracle | N/A (Source-First) | Autodesk DXF Spec & `ezdxf.math.bulge` |
