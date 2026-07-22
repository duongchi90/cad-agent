# CAD Agent Status

## Status vocabulary

- **Verified:** the named command ran successfully on the named commit and
  environment.
- **Partially verified:** deterministic coverage passed, but a required private
  data or AutoCAD Mechanical gate has not run on the same candidate.
- **Unverified:** no current reproducible evidence supports the claim.
- **NOT RUN:** the gate was intentionally not executed; this is never a pass.

## Supported release environment

- Windows
- Python 3.11
- AutoCAD Mechanical 2027
- Tesseract 5.4.0.20240606

## Authoritative verification

After bootstrap, run `.\scripts\verify.ps1`. It runs the offline gate and
collects unavailable-state probes for `real_data` and `autocad_mechanical` as explicit
`SKIP` results with prerequisites removed. A real private-data or live AutoCAD
Mechanical gate that was not separately executed remains `NOT RUN`.

## Pre-foundation baseline

| State | Date | Commit | Environment | Command | Result |
|---|---|---|---|---|---|
| Verified | 2026-07-22 | `908d016` | Windows, bundled Python 3.12.13, Tesseract 5.4.0.20240606 | `python -m pytest primitive_ir_lib/tests semantic_ir_lib/tests dxf_builder_lib/tests mcp_integration_lib/tests agent_lib/tests -q -p no:cacheprovider` | `255 passed, 11 skipped, 3 warnings` |

This baseline demonstrates that the existing core is worth preserving. It is
not the Python 3.11 foundation certificate because seven solver tests were among
the skips and the run used Python 3.12.

## Current module status

| Area | State | Evidence and limit |
|---|---|---|
| Primitive IR | Verified | Final Python 3.11 offline gate passed with zero skips; the approved private PDF, identified by SHA-256 below, completed Primitive IR for all nine pages. |
| Semantic IR | Verified | Final Python 3.11 offline gate passed with `python-solvespace` installed and zero offline skips; the approved private PDF completed all nine Semantic IR checkpoints. |
| DXF build/review/repair | Verified | Final Python 3.11 offline DXF tests passed; production AutoCAD Mechanical mutation is outside this state. |
| Visual PDF-to-DXF fidelity | Partially verified | Private paper-coordinate baselines, overlays, region approvals, reconstruction candidates, and table-grid observations exist outside Git. They are `needs_review`; neither the old analysis DXFs nor a headless DXF review proves visual similarity to the PDF. |
| MCP/File IPC | Verified | Offline/fake IPC tests and all four `autocad_mechanical` live File IPC tests passed on AutoCAD Mechanical 2027. Production drawing mutation remains separately gated by backup and human approval. |
| Agent advice/audit | Partially verified | Offline tests passed; `run_agent()` is non-mutating, but the current run/demo entry points auto-apply reports and are not approved production mutation paths. |
| Reproducible foundation | Verified | See the Foundation certificate and `docs/reviews/2026-07-22-reproducible-foundation.md`. |
| Thin image/PDF orchestration CLI | Verified | `cad_agent` run/resume and run-pdf/resume-pdf produce SHA-bound staged DXF and build evidence. Separate Mechanical review/repair commands enforce evidence, approval, backup, and second-review boundaries. |
| Production repair safety loop | Partially verified | Fake-MCP tests cover refusal, backup, repair, second review, and rollback. A real AutoCAD Mechanical staged-DXF review passed; no production drawing repair was run. |

## Known production gates

- Calibration may be auto-accepted only with at least two independent
  candidates and median relative error at most 3 percent. Current production
  callers must opt into consensus and retain human approval for unverified
  scale.
- Private drawing benchmarks remain outside Git and are addressed by SHA-256.
- AutoCAD Mechanical mutation requires backup, human approval, live review, repair, and
  a second review.

## Next slice

Maintain the SHA-bound private benchmark and run any future optimization against
it. Production repair remains a separate human-approved operation with backup
and a second live review; it was not requested or run here.

## Thin vertical-slice CLI evidence

- State: **Verified**
- Date: `2026-07-22`
- Implementation Head SHA: `8410712f0c7c23f707acc1b251620712806be971`
- Design and plan: `docs/superpowers/specs/2026-07-22-vertical-slice-cli-design.md`; `docs/superpowers/plans/2026-07-22-vertical-slice-cli.md`
- Focused command: `& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_cad_agent_cli.py -q -p no:cacheprovider` → `3 passed`
- Authoritative command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` → exit `0`
- Offline JUnit: `tests=295; failures=0; errors=0; skipped=0`
- `real_data`: unavailable-state probe `SKIP` (`tests=1; skipped=1`); approved private run `NOT RUN`
- `autocad_lt`: historical unavailable-state probe `SKIP` (`tests=4; skipped=4`); live session run `NOT RUN` at this pre-target-change commit
- Historical limitation: this former image-only slice is superseded by the PDF vertical-slice evidence below.

## PDF vertical-slice orchestration evidence

- State: **Verified**
- Date: `2026-07-22`
- Implementation Head SHA: `1669f25e88847b47284219c92769801a5bc81768`
- Design and plan: `docs/superpowers/specs/2026-07-22-pdf-vertical-slice-design.md`; `docs/superpowers/plans/2026-07-22-pdf-vertical-slice.md`
- Behavior: `run-pdf` and `resume-pdf` SHA-bind a PDF, its explicit scale approval, the package render manifest, and per-page rendered PNG, Primitive IR, Semantic IR, staged DXF, and build-evidence checkpoints. Resume reuses intact pages, rebuilds only invalid dependent stages, and rejects a changed PDF before reuse.
- Focused command: `& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_cad_agent_pdf.py tests\test_cad_agent_cli.py tests\test_cad_agent_live.py -q -p no:cacheprovider` -> `12 passed`; coverage includes multi-page output, byte-identical resume, changed source refusal, affected-page rebuild, missing Primitive IR recovery, and CLI run/resume.
- Live staged review: a newly generated two-page PDF under `C:\temp\cad-agent-pdf-live-20260722` completed through `run-pdf`; `mechanical-review` opened only page 1's staged DXF through the AutoCAD Mechanical 2027 File IPC dispatcher and reported `passed=true`, `structural_checked=1`, `geometry_checked=1`, with no mismatches or warnings. No repair or production save was requested.
- Current live marker gate: with AutoCAD Mechanical HWND `393650` and the loaded dispatcher, `& '.\.venv-py311\Scripts\python.exe' -m pytest -m autocad_mechanical -ra -p no:cacheprovider` -> `4 passed, 305 deselected` in `69.50s`; the smoke scope used only disposable DXFs under `C:\temp`.
- Authoritative command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` -> exit `0`; offline JUnit `tests=304; failures=0; errors=0; skipped=0`; SHA-256 `d9f8d85ed0ae42b14d4db00639a51d329a438b11ee2878cb8428b576dbd0e0fe`.
- `real_data`: unavailable-state probe `SKIP` (`tests=1; skipped=1`), SHA-256 `9bef0b1195208264fc4b7e0f07c0ec898f659f9925b6caa983143659ebb107d5`; approved private run `NOT RUN`.
- `autocad_mechanical`: unavailable-state probe `SKIP` (`tests=4; skipped=4`), SHA-256 `ec6a9b12540c9188a76988880e3651f81c63c399d4da5c989002f2c9b4b801f4`.
- Remaining risk: no approved private PDF was run at this historical command; the later full private-PDF evidence is recorded below.

## Approved private PDF full-run evidence

- State: **Verified**
- Date: `2026-07-22`
- Approved input: private PDF SHA-256 `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`; it remains outside Git.
- Calibration: all nine title blocks state `1:40`; the approved 144-DPI conversion is `7.055555555556 mm/px`. OCR also records any detected scale label as a `needs_verification` candidate and never overrides the approved manual calibration.
- Checkpoints: all 9/9 rendered-page, Primitive IR, Semantic IR, staged-DXF, and SHA-bound build-evidence records completed under private staging. Every staged DXF passed the headless reviewer.
- Visual-fidelity correction: these checkpoints are analysis-pipeline evidence only. The page-wide model-scale transform, zero extracted text primitives, and semantic `INSERT` overlays mean they must not be read as faithful drawing-sheet reconstructions. The separate fidelity workflow below is the only current visual-comparison path.
- Dense-data optimization evidence: page 1 completed compound recognition with 1,170 primitives and 538,983 detected constraints. Page 5 reduced 109,399 raw constraints to 1,392 after pruning; its 478 relevant lines exceed the documented 1,000-coordinate solver capacity, so the DXF preserved calibrated primitive geometry through the explicit `too_many_unknowns` fallback instead of spending minutes in an unstable solve.
- Live staged review: the standard `cad_agent mechanical-review` command with `--timeout-s 60` reviewed page 5 through AutoCAD Mechanical 2027 and reported `passed=true`, `structural_checked=485`, `geometry_checked=485`, no mismatches, no warnings, and no degraded geometry check. It was read-only: no repair or save was requested.
- Final repository verification: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` passed on `8c24896` with `318 passed, 5 deselected`; the final timeout-option revision is covered by focused CLI/live tests and the same verifier run.

## Fidelity reconstruction CLI evidence

- State: **Partially verified**
- Date: `2026-07-22`
- Implementation Head SHA: `374e75fb15abe9fd33df74fe61a84c966946f488`
- Design and plan: `docs/superpowers/specs/2026-07-22-fidelity-reconstruction-cli-design.md`; `docs/superpowers/plans/2026-07-22-fidelity-reconstruction-cli.md`
- Behavior: the private `fidelity-pdf`, `fidelity-overlay`, `fidelity-region-proposal`, `fidelity-region-approve`, `fidelity-reconstruct`, and `fidelity-observe` commands bind source and artifact hashes, keep output outside Git, forbid Mechanical operations on fidelity DXFs, and preserve `needs_review` rather than claiming a visual pass.
- Private source evidence: all nine paper-coordinate baselines and overlays completed. Under the user's explicit 2026-07-22 approval, every page has one SHA-bound `sheet_content` layout-region approval, reconstruction candidate, and composed page DXF outside Git (page 5 uses revision 4). These are broad layout regions, not approved model-view geometry. Table-grid observations and bounded table-region OCR completed for 9/9 pages. After the user's explicit approval to accept OCR subject to later correction, all 419 ordinary OCR candidates were hash-approved and emitted as `TEXT` into fresh private DXFs; the original geometry layouts remain unchanged.
- Authoritative command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` -> exit `0` on `ef7140d`; offline JUnit `tests=327; failures=0; errors=0; skipped=0`.
- `real_data`: private command evidence exists but the marker benchmark is **NOT RUN** for this workflow; `autocad_mechanical`: **NOT RUN** by design because fidelity artifacts are refused before live review/repair.
- Remaining risk: all nine compositions remain `needs_review`, and broad layout approvals do not validate visual similarity. OCR text remains correctable and text placement/style needs review. Dimensions, linetypes, hatch, table-cell-to-DXF mapping, and disciplined model-view reconstruction remain unfinished.

## Mechanical production review/repair evidence

- State: **Partially verified**
- Date: `2026-07-22`
- Implementation Head SHA: `ddf683431cabf4b4a12c3448aed0a20b7b54d429`
- Design and plan: `docs/superpowers/specs/2026-07-22-mechanical-production-repair-design.md`; `docs/superpowers/plans/2026-07-22-mechanical-production-repair.md`
- Safety behavior: `run` writes `build-evidence.json` bound to the staged DXF SHA-256. `mechanical-review` is read-only; `mechanical-repair` requires an approval reference, literal `--confirm-repair APPLY`, timestamped DXF/evidence backups, and a passing post-repair live review before save.
- Focused tests: `tests/test_cad_agent_live.py` and `tests/test_cad_agent_cli.py` → `7 passed`; coverage includes missing approval refusal, backup creation, successful fake repair, and failed-second-review rollback.
- Live staged review: `cad_agent mechanical-review` on a disposable DXF under `C:\temp` through AutoCAD Mechanical 2027 → `passed=true`, `structural_checked=10`, `geometry_checked=10`, no mismatch or degraded geometry check.
- Authoritative command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` → exit `0`; offline JUnit `tests=299; failures=0; errors=0; skipped=0`; SHA-256 `80140e4ca6c7089742a8282ad0e9cea083ce167c110b91f11cbe3f0d485e3569`
- `real_data`: unavailable-state probe `SKIP` (`tests=1; skipped=1`), SHA-256 `f6b25dd4aa7da9b5c12eaad290bc042061a53b54897fec50d176e9035f0aadb3`; approved private run `NOT RUN`
- `autocad_mechanical`: unavailable-state probe `SKIP` (`tests=4; skipped=4`), SHA-256 `69ba0f74887b47dfb2a09f4a4a670acdead32db67677e63f70b28084f7a402e5`
- Remaining risk: no customer/production drawing was repaired. A real repair remains gated on an approved input, backup verification, explicit operator approval, and a post-repair review.

## Historical File IPC evidence before the AutoCAD Mechanical target change

- State: **Partially verified**
- Date: `2026-07-22`
- Head SHA: `52b92885698827c36984f02e8461f4e18de6072c`
- Command: `CAD_AGENT_FILE_IPC=1`, AutoCAD HWND `393650`, and the locally loaded dispatcher; `& '.\.venv-py311\Scripts\python.exe' -m pytest -m autocad_lt -ra -p no:cacheprovider`
- Result: `4 passed, 296 deselected` in `69.52s`; the run covered active-document access, primitive live review/repair, beam INSERT attribute repair, and five remaining component INSERT repairs.
- Session: AutoCAD Mechanical 2027, process `acad.exe`, HWND `393650`.
- Safety: all smoke DXFs were newly created under `C:\temp`; no production drawing was saved or modified.
- Limit: the then-current marker was `autocad_lt`, so this evidence predates the AutoCAD Mechanical target contract and is retained as historical context only.

## AutoCAD Mechanical 2027 target evidence

- State: **Verified**
- Date: `2026-07-22`
- Implementation Head SHA: `bda0cf0ea094d67bddca65aa8f9df953a4f25078`
- Design and plan: `docs/superpowers/specs/2026-07-22-autocad-mechanical-2027-design.md`; `docs/superpowers/plans/2026-07-22-autocad-mechanical-2027.md`
- Live command: `CAD_AGENT_FILE_IPC=1`, AutoCAD Mechanical HWND `393650`, and the loaded dispatcher; `& '.\.venv-py311\Scripts\python.exe' -m pytest -m autocad_mechanical -ra -p no:cacheprovider` → `4 passed, 296 deselected` in `69.41s`
- Live scope: active-document access, primitive live review/repair, beam INSERT attribute repair, and five remaining component INSERT repairs; every smoke DXF was created under `C:\temp`.
- Session: AutoCAD Mechanical 2027, `acad.exe`, HWND `393650`.
- Authoritative command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` → exit `0`
- Offline JUnit: `tests=295; failures=0; errors=0; skipped=0`; SHA-256 `5d380796e1c5582ee3f1df48b9979853cda782f66ba3268fe8a46f5126b57298`
- `real_data`: unavailable-state probe `SKIP` (`tests=1; skipped=1`); SHA-256 `c2e3927cd97a46b1c45658ec263e5d221cb169a0be3de26a99a5651c9e42d289`; approved private run `NOT RUN`
- `autocad_mechanical`: unavailable-state probe `SKIP` (`tests=4; skipped=4`); SHA-256 `039a06a9c3c6a0a4aa7c6283fae44cd4c44caa04c7809f5bc7ffdbe20146be74`
- Remaining risk: production drawing mutation remains prohibited without a verified backup, explicit human approval, live review, repair, and a second review.

## Foundation certificate

- State: **Verified**
- Date: `2026-07-22`
- Reviewed implementation Head SHA: `a96a31df6a735d103c29548855fa8a170e535c18`
- Command: `.\scripts\verify.ps1`
- Exit code: `0`
- Python: `3.11.9`
- Tesseract executable: `C:\Program Files\Tesseract-OCR\tesseract.exe (tesseract v5.4.0.20240606)`
- Dependencies: `numpy=2.4.6; opencv-python=5.0.0.93; pytesseract=0.3.13; Pillow=12.3.0; pypdf=6.14.2; PyMuPDF=1.28.0; ezdxf=1.4.4; anthropic=0.117.1; python-solvespace=3.0.8; pytest=9.1.1; ruff=0.15.22`
- Offline JUnit: `tests=292; failures=0; errors=0; skipped=0`; SHA-256 `c35bde5ee7f22eeb7489baa7bcabdf3a16b6c89555a079482e0d3d61a41e742c`
- `real_data`: `SKIP` unavailable-state probe; `tests=1; skipped=1`; SHA-256 `b63e0effc175a3854ea6b217d68f894a3fcc0bc7299a5616f6f3d452c2028986`
- `autocad_lt`: `SKIP` unavailable-state probe; `tests=4; skipped=4`; SHA-256 `6818b5d401859ff92ee0b3b3f40891ac320018bdf386aa29bc8fb2cb0aa1bd0c`
- Unexpected warnings: `0`; scoped intentional ROI warning policy remains documented in `docs/QUALITY.md`
- Ruff: `PASS`
- Lock/environment, Git whitespace, and repository content-hash side-effect checks: `PASS`
- Verification transcript SHA-256: `486ec0fe693a209a866e96673a34e249b4496ec3906e35d101e44f538c93de3a`
- Independent review: `docs/reviews/2026-07-22-reproducible-foundation.md`; three final-head reports; unresolved P0/P1 `0`
- Remaining risks: the approved private `real_data` gate and live `autocad_lt` gate were NOT RUN; current `agent_lib.run`/demo auto-apply behavior is not an approved production mutation path.
