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
| Primitive IR | Partially verified | Offline tests passed in the pre-foundation baseline. The approved private real-image gate was NOT RUN. |
| Semantic IR | Partially verified | Offline logic passed; solver-dependent coverage was skipped in the pre-foundation environment. |
| DXF build/review/repair | Verified | `ezdxf`-backed offline tests passed in the pre-foundation baseline. |
| MCP/File IPC | Partially verified | Fake/offline MCP tests passed. AutoCAD LT live smoke was NOT RUN on the current candidate. |
| Agent advice/audit | Partially verified | Offline agent tests passed; `run_agent()` is non-mutating, but current run/demo entry points auto-apply reports without a human approval prompt and are not approved production mutation paths. |
| Reproducible foundation | Unverified | Certification requires `scripts/verify.ps1` on the completed foundation head using Windows/Python 3.11. |

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
