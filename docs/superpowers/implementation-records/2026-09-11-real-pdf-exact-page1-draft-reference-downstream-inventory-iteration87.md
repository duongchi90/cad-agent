# Real-PDF exact page-1 DRAFT_REFERENCE downstream inventory — iteration 87

Date: 2026-09-11  
Issue: #409 real-PDF exact-identity acceptance  
Canonical main context: `e8fc0092ee46750e50de0ea408fd91811cae10c2`  
Executor branch: `codex/audit-text-style-compat-20260910`  
Prior evidence head: `894fa405575104ff83c4de81fed98a6a3d4541a1`

## Authorization and scope

SOL authorized one read-only downstream draft-path inventory from the fresh
iteration-80/81 page-1 DXF/build-evidence identity. DARA, R3, R4, and
source-fusion were explicitly skipped as non-applicable to the Owner's
non-authoritative PDF `DRAFT_REFERENCE` lane. AutoCAD/FileIPC was not launched.

## Exact identity recheck

The staged manifest and page-1 artifacts were read without editing:

```text
manifest_sha256=f7c7b1afbd52f8f504dafbcb9b6efb416ee332b88260a01aea2414ab9d650eaf
source_sha256=e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75
page=1
dxf_sha256=167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714
build_evidence_sha256=16053d029396a8efc029001991068207c60e4484538eb1f21a765dec2250d659
release_profile=DRAFT_REFERENCE
authoritative_release_eligible=false
drawing_setup_evidence=null
```

The page-1 DXF and build-evidence hashes still match the manifest stage hashes
and the iteration-81 composed identity binding. No bytes changed.

## Ordered downstream gate inventory

### 1. Setup/readback — `NOT_PROVEN` (first unproven gate)

The manifest carries `drawing_setup_evidence=null`. The staged root has no
setup audit or readback artifact, and no live AutoCAD/FileIPC operation was
performed. The existing image/PDF path is correctly still
`DRAFT_REFERENCE`; the missing setup/readback evidence cannot be promoted to
authoritative evidence.

### 2. Persistence/reopen — `NOT_PROVEN`

No AutoCAD document persistence, close/reopen, or post-reopen identity/readback
artifact exists for this page-1 candidate. This gate was not attempted.

### 3. Visual — `NOT_PROVEN`

The run contains a rendered PNG, but no independent visual-review verdict or
visual promotion artifact. A rendered image is not an independent visual
acceptance result.

### 4. Dimension — `NOT_PROVEN`

The page-1 build evidence has `dimension_count=0` and empty written-dimension
maps. No dimension-first setup evidence or independent dimension verification
was run. This is not treated as a pass.

## Classification

```text
SETUP_READBACK=NOT_PROVEN
PERSISTENCE_REOPEN=NOT_PROVEN
VISUAL=NOT_PROVEN
DIMENSION=NOT_PROVEN
FIRST_UNPROVEN_GATE=SETUP_READBACK
HUMAN_GATE=NO
```

No production code, source, custody, candidate, DXF, or live CAD state was
mutated. No authoritative release claim was made.

## Next review

Return this exact read-only inventory to SOL for the next single bounded
action. Preserve the page-1 identity chain and do not skip the first
unproven gate by inferring visual or dimension acceptance from run-pdf output.
