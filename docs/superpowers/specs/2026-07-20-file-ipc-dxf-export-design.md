# File IPC DXF Export Design

## Problem

`QSAVE` reports success while an attribute change remains only in AutoCAD
memory, and `SAVEAS "DXF"` returns an empty File IPC error on AutoCAD LT.
Neither operation is a reliable export contract for the real component smoke.

## Decision

Replace the File IPC `drawing-save-as-dxf` implementation in
`mcp_dispatch.lsp` with AutoCAD's dedicated `DXFOUT` command. The command
receives a distinct destination file and runs with dialogs disabled. The
dispatcher verifies `(findfile path)` before returning success; otherwise it
returns a meaningful error containing the destination path.

The Python client retains `drawing_save_as_dxf(path)`. The smoke exports to a
separate DXF, reassigns `BuildResult.output_path`, and verifies the serialized
attribute through `ezdxf.readfile` before calling Reviewer/Repair #1.

## Verification

1. An opt-in smoke changes beam `PART_ID` to `wrong` through File IPC.
2. `drawing_save_as_dxf` returns only after the new destination exists.
3. ezdxf reads `wrong` from that file.
4. Reviewer #1 detects the mismatch; Repair #1 restores the expected value;
   final review passes after reopening the repaired DXF in AutoCAD.
