# File IPC Live MCP Client Design

## Goal

Allow Phase 4 review and repair code to communicate directly with a running
AutoCAD MCP File IPC dispatcher, without requiring a Codex chat callback.

## Scope

Add a production `FileIPCLiveMCPClient` that implements the existing
`MCPClient` protocol for primitive operations: opening a drawing, listing and
querying entities, erasing an entity, creating lines/circles/arcs, and creating
text. Keep `LiveMCPClient` unchanged for callback-based runtimes and keep
`FakeMCPClient` for deterministic unit tests.

## Architecture

The new client writes command JSON files to a configurable IPC directory
(default `C:/temp`), triggers the AutoLISP dispatcher through a supplied
trigger function, and polls for the matching result JSON. A small transport
object owns file naming, timeout, cleanup, and response normalization; the
client maps its typed methods to the existing AutoCAD MCP operation names.

The dispatcher trigger is injectable. Production supplies a Windows trigger
that posts `(c:mcp-dispatch)` to the AutoCAD window; tests supply a fake
trigger that creates deterministic result files without AutoCAD.

## Errors and safety

- Missing or timed-out result raises `MCPTimeoutError`.
- A dispatcher response with `ok: false` raises `MCPToolError`.
- Each request uses a unique ID and deletes its own command/result files.
- The adapter never creates, saves, or closes a drawing unless called through
  the existing review/repair APIs.

## Validation

1. Unit tests cover success, timeout, tool error, and request/response mapping
   with a fake trigger.
2. Existing Phase 4 fake-client tests remain green.
3. An opt-in live smoke test, guarded by `CAD_AGENT_FILE_IPC=1`, calls only
   `drawing.info` and `entity.list` against the active AutoCAD drawing.

## Deferred work

BLOCK/ATTRIB component creation is not included. The File IPC wrapper's block
support is not sufficient for the project's component API; that work needs a
separate AutoLISP or COM design.
