# CAD Agent Status

## Status vocabulary

- **Verified:** the named command ran successfully on the named commit and
  environment.
- **Partially verified:** deterministic coverage passed, but a required private
  data or AutoCAD LT gate has not run on the same candidate.
- **Unverified:** no current reproducible evidence supports the claim.
- **NOT RUN:** the gate was intentionally not executed; this is never a pass.

## Supported release environment

- Windows
- Python 3.11
- AutoCAD LT
- Tesseract 5.4.0.20240606

## Authoritative verification

After bootstrap, run `.\scripts\verify.ps1`. It runs the offline gate and
collects unavailable-state probes for `real_data` and `autocad_lt` as explicit
`SKIP` results with prerequisites removed. A real private-data or live AutoCAD
LT gate that was not separately executed remains `NOT RUN`.

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
| Primitive IR | Partially verified | Final Python 3.11 offline gate passed with zero skips; approved private `real_data` execution was NOT RUN and its unavailable-state probe was SKIP. |
| Semantic IR | Verified | Final Python 3.11 offline gate passed with `python-solvespace` installed and zero offline skips. |
| DXF build/review/repair | Verified | Final Python 3.11 offline DXF tests passed; production AutoCAD LT mutation is outside this state. |
| MCP/File IPC | Partially verified | Offline/fake IPC tests passed; live `autocad_lt` execution was NOT RUN and its unavailable-state probe was SKIP. |
| Agent advice/audit | Partially verified | Offline tests passed; `run_agent()` is non-mutating, but the current run/demo entry points auto-apply reports and are not approved production mutation paths. |
| Reproducible foundation | Verified | See the Foundation certificate and `docs/reviews/2026-07-22-reproducible-foundation.md`. |

## Known production gates

- Calibration may be auto-accepted only with at least two independent
  candidates and median relative error at most 3 percent. Current production
  callers must opt into consensus and retain human approval for unverified
  scale.
- Private drawing benchmarks remain outside Git and are addressed by SHA-256.
- AutoCAD LT mutation requires backup, human approval, live review, repair, and
  a second review.

## Next slice

After the foundation is certified, design and implement the thin `cad_agent`
vertical-slice CLI with manifests, checkpoints, approval gates, and resumability.

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
