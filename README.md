# CAD Agent

CAD Agent converts CAD images/PDFs into structured IR and DXF, then validates
the result headlessly and through AutoCAD LT.

## Supported release environment

- Windows
- Python 3.11
- AutoCAD LT
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

- `cad_agent/`: thin `doctor`, `run`, and `resume` orchestration with durable manifests.
- `primitive_ir_lib/`: image/PDF to Primitive IR.
- `semantic_ir_lib/`: parts, compounds, constraints, pruning, and solving.
- `agent_lib/`: audited advice for ambiguous cases.
- `dxf_builder_lib/`: DXF build, headless review, and headless repair.
- `mcp_integration_lib/`: AutoCAD LT live review/repair through File IPC.

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
incomplete stage. The CLI produces staged DXF only; it never performs AutoCAD LT
repair or production mutation.

## Safety

Private drawings and annotations stay outside Git. Missing private/live tests are
reported as `SKIP` or `NOT RUN`. The specialized markers are `real_data` and
`autocad_lt`; `.\scripts\verify.ps1` probes their unavailable state but never
executes either live gate. Unverified calibration, ambiguous recognition, and
production DXF mutation require human approval.

## Canonical documentation

- Product and scope: `docs/PROJECT.md`
- Current architecture: `docs/ARCHITECTURE.md`
- Verified status: `docs/STATUS.md`
- Test and release gates: `docs/QUALITY.md`
- Agent working agreement: `AGENTS.md`

`HANDOFF.md` and `CAD-Agent-Kien-Truc-v1_3.md` are retained as historical
records; they are not current status sources.
