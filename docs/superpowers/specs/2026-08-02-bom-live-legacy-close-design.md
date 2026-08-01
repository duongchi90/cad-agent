# Mechanical BOM Live Gate and Legacy Close Design

**Date:** 2026-08-02  
**Scope:** Windows, AutoCAD Mechanical 2027, disposable DXF only

## Goal

Promote the `mechanical_bom` live gate when its prerequisites are available,
then remove the legacy File IPC close race that reports `Drawing is busy`.

## Approved behavior

1. The Mechanical BOM live test creates and hashes a disposable DXF below
   `C:\temp`, uses the managed .NET IPC client for health, review,
   `mechanical_bom`, and close-without-save, and verifies the drawing hash and
   `DBMOD` remain unchanged. It must never operate on `Drawing1.dwg`.
2. The legacy Python client must not call COM `vla-close` for the no-save raw
   LISP close path. It queues `(command-s "_.CLOSE" "_N")` through the
   existing AutoCAD command-line trigger so the close runs after the active
   dispatcher command releases its document context.
3. `drawing_close(save_changes=True)` remains outside this fix and continues to
   use the existing save-enabled behavior; no production repair or save path is
   changed.

## Evidence states

- Live prerequisites absent: record `NOT RUN`; never infer live PASS from
  offline tests.
- Disposable managed BOM succeeds and closes without save: record `PASS`.
- Legacy close regression is proven by an offline test that asserts the exact
  queued expression and by a focused live disposable test when prerequisites
  are available.

## Safety boundary

No `Drawing1.dwg`, customer drawing, private artifact, COM reference in the
plugin, or production save/repair operation is permitted.
