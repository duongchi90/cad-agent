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

## AutoCAD .NET plugin — Option A baseline (historical evidence)

This subsection records the original Option A integration evidence. The current
read-only Mechanical BOM extension is recorded separately below.

- Candidate integration head: `4053c2a` on `integration/autocad-dotnet-option-a`.
- State: **Verified for the managed disposable smoke scope**; the repository's
  legacy-LISP aggregate marker remains a separate gate.
- Scope completed: Windows-only AutoCAD Mechanical 2027 managed plugin scaffold,
  versioned JSON/File IPC contracts, Mechanical no-op boundary, deterministic
  read-only review core, isolated Python dotnet_ipc backend, and the four
  command/dispatcher boundaries, plus the Windows `CADAGENT_DISPATCH` trigger,
  disposable .NET live-smoke harness, and one-shot `Application.Idle`
  disposable-close fix.
- C# evidence: restore/build/test passed on Release x64 with 51 passed, 0
  failed, 0 skipped; Autodesk reference-conflict warnings remain, and no
  Autodesk DLL was copied to plugin output.
- Python focused evidence: the .NET IPC focused suite passed 16 tests plus 18
  subtests; the opt-in live module passed 2 offline cleanup tests and skipped
  its one live test; the exact three-file Ruff gate passed.
- Authoritative verifier: **PASS** when run on commit `00797d9` with the
  explicit lock-matching Python 3.11 interpreter
  `D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe`:
  40/40 locked distributions, .NET 50/50, dotnet_ipc JUnit 34/0/0/0,
  offline JUnit 439/0/0/0, unavailable probes 2 + 7 skipped, and full Ruff
  passed. The integration-local `.venv-py311` remains incomplete, so the
  successful command supplied `-PythonExe` explicitly.
- Direct AutoCAD .NET smoke: **PASS** on a fresh disposable DXF in an isolated
  AutoCAD Mechanical 2027 process. Health and read-only review succeeded for
  handle `2F`; `close_disposable` returned
  `closed_without_saving=true`; after an 8-second independent postcondition
  check AutoCAD was back on `[Start]` and no longer had the DXF document open.
  The DXF remained on disk and was not saved or mutated.
- Automated AutoCAD live marker: **FAIL** when attempted with the legacy LISP
  dispatcher (`8 failed, 5 passed, 423 deselected`); the legacy close path
  reports `Automation Error. Drawing is busy`. The focused .NET live test
  reported `1 passed, 3 deselected`; this is retained as historical evidence for
  the legacy-LISP bootstrap failure and is separate from the direct managed
  smoke above.
- Safety boundary: no production save, repair, or mutation was added or run;
  the existing dispatcher was not modified.
- Evidence records: `docs/reviews/2026-08-01-autocad-dotnet-live-review.md`,
  `docs/reviews/2026-08-01-autocad-dotnet-close-live-review.md`, and
  `docs/reviews/2026-08-01-autocad-dotnet-close-live-followup.md`.
- Remaining gate before merge: run the authoritative offline verifier on this
  exact candidate, review the final diff, and then integrate only the reviewed
  commit. No COM/ActiveX code was added to the plugin.

## AutoCAD .NET plugin — Mechanical BOM 2A extension

- Candidate integration head: `ac75d20` on `integration/mechanical-bom-readonly`.
- Date: 2026-08-01.
- State: **Partially verified**. The managed read-only implementation, IPC
  contract, Python helper, unit tests, and authoritative offline verifier pass;
  the live AutoCAD Mechanical gate is explicitly **NOT RUN**.
- Scope: operation `mechanical_bom` reads direct ModelSpace `BlockReference`
  inserts and direct `AttributeReference` values, returns deterministic
  `component_count`/`components` payload data, and always reports
  `changed=false`. It does not traverse nested blocks, mutate/save drawings,
  create balloons, or use Mechanical SDK/COM/ActiveX/native APIs.
- Contract evidence: schema remains `1.0`; `parameters` is exactly `{}`;
  request/result examples and C#/Python validation are included under
  `contracts/autocad-ipc/`.
- C# evidence: Release x64 build/test passed with **58 passed, 0 failed, 0
  skipped**. Existing Autodesk `MSB3277` reference-conflict warnings remain;
  no Autodesk DLL was copied to plugin output.
- Python evidence: focused .NET IPC/live-module run passed **22 tests and 18
  subtests**, with one expected live prerequisite skip; the corrected
  disposable fixture test passed and verifies nested inserts are excluded.
- Authoritative verifier: **PASS** on `ac75d20` using the lock-matching Python
  3.11 interpreter `D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe`:
  C# **58/58**, dotnet IPC JUnit **36/0/0/0**, offline JUnit
  **443/0/0/0**, real-data unavailable probe **2 skipped**, AutoCAD Mechanical
  unavailable probe **7 skipped**, and Ruff/environment checks passed.
- AutoCAD live marker: **NOT RUN** because `CAD_AGENT_FILE_IPC`, a live
  AutoCAD HWND, and the declared File IPC bootstrap path were not available.
  No AutoCAD process or `Drawing1.dwg` was touched; no live PASS is inferred
  from build or unit tests.
- Evidence records: `docs/superpowers/specs/2026-08-01-mechanical-bom-readonly-design.md`,
  `docs/superpowers/plans/2026-08-01-mechanical-bom-readonly.md`, and the
  task reports/review packages in the plan's ignored SDD workspace.
- Remaining gate: complete the final whole-branch review, then merge this
  reviewed candidate into `main` and push it. A future operator-controlled
  disposable-DXF AutoCAD session may promote the live marker from `NOT RUN` to
  `PASS` or `SKIP`.

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
| Semantic IR | Verified | Final Python 3.11 offline gate passed with `python-solvespace` installed and zero offline skips; the approved private PDF completed all nine Semantic IR checkpoints. Assembly now uses raw detections for compound inference but persists only deterministic solver-ready constraints, reducing private page 1 from 538,983 raw relations to 3,693 retained constraints. |
| DXF build/review/repair | Verified | Final Python 3.11 offline DXF tests passed; production AutoCAD Mechanical mutation is outside this state. |
| Visual PDF-to-DXF fidelity | Verified for reviewable paper-layout and primary-linework scope | All nine delegated visual approvals were promoted into the fidelity manifest, and 9/9 promoted DXFs passed the dedicated read-only AutoCAD Mechanical review checkpoint. OCR/font, hatch, linetype, table placement, and dimension extensions now have review-only approval/reconstruction paths, but remain non-authoritative CAD content; model export remains excluded. |
| MCP/File IPC | Verified | Offline/fake IPC tests and the current six-test `autocad_mechanical` live gate passed on AutoCAD Mechanical 2027, including identical filenames under different directories and disposable-drawing cleanup. Active-document identity is full-path-bound. |
| Agent advice/audit | Verified | Agent execution is non-mutating by default. Application is a separate step bound to a saved report SHA-256 and exact source/IR hashes; approved constraint drops trigger a new solve before DXF generation. |
| Reproducible foundation | Verified | See the Foundation certificate and `docs/reviews/2026-07-22-reproducible-foundation.md`. |
| Thin image/PDF orchestration CLI | Verified | `cad_agent` run/resume and run-pdf/resume-pdf produce SHA-bound staged DXF and build evidence. Separate Mechanical review/repair commands enforce evidence, approval, backup, and second-review boundaries. |
| Production repair safety loop | Partially verified | Fake-MCP tests cover refusal, hash-verified backup, repair, second review, close-without-save rollback, and verified-backup reopen. A real staged-DXF review passed; no production drawing repair was requested or run. |

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
it. Review-only fidelity extensions must be rerun against the private PDF before
they can be considered for visual acceptance. Production repair remains a
separate human-approved operation with backup and a second live review; it was
not requested or run here.

## Latest continuation evidence

- Head: `dae1f2c128c1b58eb84a400d15b53d9ada127916`.
- Offline gate: `scripts/verify.ps1` passed with `387 passed, 8 deselected`; the
  unavailable-state probes recorded `2` real-data skips and `6` AutoCAD skips.
- Live gate: with AutoCAD Mechanical 2027 and the local File IPC dispatcher,
  `python -m pytest -m autocad_mechanical -ra -p no:cacheprovider` passed
  `6 passed, 389 deselected` in `143.68s`. All smoke files were disposable
  DXFs under `C:\temp`; each live test now closes its temporary drawing without
  saving.
- Fidelity hatch: commits `50e49a1`, `75b5b80`, and `939cc29` add stable
  candidate IDs, hash-bound polygon approval, native review-only `HATCH`
  reconstruction, and the corresponding CLI/design evidence. No production
  AutoCAD mutation is authorized.

## First product milestone decision

- State: **Verified** for the reviewable-DXF scope defined in
  `docs/PROJECT.md`.
- Date: `2026-07-28`.
- The approved nine-page private PDF completed Primitive IR, Semantic IR,
  optional audited Agent advice, staged/reconstructed DXF, headless structural
  checks, delegated visual promotion, and nine SHA-bound read-only AutoCAD
  Mechanical 2027 review checkpoints.
- The Agent path is advisory by default and has a separate explicit approval
  gate. No production drawing was mutated.
- Deferred work does not block the reviewable milestone: the user explicitly
  deferred the known font/OCR correction. Hatch, linetype, table placement,
  and true dimension semantics remain review observations rather than
  fabricated authoritative CAD entities.
- Production repair is an operational gate, not an automatic completion step:
  it still requires a named production DXF, matching evidence, verified backup,
  explicit repair confirmation, and a passing post-repair review.

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
- Follow-on fidelity evidence: after the user's blanket approval for correctable OCR, 419 ordinary OCR candidates were emitted as Unicode `TEXT`. Bounded table-region OCR then supplied 81 additional table-text candidates (pages 2, 3, 5, 6, 8, and 9); dashed-line candidates and 14 dimension-value candidates were observed with provenance outside Git. These later candidates remain `needs_review`: linetypes are heuristic, table placement needs visual review, dimensions are observations only (no inferred `DIMENSION` entities), and hatch/model-view reconstruction are intentionally not fabricated.
- Latest source verification: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` passed on `99f9931`; offline JUnit `tests=328; failures=0; errors=0; skipped=0`. The private integrated PDF/DXF overlay set covers 9/9 pages and remains a diagnostic comparison, not a fidelity pass.
- Linetype reconstruction: `fidelity-linetype-reconstruct` was added on `1c8cbc8`. It clones an existing private layout DXF, applies `FIDELITY_DASHED` only to hash-bound observed horizontal patterns, and writes revisioned candidates with a report. The private nine-page revision changed 76, 88, 7, 60, 8, 14, 82, 16, and 67 LINE entities respectively; this remains a visual candidate, not an authoritative linetype mapping. The official verifier passed on that commit with `330 passed, 6 deselected`.
- Region-quality gate: the review-only reconstruction now compares an unfiltered and a short/near-duplicate-stroke filtered candidate on the approved crop before writing DXF. A private nine-page rerun under `C:\temp\cad-agent-fidelity-e48f3970-region-quality-r2` rejected the filtered profile on all pages because local F1 would decrease (baseline: 0.799, 0.817, 0.758, 0.738, 0.826, 0.875, 0.785, 0.709, 0.764; filtered: 0.787, 0.808, 0.751, 0.728, 0.821, 0.851, 0.781, 0.701, 0.757). The composed-page candidates therefore retain baseline geometry; their review-only F1 values are 0.506, 0.539, 0.369, 0.425, 0.345, 0.419, 0.380, 0.313, and 0.432. This is evidence that the heuristic was safely rejected, not a visual-fidelity pass.
- Hatch observation: `fidelity-hatch-observe` now writes SHA-bound, review-only diagonal-stroke sidecars. Its nine-page private rerun found six candidates only on pages 3, 5, and 9 (peak segment counts 20, 5, and 10); it found none on the other pages. No DXF `HATCH` entity or production mutation is emitted, and every candidate remains `needs_review` pending explicit boundary approval.
- Remaining risk: all nine compositions remain `needs_review`, and broad layout approvals do not validate visual similarity. OCR text remains correctable and text placement/style needs review. Disciplined model-view reconstruction, true dimension semantics, verified linetypes/hatches, and table-cell placement still require visual review before they can be represented as authoritative CAD content.

## Delegated-review fidelity promotion

- State: **Verified** (reviewable paper-layout and primary-linework scope only)
- Date: `2026-07-28`
- Source: approved private PDF, SHA-256
  `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`.
- Private artifact identifier: source prefix `e48f3970`, final manifest SHA-256
  `e36814340cb8ec32b71cefec67f454de29619632be30283d3bf77311fe0fe90d`.
  The external root contains all nine rendered pages, structural round-trip
  passes, overlays, observations, approvals, composed DXFs, promotions, and
  Mechanical review reports.
- OCR evidence: all 419 new OCR candidates exactly match the candidate text and
  pixel boxes in the previously approved set. Nine fresh text-approval files
  were created. Fresh DXF text reconstruction was intentionally not run because
  the user deferred the known Vietnamese preview-font correction.
- Private-data command with `<private-pdf>` and `<private-fidelity-root>`
  environment values plus `CAD_AGENT_FIDELITY_REQUIRE_RECONSTRUCTION=1`:
  `python -m pytest tests\test_cad_agent_fidelity_real_data.py -ra -p
  no:cacheprovider` -> `1 passed`. The gate validates 9/9 promotion and
  Mechanical checkpoints.
- Live command: AutoCAD Mechanical 2027 session `acad.exe`, HWND `787740`,
  loaded File IPC dispatcher; `python -m pytest -m autocad_mechanical -ra -p
  no:cacheprovider` -> `5 passed, 355 deselected` in `82.78s`. All live DXFs
  were disposable.
- Authoritative offline command:
  `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1`
  -> exit `0`; offline JUnit `tests=353; failures=0; errors=0; skipped=0`.
- Delegated visual review: all nine `reconstruction_pages/page_XX/overlay.png`
  files were inspected on 2026-07-28. Red is source raster edge, cyan is
  reconstructed DXF edge, and green is overlap. The paper layout and primary
  vehicle/structure linework were accepted for review use on every page.
- Integrated promotion: all nine composed pages received a delegated visual
  approval record and transitioned through
  `approved_for_mechanical_review` to `mechanical_reviewed`. The dedicated
  command compared each promoted type/layer signature with AutoCAD and wrote
  nine SHA-bound reports. Every report records `save_performed=false` and
  `repair_performed=false`.
- Limit: this is not a production model or a claim of pixel-perfect fidelity.
  Text/font/OCR, hatch, linetype, table placement, and dimension semantics are
  outside the accepted primary-linework scope.

## Agent action approval evidence

- State: **Verified**
- Date: `2026-07-28`
- Hardened Head SHA: `4656e9f148bcd90c43c9eba672fdd5977f8cc307`.
- Design and plan:
  `docs/superpowers/specs/2026-07-28-agent-action-approval-design.md`;
  `docs/superpowers/plans/2026-07-28-agent-action-approval.md`.
- Safety behavior: the file runner and synthetic demo are advisory by default.
  Application is a second step requiring a saved report and SHA-256, literal
  `APPLY`, an approval reference, and exact source/Primitive/Semantic IR hashes.
  The audit records provenance/action hashes and the post-application solve
  state. Approved constraint drops are solved again before DXF generation.
- Advisory smoke: the real runner loaded the repository's 900x700 synthetic
  image and IR, produced 10 constraint-drop proposals, exited `0`, and recorded
  `application_requested=false` and `actions_applied=false` under
  `C:\temp\cad-agent-agent-gate-09c276c`.
- Final authoritative command is recorded in the release candidate section:
  353 offline tests, one private fidelity test, and five live AutoCAD
  Mechanical tests all passed.
- Boundary: this gate controls in-memory IR application only. It does not grant
  permission to repair or save a production AutoCAD drawing.

## Semantic constraint compaction evidence

- State: **Verified** on
  `4656e9f148bcd90c43c9eba672fdd5977f8cc307`.
- Date: `2026-07-28`.
- Design and plan:
  `docs/superpowers/specs/2026-07-28-semantic-constraint-compaction-design.md`;
  `docs/superpowers/plans/2026-07-28-semantic-constraint-compaction.md`.
- Behavior: assembly uses the complete detected set for compound inference and
  persists only `prune_constraints(...).kept` in Semantic IR.
- Focused result: compound/pruning tests -> `26 passed`; final authoritative
  offline run -> `353 passed, 7 deselected`; Ruff -> `PASS`.
- Approved private page 1: 1,170 primitives, 1,187 parts, 3,693 retained
  constraints, Semantic assembly `34.002s`. The earlier raw count was 538,983.
- Approved private page 5: 485 primitives, 495 parts, 1,392 retained
  constraints, Semantic assembly `5.758s`, matching the previously recorded
  pruning result.
- Final private-data and live AutoCAD Mechanical gates passed on the same
  candidate.

## File IPC active-document verification

- State: **Verified** on
  `4656e9f148bcd90c43c9eba672fdd5977f8cc307`.
- Date: `2026-07-28`.
- Release-gate observation: the initial four-test AutoCAD Mechanical run had
  one transient `block-get-attributes` timeout followed by one wrong-document
  `Entity not found`; four later component subcases passed.
- Root cause: raw-LISP document opening waited for a dispatcher ping and
  originally verified only the basename.
- Fix: `drawing_open()` verifies normalized `DWGPREFIX + DWGNAME`, retries one
  mismatch, and rejects identical basenames under another directory.
  `block_get_attributes()` retries one timeout because it is read-only. No
  mutating command is retried.
- Final live evidence: five tests passed in `82.78s`, including two disposable
  `same-name.dxf` files in different directories.
- Design and plan:
  `docs/superpowers/specs/2026-07-28-file-ipc-active-document-verification-design.md`;
  `docs/superpowers/plans/2026-07-28-file-ipc-active-document-verification.md`.

## Mechanical production review/repair evidence

- State: **Partially verified**
- Date: `2026-07-22`
- Implementation Head SHA: `ddf683431cabf4b4a12c3448aed0a20b7b54d429`
- Design and plan: `docs/superpowers/specs/2026-07-22-mechanical-production-repair-design.md`; `docs/superpowers/plans/2026-07-22-mechanical-production-repair.md`
- Safety behavior: `run` writes `build-evidence.json` bound to the staged DXF
  SHA-256. `mechanical-review` is read-only; `mechanical-repair` requires an
  approval reference, literal `--confirm-repair APPLY`, source/copy hash-verified
  DXF/evidence backups, and a passing post-repair live review before save. A
  failed review closes the modified drawing without save before reopening the
  verified backup.
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
- Remaining risks: at this historical foundation head, the approved private `real_data`
  gate and then-current live `autocad_lt` gate were not run, and the Agent
  entry points still auto-applied reports. Later sections supersede those
  specific limits with private-data, AutoCAD Mechanical 2027, and Agent
  approval-gate evidence.
