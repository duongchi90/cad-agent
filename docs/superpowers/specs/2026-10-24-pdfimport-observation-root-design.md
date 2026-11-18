# Initial PDFIMPORT Observation Root

## Approval and scope

- Approval: PO_SOL bounded implementation admission, 2026-10-24.
- Supported scope: derive a stable identity digest for one closed initial
  PDFIMPORT observation packet in the existing `cad_agent.visual_evidence`
  owner.
- This is a typed observation/currentness identity only. It does not authorize
  mutation, promotion, source-fidelity claims, or product acceptance.

## Design

The packet is closed and versioned. It binds the exact source PDF, import
script, completed receipt, candidate DWG path, and candidate DWG SHA-256. The
existing Primitive-IR `external_geometry` provenance validator remains
unchanged. The new digest uses the existing canonical JSON hash helper and a
separate provenance mode so the observation cannot be confused with external
geometry provenance.

The helper validates packet shape and hash/path syntax only. Its caller must
independently verify the actual artifact bytes, receipt authenticity and
completion, path aliases, native document custody, and current on-disk DWG
identity before using the digest. The helper is not evidence that those checks
occurred. No manifest schema, IPC transport, dispatcher, runtime, or drawing is
changed by this design.

## Alternatives considered

- Reuse `external_geometry` provenance: rejected because PDFIMPORT has no
  Primitive IR or the required projection/verification packet and fabricating
  those fields would misstate evidence.
- Change the manifest or IPC schema: rejected because this bounded owner-local
  identity function is sufficient for the next observation step.
- Treat the DWG or log hash as mutation authority: rejected; neither establishes
  a mutation event or native custody.

## Acceptance

- Reject unknown/missing fields, wrong schema/mode, malformed SHA-256 values,
  and noncanonical/nonabsolute Windows candidate paths.
- Produce a deterministic canonical digest bound to every accepted field.
- Keep the external geometry validator and all native/runtime owners unchanged.
- Focused tests pass; canonical verification and exact-head review remain
  separate gates before adoption.
