# TARGET_IDENTITY: Tier 1 Calibration Benchmark

- **TARGET_NAME:** `libcadgeom_core` (2D CAD Computational Geometry Kernel)
- **ROLE:** Standard 2D CAD algorithmic subsystem (Orientation, Bounding Box, Shoelace Area, Ray-Casting Point-in-Polygon, Douglas-Peucker Polyline Decimation, Monotone Chain Convex Hull)
- **SOURCE_LANGUAGE:** C99
- **LICENSE:** MIT (Permissive Open Source)
- **EXACT_SOURCE_COMMIT:** `fixture-20261013-msvc-x64-v1`
- **BUILD_TOOLCHAIN:** Microsoft Visual Studio 2026 Build Tools v18.7.3
- **COMPILER:** `cl.exe` v19.51.36248 for x64
- **COMPILER_FLAGS:** `/c /O2 /GS- cadgeom_core.c`
- **LINKER_FLAGS:** `/subsystem:console /entry:main /nodefaultlib /OPT:REF /OPT:ICF`
- **BINARY_LOCAL_PATH:** `C:\Tools\benchmarks\tier1\cadgeom_core.exe`
- **BINARY_FORMAT:** PE32+ (x86_64 native executable)
- **BINARY_SIZE:** 6,656 bytes
- **BINARY_SHA256:** `2f4d499d3dfd40afea16f0bc49169dcf0dbb4f9ee898bb4e2e60760c20b8ba8a`
- **PDB_PRESENT:** `NO`
- **SYMBOL_STRIPPING:** `YES` (All user symbols, function names, and variable names stripped; entry point linked directly to `main`)
- **OPTIMIZATION_LEVEL:** `RELEASE_O2` (Global optimization, vectorization, register variable allocation, inlining, frame pointer omission)
