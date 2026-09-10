# Page-1 reuse execution packet

Date: 2026-09-10
Status: prepared; read-only/offline; not a production approval
Bounded action: SOL continuation checkpoint `VERDICT=PASS`
Supported scope: freeze the evidence-backed page-1/page-2 reuse boundary and
define one future read-only viewport registration request.

## Evidence identity

The private PDF, DWG, rendered images, and disposable DXF remain outside Git.
This record contains metadata and hashes only; it does not publish their bytes,
private annotations, or customer drawing content.

| Artifact | Identity |
| --- | --- |
| PDF source bundle | SHA-256 `13d822cf828cccc6cd21b19ec3c410f0ea89aef440aeca4c96248e86c08b5b38`; page size `2382x1685` |
| PDF page-1 render | SHA-256 `b03477a1f9cd5df4f8ee6125f8faed1bf35586cb4f891c30bf2351929833b9d0` |
| PDF page-2 render | SHA-256 `60a730042a2df51116a3e0e4840d797a3cdeb6370c899fdcc3af382af1d30a97` |
| Base DWG read-only observation | SHA-256 `78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8`; `DBMOD=0`; `XREF=0` |
| Page-1/page-2 reuse oracle | SHA-256 `b69a65f98b11e5198f486f48c59e6ef90bc8d5b02e70415baf580108c5f959e7` |
| Page-2 correspondence oracle | SHA-256 `f6d230ce4cde824c023b16f8bb7993063fabf563603bfa2cef0554634a610050` |

The provisional registration oracle consumed 72 bounded eligible INSERT
records, preserved five unresolved handles, and explicitly does not claim exact
pixel registration or exact CAD identity. Its confidence is
`LOW_PROVISIONAL`.

## Frozen reuse boundary

Eligible page-2/base groups:

- `cabin-front`
- `chassis-underbody`
- `wheel-axle-geometry`
- `front-view-envelope`
- `drawing-frame-table`

Frozen page-1 after-conversion delta groups:

- `cargo-side-frame`
- `cargo-side-rail-curtain-structure`
- `cargo-upper-structure`
- `cargo-top-support-layout`
- `curtain-or-rail-support-details`
- `cargo-width-envelope-annotation`
- `rear-cargo-upper-structure`
- `rear-door-or-open-frame-arrangement`
- `rear-upper-handrail-supports`
- `after-conversion-title-text`
- `sheet-number-and-document-text`
- `page-1-annotations`

The dimension observation preserves the reusable/same set `5250`, `1230`,
`2585`, `1435`, `1490`, `2610`, `1355`, `1525`, and `1700`; the top-view cargo
width observation changes from `1800` to `1760`. These observations are not
CAD-export authorization.

## Frozen candidate boundary

The disposable page-1 candidate remains frozen and unpromoted. Its metadata is:

- DXF SHA-256: `19bcd2d4ddfe17be0ff73606064562207d7f9aefa756e108b3950b417bb6982f`
- render SHA-256: `490ba1fe37163b3319fcd89614bb0c548afee83fb5e5d0985e63ccd1ec3ca6bb`
- overlay SHA-256: `b73adbe6f9c50e929a6465b41452cbd59d246c708cc72412a8df28c3bace08c7`
- report SHA-256: `dd48e3e5c1e9cf08c7b00a04e80bd8dc5250a1c8c4285e8ae3461fb373e7a867`
- geometry fingerprint: `81a0e2c3ecfa7ca38ddd069d7866ced392136e53f780fe487a2f61bb182928d0`
- metrics: full-page precision `0.980933`, recall `0.874512`, F1 `0.924671`; content-ROI F1 `0.924540`
- visual-fidelity review: `PASS_VISUAL_FIDELITY` at established execution-output item 13
- unresolved: production promotion and authorization to use this candidate as the page-1 reuse solution

The candidate remains `ACCEPTED_DISPOSABLE_FROZEN`. The item-13 independent SOL
visual-fidelity review passed for the frozen hashes; that verdict is not a
release, production-promotion, or page-1 reuse-solution authorization.

## Future live registration request

When the declared AutoCAD/FileIPC prerequisites are present, execute exactly
one existing-owner read-only request:

```text
operation=viewport_query
request_id=layout-vp-126babe-20260910
handle=126BABE
drawing_sha256=78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8
approval=null
```

Expected invariants are `success=true`, `changed=false`, one returned entity
handle `126BABE`, no top-level errors, equal before/after source hashes,
`DBMOD` unchanged at zero, and closed field states for
`center_point`, `width`, `height`, `view_center`, `view_height`, `view_target`,
and `twist_angle`. Every field must be `OBSERVED` with a finite value,
`UNSUPPORTED` with `PROPERTY_UNAVAILABLE`, or `ERROR` with an allowed read
failure reason. Width, height, and view height must be positive. No guessed
zero/default is accepted.

The observed result may refine registration; if it changes the candidate or
decision-relevant evidence, the changed evidence requires a fresh review. It
may not promote or mutate the frozen candidate. The item-13 visual-fidelity
pass remains bound to the unchanged frozen hashes. At packet creation, the
required live prerequisites were absent and no AutoCAD process was running, so
this request remains `NOT RUN`.

## Safety and verification

- No source DWG, PDF, candidate DXF, AutoCAD state, or FileIPC state was mutated.
- No new geometry, extraction, Xref, save, or production promotion was done.
- The complete packet is stored outside Git at the local evidence boundary;
  its SHA-256 is `312e2ce76ebf3998cbf7b9d1f6e64c8c5d6c6c2ec3d357047307193a2dfebafe`.
- This Git record is metadata-only. The branch remains partially verified and
  the live AutoCAD/private-fidelity gates remain `NOT RUN`/unavailable.
