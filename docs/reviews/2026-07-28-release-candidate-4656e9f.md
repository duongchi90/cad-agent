# Release Candidate Record: 4656e9f

## Candidate

- Implementation Head SHA:
  `4656e9f148bcd90c43c9eba672fdd5977f8cc307`
- Date: `2026-07-28`
- Target: Windows, Python 3.11.9, AutoCAD Mechanical 2027,
  Tesseract 5.4.0.20240606
- Approval: user delegated visual-review decisions to Codex on 2026-07-28;
  the nine private promotion records use the reference
  `user-delegated-visual-approval-2026-07-28`.
- Scope: reviewable paper layout and primary linework. The user explicitly
  deferred font/OCR correction.

## Verification

### Authoritative offline gate

Command:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

Result: exit `0`; `353 passed, 7 deselected`; offline JUnit has
`tests=353`, `failures=0`, `errors=0`, `skipped=0`. Ruff, lock/environment,
Git whitespace, clean-tree, and side-effect checks passed.

Artifact hashes:

- offline JUnit:
  `3c540aac53b84cfbec6ea2d1f0f6e32acc9ed579891df2d2117e8673cf6c819b`
- unavailable real-data probe:
  `bce2a42d0cb27d56cb46246f346f46bb2660895f35df81d79a55b0be99a9a6a6`
- unavailable AutoCAD probe:
  `b8b3b7807d76dec3c8e188a33ef48d25845b18c937eadc38fe517a8c707b626c`

Locked dependencies:
`numpy=2.4.6; opencv-python=5.0.0.93; pytesseract=0.3.13;
Pillow=12.3.0; pypdf=6.14.2; PyMuPDF=1.28.0; ezdxf=1.4.4;
anthropic=0.117.1; python-solvespace=3.0.8; pytest=9.1.1; ruff=0.15.22`.

### Approved private fidelity gate

Input: private PDF outside Git, SHA-256
`e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`.

Command: set `CAD_AGENT_FIDELITY_PDF=<private-pdf>`,
`CAD_AGENT_FIDELITY_MANIFEST=<private-fidelity-root>\fidelity-run-manifest.json`,
and `CAD_AGENT_FIDELITY_REQUIRE_RECONSTRUCTION=1`, then run:

```powershell
python -m pytest tests\test_cad_agent_fidelity_real_data.py -ra `
  -p no:cacheprovider
```

Result: exit `0`; `1 passed`. The gate validates all nine composed-page,
promotion, and read-only Mechanical review checkpoints. Private manifest
SHA-256:
`e36814340cb8ec32b71cefec67f454de29619632be30283d3bf77311fe0fe90d`.
Private JUnit SHA-256:
`ea2cb63ee48f3d6bf487b875e55d5bf8eac32338d731859879c234ceb8bc754b`.

### AutoCAD Mechanical gate

Session: AutoCAD Mechanical 2027, `acad.exe`, HWND `787740`, loaded local File
IPC dispatcher. Command with the live environment enabled:

```powershell
python -m pytest -m autocad_mechanical -ra -p no:cacheprovider
```

Result: exit `0`; `5 passed, 355 deselected` in `82.78s`. Coverage includes
component/attribute round trips, primitive review/repair on disposable DXFs,
and two `same-name.dxf` files in different disposable directories. Live JUnit
SHA-256:
`1df4cf715cb1c3bd920ceca3bfc60144e9d7803d8e0ed96011a3c1759eba5e29`.

Separately, the dedicated fidelity workflow promoted and reviewed 9/9 private
pages through the same AutoCAD session. Every report records
`save_performed=false` and `repair_performed=false`.

## Safety adjudication

- Active drawing identity is the normalized full `DWGPREFIX + DWGNAME`, not a
  basename.
- Production repair verifies stable source hashes and equal backup-copy hashes
  before mutation.
- Failed repair closes the modified drawing without saving before it opens the
  verified backup.
- Agent execution is advisory by default. Application is bound to a saved
  report SHA-256 and exact source/Primitive/Semantic IR SHA-256 values; a
  post-drop solve feeds DXF generation.
- Fidelity promotion authorizes only read-only Mechanical review. It prohibits
  repair, production save, and model export.
- Private files, generated private artifacts, credentials, and crash logs are
  absent from Git.
- The release verification itself was read-only with respect to production
  drawings. Production-backup checklist items are therefore not applicable to
  this candidate run; the repair capability was verified with disposable/fake
  inputs only.

## Remaining limits

- Font/OCR correction is explicitly deferred.
- Hatch, linetype, table placement, model export, and true dimension semantics
  are not certified as authoritative CAD content.
- No customer/production drawing was repaired. A future production repair
  still requires a named approval, verified backup, explicit `APPLY`, and a
  passing post-repair review.
