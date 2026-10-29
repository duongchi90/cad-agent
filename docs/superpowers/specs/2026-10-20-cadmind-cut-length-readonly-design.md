# CadMind Cut Length Read-Only Design

**Approval date:** 2026-10-20
**Approval:** Local PO admitted bounded design and implementation.
**Base:** `5979b1813a27dbc7435c64c6cf3c220f5f8e09ad`

## Supported scope

Add an identity-bound, read-only `measure_entity_lengths` operation to the
existing `cad_agent.cad_read_facade` owner. The caller supplies a nonempty,
bounded, explicit selection of entity handles and the existing candidate
identity inputs. Initial supported entity types are LINE and CIRCLE.

LINE length is the Euclidean distance between its 3D endpoints. CIRCLE length is
its circumference, `2 * pi * radius`. All inputs, per-entity values and the
aggregate must be finite and nonnegative; invalid geometry, missing/unsupported
entities, duplicate handles, identity drift, incomplete reads and overflow must
fail closed without a clean aggregate.

Report lengths in raw drawing units and include the drawing's `INSUNITS` value
when available. An optional caller unit label is explicitly declarative
metadata; it never changes a numeric result or asserts physical scale. No unit
conversion, AutoCAD mutation, new transport, or CadMind DTO/binary reuse is in
scope. The observation remains non-atomic under the existing read contract.

## Independent oracle

- A 3-4-5 LINE measures 5 drawing units.
- A radius-2 CIRCLE measures `4 * pi` drawing units.
- Mixed selection totals the two values without conversion.
- Duplicate, missing, unsupported, malformed, nonfinite, stale-identity and
  overflow cases do not return a successful aggregate.
- An empty selection is rejected explicitly.
