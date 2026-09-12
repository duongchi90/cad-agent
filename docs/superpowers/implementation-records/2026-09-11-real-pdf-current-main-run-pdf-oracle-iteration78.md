# Current-Main Real-PDF `run-pdf` Oracle — Iteration 78

Date: 2026-09-11 (Asia/Saigon)
Canonical main SHA: `e8fc0092ee46750e50de0ea408fd91811cae10c2`
Executor branch: `codex/audit-text-style-compat-20260910`

## Authority and exact scope

SOL's iteration-77 decision was:

```text
VERDICT=CLEAR_CONTINUE
NEXT_SINGLE_BOUNDED_ACTION=Run exactly one fresh disposable current-main
run-pdf oracle ...
HUMAN_GATE=NO
```

The exact approved inputs were:

- source: `202607092308.pdf`;
- source SHA-256:
  `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`;
- calibration approval: `STATUS-e48f3970-144dpi-1to40`;
- scale: `7.055555555556` mm/px;
- DPI: `144`;
- clean detached worktree: `C:/temp/cad-agent-real-pdf-current-main-iter78`;
- isolated output root:
  `C:/temp/cad-agent-real-pdf-current-main-iter78-run`.

The exact command was:

```powershell
py -3.11 -m cad_agent run-pdf `
  --input C:/Users/dkv/Downloads/202607092308.pdf `
  --output-dir C:/temp/cad-agent-real-pdf-current-main-iter78-run/staged `
  --scale-mm-per-px 7.055555555556 `
  --calibration-approval STATUS-e48f3970-144dpi-1to40 `
  --dpi 144
```

The identity context was recorded before execution in:

`C:/temp/cad-agent-real-pdf-current-main-iter78-run/oracle-context.json`

## Result

The one oracle exited `1` before render/page processing:

```text
ModuleNotFoundError: No module named 'fitz'
```

The failure phase was the existing `primitive_ir_lib.run_pdf` import. No
rendered page, Primitive IR, Semantic IR, DXF, or build-evidence stage was
completed. The generated manifest is:

`C:/temp/cad-agent-real-pdf-current-main-iter78-run/staged/pdf-run-manifest.json`

Manifest SHA-256:

`d1050dc93adb37e4ea185a0a02d32d30e867595cdc608b714cd7f8e7955f39fe`

Manifest state: `render.state=pending`, `pages=[]`, completed page stages `0`.

## Fail-closed disposition

- Classification: `NOT_PROVEN` for the current-main source-to-run-pdf gate.
- This is a missing clean-worktree prerequisite, not evidence of a product
  defect and not a pass.
- The source SHA after execution remained
  `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`.
- The detached worktree and main worktree had no project modifications.
- `retry_performed=false`.
- No downstream candidate/build, DARA/R3/R4, AutoCAD/FileIPC,
  persistence/reopen, visual, dimension, provider, M2, source/candidate/DXF,
  or production-code action was run.

This closes the single authorized oracle without promoting historical
run-pdf evidence across the current-main identity boundary.
