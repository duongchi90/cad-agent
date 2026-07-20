# File IPC Phase 4 End-to-End Smoke Test

## Goal

Verify that a DXF built by the project can be opened, reviewed, damaged, and
repaired through a real AutoCAD File IPC session.

## Flow

The opt-in test creates a temporary DXF containing one line through
`dxf_builder_lib`, opens it through `FileIPCLiveMCPClient`, and runs
`review_dxf_live`. It then moves the line to a wrong layer using the IPC
client, runs `repair_dxf_live`, and asserts a final live review passes.

## Safety

The test runs only with `CAD_AGENT_FILE_IPC=1`, writes to a temporary DXF, and
does not save or close the user's active drawing. It requires an AutoCAD frame
handle through `CAD_AGENT_AUTOCAD_HWND` and a loaded `mcp_dispatch.lsp`.

## Scope

Primitive LINE review/repair only. BLOCK/ATTRIB components remain deferred.
