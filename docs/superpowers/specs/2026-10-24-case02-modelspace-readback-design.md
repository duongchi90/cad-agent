# CASE02 ModelSpace Readback Design

**Date:** 2026-10-24
**Status:** Approved for bounded implementation by PO_SOL; Luna owns implementation
**Base SHA:** `abfb60ea7d9cf2012e0ea30b68b9fef8b5fb0512`
**Supported scope:** Extend the existing read-only `drawing_setup_audit` owner to optionally enumerate the active drawing's complete ModelSpace inventory and bind it to the exact on-disk DWG and current AutoCAD receiver.

## Decision

Add an explicit opt-in to the existing `drawing_setup_audit` request. The default request and result remain unchanged. When opted in, the same dispatcher operation returns the existing setup snapshot plus a complete ModelSpace entity inventory containing each entity's handle, DXF type, and finite geometric bounds or an explicit unsupported/unreadable disposition.

The existing Python CLI/client remains the caller and writes the returned inventory inside the existing hash-bound drawing setup audit artifact. No new operation, dispatcher, transport, authority store, or native subsystem is introduced.

## Read-only custody boundary

The opted-in path must fail closed unless all of the following hold across one AutoCAD command/read transaction:

- The request's normalized drawing path matches the active document and database filename.
- The exact request SHA-256 matches the DWG bytes immediately before and after the read.
- `DBMOD` is zero before and after the read. Equality alone is insufficient because a dirty in-memory drawing can differ from disk.
- The same active `Document` and `Database` instances remain current through the read.
- The receipt identifies the current AutoCAD process ID and the loaded plugin binary path/SHA-256/version.
- Every ModelSpace object is enumerated. Each object has a handle/type and either finite bounds or an explicit unsupported/unreadable/nonfinite disposition. Incomplete enumeration fails; incomplete geometry is represented explicitly and cannot be reported as complete bounds coverage.
- The operation does not save, mutate, create, erase, close, or change drawing state.

`drawing_setup_audit`'s legacy empty-parameter request retains its existing behavior. The new opt-in is a single boolean; callers cannot choose a response size limit.

## Bounded response

Request writes and every other operation retain the existing 1 MiB default limit. Only an explicitly opted-in `drawing_setup_audit` response may use the fixed 16 MiB envelope limit, enforced by both the AutoCAD writer and Python reader. The limit is policy-owned, not caller-controlled. Serialization must stop at the bound; overflow writes a small structured `INVENTORY_RESPONSE_LIMIT_EXCEEDED` failure with no partial inventory or completeness claim.

## Claims and non-goals

The result proves a read-only inventory observation for the bound path/hash, process, plugin build, document/database session, and DBMOD state. It does not establish source-to-entity correspondence, page assignment, semantic correctness, visual/dimension acceptance, editing quality, save/reopen acceptance, or product/native PASS. Unsupported or unreadable extents prevent a complete-bounds claim.

No CASE02 drawing is opened or changed as part of implementation tests. A later live readback must use the frozen candidate hash and the verified current receiver/document, and must stop if custody or complete enumeration cannot be established.

## Approval boundary

PO_SOL decision: refine/approve this existing-owner approach with the custody and fail-closed conditions above, including the operation-scoped fixed response limit. PO remains advisory and has no repository or native mutation authority. This design does not authorize unrelated production behavior or a new transport.
