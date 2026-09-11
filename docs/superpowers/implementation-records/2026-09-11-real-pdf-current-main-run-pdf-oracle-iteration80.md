# Current-Main Real-PDF `run-pdf` Oracle — Iteration 80

Date: 2026-09-11 (Asia/Saigon)
Canonical main SHA: `e8fc0092ee46750e50de0ea408fd91811cae10c2`
Executor branch: `codex/audit-text-style-compat-20260910`

## Authority and exact scope

SOL's iteration-79 decision was:

```text
VERDICT=CLEAR_CONTINUE
NEXT_SINGLE_BOUNDED_ACTION=Run exactly one fresh current-main run-pdf oracle
using the now-proven .venv-py311 interpreter, approved source SHA,
calibration, DPI, and scale; record the manifest and all stage states.
Stop at this gate whether PASS or FAIL.
HUMAN_GATE=NO
```

The exact identity was pre-bound in
`C:/temp/cad-agent-real-pdf-current-main-iter80-run/oracle-context.json`:

- clean detached worktree:
  `C:/temp/cad-agent-real-pdf-current-main-iter78`;
- worktree HEAD:
  `e8fc0092ee46750e50de0ea408fd91811cae10c2`;
- worktree status before and after: clean;
- source: `202607092308.pdf`;
- source SHA-256:
  `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`;
- calibration approval: `STATUS-e48f3970-144dpi-1to40`;
- DPI: `144`;
- scale: `7.055555555556` mm/px;
- repository lock SHA-256:
  `d4739cc0c3b523ab11069178680f534fa436e4e64e30e07c30d1f07e652d784d`;
- interpreter:
  `C:/temp/cad-agent-real-pdf-current-main-iter78/.venv-py311/Scripts/python.exe`;
- isolated output root:
  `C:/temp/cad-agent-real-pdf-current-main-iter80-run`.

The one command was:

```powershell
C:/temp/cad-agent-real-pdf-current-main-iter78/.venv-py311/Scripts/python.exe -m cad_agent run-pdf `
  --input C:/Users/dkv/Downloads/202607092308.pdf `
  --output-dir C:/temp/cad-agent-real-pdf-current-main-iter80-run/staged `
  --scale-mm-per-px 7.055555555556 `
  --calibration-approval STATUS-e48f3970-144dpi-1to40 `
  --dpi 144
```

## Result

The existing `run-pdf` manifest/stage contract completed for all 9 pages.
The manifest is:

`C:/temp/cad-agent-real-pdf-current-main-iter80-run/staged/pdf-run-manifest.json`

Manifest SHA-256:

`f7c7b1afbd52f8f504dafbcb9b6efb416ee332b88260a01aea2414ab9d650eaf`

Fresh current-main stage evidence:

- `render.state=completed`;
- rendered PNG: `9/9` completed;
- Primitive IR: `9/9` completed;
- Semantic IR: `9/9` completed;
- staged DXF: `9/9` completed;
- SHA-bound build evidence: `9/9` completed;
- source hash in the manifest matches the approved source hash;
- the source hash after execution remained unchanged.

The manifest remains `release_profile=DRAFT_REFERENCE` and
`authoritative_release_eligible=false`. This is current-main `run-pdf` stage
evidence, not release approval.

## Bounded disposition

- `SOURCE_SHA_BOUND_RUN_PDF_MANIFEST_STAGE_ON_CURRENT_MAIN=PROVEN_CURRENT`.
- The one authorized oracle is closed. No candidate/build consumption beyond
  the existing `run-pdf` stage, DARA/R3/R4, AutoCAD/FileIPC,
  persistence/reopen, visual, dimension, provider, M2, source/candidate/DXF,
  or production-code action was performed.
- No retry was performed. No repository code, source bytes, candidate, DXF, or
  historical evidence was changed.
- Candidate/build acceptance outside the `run-pdf` manifest, DARA/R3/R4,
  setup/readback, persistence/reopen, visual, and dimension gates remain
  `NOT_PROVEN` and require a fresh SOL decision.
