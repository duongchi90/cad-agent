# CAD Agent

CAD Agent converts CAD images/PDFs into structured IR and DXF, then validates
the result headlessly and through AutoCAD Mechanical 2027.

## Supported release environment

- Windows
- Python 3.11
- AutoCAD Mechanical 2027
- Tesseract 5.4.0.20240606

## Quick start

```powershell
$python311 = py -3.11 -c "import sys; print(sys.executable)"
.\scripts\bootstrap.ps1 -PythonExe $python311
.\scripts\verify.ps1
```

The bootstrap creates/reuses `.venv-py311` and installs the hash-locked
`requirements/windows-py311.lock`. Verification rejects a stale/polluted
environment, runs the offline suite with zero skips, safely probes both
specialized markers as unavailable, runs Ruff/Git/content checks, and writes
three JUnit artifacts under `.artifacts/`.

## Packages

- `cad_agent/`: thin image/PDF orchestration with durable manifests.
- `primitive_ir_lib/`: image/PDF to Primitive IR.
- `semantic_ir_lib/`: parts, compounds, constraints, pruning, and solving.
- `agent_lib/`: audited advice for ambiguous cases.
- `dxf_builder_lib/`: DXF build, headless review, and headless repair.
- `mcp_integration_lib/`: AutoCAD Mechanical 2027 live review/repair through File IPC.

## Staged image run

For a PNG/JPG drawing with a verified manual scale, the orchestration CLI records
an explicit calibration approval reference and creates resumable checkpoints:

```powershell
& '.\.venv-py311\Scripts\python.exe' -m cad_agent run `
  --input C:\approved-data\drawing.png `
  --output-dir output\drawing-run `
  --scale-mm-per-px 0.0917 `
  --calibration-approval 'approved ticket/reference'
```

Use `python -m cad_agent doctor --json` to inspect prerequisites, and `resume`
with the generated `run-manifest.json` plus the original input to retry only an
incomplete stage. The CLI produces staged DXF only; it never performs AutoCAD Mechanical
repair or production mutation.

## Staged PDF run

`run-pdf` renders every page then creates independently resumable Primitive IR,
Semantic IR, DXF, and build-evidence checkpoints per page. It also records the
manual-scale approval and source SHA-256 in `pdf-run-manifest.json`:

```powershell
& '.\.venv-py311\Scripts\python.exe' -m cad_agent run-pdf `
  --input C:\approved-data\drawing.pdf `
  --output-dir output\drawing-pdf-run `
  --scale-mm-per-px 0.0917 `
  --calibration-approval 'approved ticket/reference' `
  --dpi 144
```

Use `resume-pdf` with that manifest and the original PDF to retry only missing
page stages. A changed source PDF is rejected by SHA-256 before any checkpoint
is reused.

To review a staged DXF in AutoCAD Mechanical, retain its `build-evidence.json`
and run `cad_agent mechanical-review` with the AutoCAD window handle and loaded
dispatcher. `mechanical-repair` is separate: it requires an approval reference,
`--confirm-repair APPLY`, and a writable backup directory before it can save a
repair.

## Safety

Private drawings and annotations stay outside Git. Missing private/live tests are
reported as `SKIP` or `NOT RUN`. The specialized markers are `real_data` and
`autocad_mechanical`; `.\scripts\verify.ps1` probes their unavailable state but never
executes either live gate. Unverified calibration, ambiguous recognition, and
production DXF mutation require human approval.

## Mixed-scale PDF sheets

A PDF page can contain views with different scales such as `TL 1:40` and
`TL 1:20`. PDF rendering records OCR scale-label candidates and the associated
geometry region in its per-page manifest. A candidate remains
`needs_verification`: it never replaces an approved calibration or authorizes
DXF production automatically.

## Canonical documentation

- Product and scope: `docs/PROJECT.md`
- Current architecture: `docs/ARCHITECTURE.md`
- Verified status: `docs/STATUS.md`
- Test and release gates: `docs/QUALITY.md`
- Agent working agreement: `AGENTS.md`

`HANDOFF.md` and `CAD-Agent-Kien-Truc-v1_3.md` are retained as historical
records; they are not current status sources.
