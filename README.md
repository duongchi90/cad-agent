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

- `primitive_ir_lib/`: image/PDF to Primitive IR.
- `semantic_ir_lib/`: parts, compounds, constraints, pruning, and solving.
- `agent_lib/`: audited advice for ambiguous cases.
- `dxf_builder_lib/`: DXF build, headless review, and headless repair.
- `mcp_integration_lib/`: AutoCAD LT live review/repair through File IPC.

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

`HANDOFF.md` and `CAD-Agent-Kien-Truc-v1_3.md` are retained as historical
records; they are not current status sources.
