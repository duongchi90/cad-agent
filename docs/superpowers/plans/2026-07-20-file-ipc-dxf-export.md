# File IPC DXF Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make File IPC export a verifiable DXF for real AutoCAD component repair smoke tests.

**Architecture:** AutoLISP uses `DXFOUT` rather than `SAVEAS`, validates the target with `findfile`, and returns a specific error if no file exists. The existing Python API continues dispatching `drawing-save-as-dxf`; the real smoke proves the serialized attribute changed.

**Tech Stack:** AutoLISP, AutoCAD LT File IPC, Python unittest, ezdxf.

## Global Constraints

- Export must use a destination path different from the active DXF.
- No success response without `(findfile path)`.

---

### Task 1: Implement verified DXFOUT bridge export

**Files:** Modify `C:/Users/duong/Desktop/autocad/autocad-mcp/lisp-code/mcp_dispatch.lsp`.

- [ ] Replace the `drawing-save-as-dxf` `SAVEAS` branch with `DXFOUT`, setting `FILEDIA` to 0 before the command and restoring it afterwards.
- [ ] Return success only when `(findfile path)` is truthy; otherwise return `DXF export not created: <path>`.
- [ ] Reload `mcp_dispatch.lsp` into the currently active AutoCAD document.

### Task 2: Verify serialized component repair

**Files:** Modify `mcp_integration_lib/tests/test_file_ipc_e2e.py` only if the assertion needs an actionable bridge error.

- [ ] Run `test_beam_insert_attribute_round_trip_real_autocad` with the three File IPC environment variables.
- [ ] Verify ezdxf reads the intentionally changed `PART_ID`, Reviewer #1 reports a component mismatch, Repair #1 writes a corrected INSERT, and final review passes.
- [ ] Run the full offline pytest suite and commit the bridge-facing client/test changes separately from external AutoLISP source changes.
