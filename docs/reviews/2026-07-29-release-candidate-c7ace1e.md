# Release Candidate Record: c7ace1e

## Candidate

- Implementation head: `c7ace1e165f20fdd01ae5ac36599990b9faa3c88`.
- Target: Windows, Python 3.11.9, AutoCAD Mechanical 2027,
  Tesseract 5.4.0.20240606.
- Scope: reviewable paper-layout/primary-linework pipeline, hash-bound
  review-only fidelity extensions, and disposable live File IPC smoke tests.

## Verification

### Offline gate

`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1`
passed with `387 passed, 8 deselected`. Lock/environment, Ruff, whitespace,
and side-effect checks passed. The real-data probe recorded two unavailable
skips and the AutoCAD probe recorded six unavailable skips when run without
live environment variables.

### Live AutoCAD Mechanical gate

With `CAD_AGENT_FILE_IPC=1`, the active AutoCAD Mechanical 2027 window, and
the local `mcp_dispatch.lsp` loaded:

```text
python -m pytest -m autocad_mechanical -ra -p no:cacheprovider
6 passed, 389 deselected in 143.68s
```

The smoke suite used only disposable DXFs below `C:\temp`. Each test closes
its temporary drawing without saving, so the gate does not mutate the drawing
that the operator had open before the run.

## Fidelity safety

The hatch slice adds stable diagonal-stroke observations, explicit polygon
approval, SHA-256 binding to the observation and base DXF, native ANSI31
`HATCH` output on `FIDELITY_HATCH`, and a `needs_review` audit report. The
dimension, table-text, linetype, and OCR paths have the same review-only
boundary. None of these candidates can enter the ordinary Mechanical
production review/repair flow.

## Limits

- No private PDF rerun was performed on this head because the approved PDF is
  outside the repository and was not present in the current environment.
- OCR/font correction, model export, and production drawing repair remain
  unperformed and require their own explicit approval and evidence.
