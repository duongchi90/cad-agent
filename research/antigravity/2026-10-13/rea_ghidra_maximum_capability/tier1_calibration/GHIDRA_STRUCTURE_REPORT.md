# GHIDRA_STRUCTURE_REPORT: Tier 1 Native Structural Recovery

## 1. Binary Identification & Section Map
- **Target Binary:** `C:\Tools\benchmarks\tier1\cadgeom_core.exe`
- **Format:** PE32+ (x86_64) Native Executable
- **Architecture:** `x86_64`
- **SHA256:** `2f4d499d3dfd40afea16f0bc49169dcf0dbb4f9ee898bb4e2e60760c20b8ba8a`
- **Total Mapped Segments:** 6

| Segment Name | Start Virtual Address | End Virtual Address | Length (Bytes) | Role & Permissions |
| :--- | :--- | :--- | :---: | :--- |
| `Headers` | `0x140000000` | `0x140000400` | 1,024 | PE DOS & NT Headers |
| `.text` | `0x140001000` | `0x140001e00` | 3,584 | Executable Machine Code (R-X) |
| `.rdata` | `0x140002000` | `0x140002400` | 1,024 | Read-Only Constants & Floating Point Literals (R--) |
| `.data` | `0x140003000` | `0x140003200` | 512 | Global Variables & CRT Thunks (RW-) |
| `.pdata` | `0x140004000` | `0x140004200` | 512 | Exception Handling Tables (R--) |
| `tdb` | `0xff00000000` | `0xff00001850` | 6,224 | Ephemeral Ghidra Session DB Segment |

---

## 2. Procedure Inventory & Virtual Address Layout
Ghidra recovered exactly 12 procedures within `.text`:

| Virtual Address | Ghidra Symbol | Role / Function Identification | Inferred Size | Fan-In | Fan-Out |
| :--- | :--- | :--- | :---: | :---: | :---: |
| `0x140001000` | `FUN_140001000` | `cadgeom_dist_sq` | 0x48 | 2 | 0 |
| `0x140001050` | `FUN_140001050` | `cadgeom_convex_hull` (Monotone chain sort & stack) | 0x340 | 1 | 1 |
| `0x140001390` | `FUN_140001390` | `cadgeom_transform_point` (2x3 affine matrix) | 0x40 | 0 | 0 |
| `0x1400013d0` | `FUN_1400013d0` | `cadgeom_bbox_expand` (Min/Max interval enclosure) | 0x20 | 1 | 0 |
| `0x1400013f0` | `FUN_1400013f0` | `cadgeom_bbox_intersects` (AABB separating axis) | 0x30 | 0 | 0 |
| `0x140001520` | `FUN_140001520` | `cadgeom_cross_product` (2D Orientation test) | 0x40 | 2 | 0 |
| `0x140001710` | `FUN_140001710` | `cadgeom_perp_distance` (Point-line normal distance) | 0x80 | 1 | 2 |
| `0x140001790` | `FUN_140001790` | `cadgeom_polygon_signed_area` (Shoelace formula) | 0x80 | 1 | 0 |
| `0x140001a40` | `FUN_140001a40` | `cadgeom_point_in_polygon` (Jordan curve ray-cast) | 0xb0 | 1 | 0 |
| `0x140001bc0` | `entry` / `main` | Test Harness / PE Entry Point | 0x90 | 0 | 1 |
| `0x140001c50` | `FUN_140001c50` | `cadgeom_douglas_peucker_recurse` (RDP recursive decimation) | 0x30 | 2 | 2 |
| `0x140001c80` | `FUN_140001c80` | `cadgeom_evaluate_contour` (Master pipeline) | 0x140 | 1 | 5 |

---

## 3. Constant and Data Reference Discovery
- **Floating-point literals in `.rdata`:**
  - `1e-9` (`0x3e112e0be826d695`) at `.rdata`: Epsilon threshold for collinearity / degenerate segment guard.
  - `0.5` (`0x3fe0000000000000`) at `.rdata`: Multiplier for polygon signed area (Shoelace formula).
  - `0.0` (`0x0000000000000000`): Baseline orientation comparison.
- **Integer constants:**
  - Threshold `3`: Minimum point count for valid polygon / convex hull.
  - Buffer limit `32`: Maximum stack buffer allocation cap.
  - `_fltused` at `0x140003000`: Microsoft CRT floating-point indicator.
