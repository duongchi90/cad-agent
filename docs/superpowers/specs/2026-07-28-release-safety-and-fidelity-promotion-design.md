# Release Safety and Fidelity Promotion Design

**Status:** Approved by the user's delegated review authority on 2026-07-28

## Problem

The release candidate had four traceability and safety gaps:

1. File IPC identified an active drawing by `DWGNAME` only.
2. Production backups were copied but not hash-verified before mutation.
3. Agent application approval was not bound to a saved report and exact inputs,
   and constraint drops did not trigger a new solve before DXF generation.
4. Visually accepted fidelity reconstructions remained outside the canonical
   manifest and were prohibited from any supported Mechanical review flow.

## Design

### AutoCAD document identity and rollback

Raw-LISP document bootstrap queries `DWGPREFIX` and `DWGNAME`, normalizes the
combined Windows path, and compares it with the complete requested path. A
same-named drawing in another directory is a mismatch.

Before production repair, source and copied DXF/evidence hashes must all match.
A failed second review closes the modified active drawing without saving, then
opens the verified backup. Repair remains separately approved and is not part
of the fidelity workflow.

### Agent application

The ordinary Agent run stays advisory. Application is a separate invocation
against a saved report. It requires the report SHA-256 and the approved source,
Primitive IR, and Semantic IR SHA-256 values. The runner rejects any mismatch
before application and records report, action-set, input, and applied-report
hashes. If approved actions drop constraints, pruning and solving run again and
the DXF builder receives only the post-application solve result.

### Fidelity promotion and Mechanical review

`fidelity-promote` consumes a composed page that is already bound to a region
approval. A delegated visual approval creates a SHA-bound promotion record and
updates the page checkpoint to `approved_for_mechanical_review`.

`fidelity-mechanical-review` is the only Mechanical path for promoted fidelity
DXFs. It opens the exact full path, compares AutoCAD's top-level type/layer
signature with the promoted DXF signature, writes a report, and advances the
manifest checkpoint. It performs no save, repair, or model export. Ordinary
`mechanical-review` and all repair paths continue to reject fidelity artifacts.

## Acceptance

- Offline tests reject same-basename/different-directory activation.
- A disposable live test proves the same identity rule in AutoCAD Mechanical.
- Corrupted backup copies stop repair before mutation; failed repair closes
  without save before the backup is reopened.
- Agent application is report/input-hash-bound and uses a post-drop solve.
- All approved private pages can be promoted and pass the dedicated read-only
  Mechanical review with manifest checkpoints and no save/repair.
