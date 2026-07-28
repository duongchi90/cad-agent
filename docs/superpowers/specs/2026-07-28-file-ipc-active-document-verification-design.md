# File IPC Active-Document Verification Design

**Status:** Approved under the user's delegated completion authority on
2026-07-28

## Problem

During the release live gate, a component round-trip timed out and the next
subcase reported `Entity not found`. Later subcases passed, and an isolated
rerun passed. Investigation showed that the raw-LISP `drawing_open()` path
waited only for a dispatcher ping. Because AutoLISP is document-scoped, the
previous document can answer that ping before AutoCAD activates the requested
DXF, causing a false successful open and handle lookup in the wrong drawing.

The same run also showed a single transient timeout on the read-only
`block-get-attributes` operation.

## Design

- After raw-LISP open, dispatcher load, and ping, query `DWGNAME` and require it
  to match the requested path's basename case-insensitively.
- If the wrong document is active, repeat the open/bootstrap sequence once.
- If the second verification still mismatches, raise `MCPToolError` naming the
  requested and active documents.
- Retry `block-get-attributes` once only when it times out. The command is
  read-only, so retry cannot duplicate a mutation.
- Do not automatically retry any write, save, repair, erase, or create command.

## Acceptance criteria

1. Offline tests prove an active-document mismatch causes one retry.
2. Offline tests prove a transient attribute-read timeout is retried once.
3. Existing File IPC mapping tests pass.
4. The previously intermittent live component round-trip passes.
5. The complete AutoCAD Mechanical live gate passes on the final candidate.
