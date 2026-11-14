# CAD Agent Accepted Product Baseline

## Durable acceptance anchor

The authorized cumulative BVTL product run is complete and accepted in
[#461](https://github.com/duongchi90/cad-agent/issues/461#issuecomment-5915471764).
Phase-4 evidence remains in [#409](https://github.com/duongchi90/cad-agent/issues/409),
Phase-5 in [#459](https://github.com/duongchi90/cad-agent/issues/459), and remaining-page
coverage in [#460](https://github.com/duongchi90/cad-agent/issues/460).

This file routes durable acceptance. It does not cache current main, PR/CI state,
runtime PID/HWND, a mutable frontier, or the next execution instruction. Fresh-read
GitHub before material conclusions. Current product: `docs/PROJECT.md`; current
owners: `docs/ARCHITECTURE.md`; authority: latest #305/#429. No Phase 6 is implied.

## Accepted identities and preservation

| Role | SHA-256 |
| --- | --- |
| Modified source PDF | `13d822cf828cccc6cd21b19ec3c410f0ea89aef440aeca4c96248e86c08b5b38` |
| ORIGINAL native BASE | `74f2367e0b74314c3f48c955da2bd2e25dcbcb7e2522e9de92ae3e6dfdd7b5cd` |
| Final cumulative accepted DWG | `4c7cb7cbfb67b669cd0577ffd575f6059ca486963fc322c41913e4f1621f4233` |

The decision-grade packet is at the workstation evidence root
`D:\Cad agent temp\solo-cumulative-product-20260930`. Its `product-acceptance.json`,
`inputs-bound.json`, frozen plan/source-correction/annotation scope, native and
persisted readbacks, protected-state comparison, visual region evidence,
`evidence-manifest.json` and sidecar, and `protected-prior-artifacts.json` must be
preserved together. Source/BASE and earlier accepted phase/coverage candidates
remain protected at their bound original paths. Historical candidates are evidence,
never generation authority or substitutes for the final cumulative result.

#461 accepts eight source-supported modifications on the same ORIGINAL-BASE
candidate, with saved/reopened native readback, editability, protected invariants,
applicable geometry/visual/dimension evidence, and deterministic verification.
Acceptance is scoped to that run. It does not establish universal drawing support,
paid-provider readiness, or PASS for every optional runtime route.

## Supported release environment and verification

- Windows
- Python 3.11
- AutoCAD Mechanical 2027
- Tesseract 5.4.0.20240606

`.\scripts\verify.ps1` remains the authoritative local gate; see `docs/QUALITY.md`.
Hosted/offline success is separate from actual private `real_data` and native
`autocad_mechanical` acceptance. Missing prerequisites are `SKIP` or `NOT RUN`.
This documentation consolidation does not rerun live CAD or reinterpret old skips.

## Unmerged CASE02 observation-root implementation evidence

Local candidate commit `25ed38ab77b93eb0912ebb8370526e154139311e`, based on main
`abfb60ea7d9cf2012e0ea30b68b9fef8b5fb0512`, adds a closed, typed
`INITIAL_PDFIMPORT_OBSERVATION_ROOT` digest helper in the existing visual-evidence
owner. It binds supplied source-PDF, import-script, completed-receipt, candidate
path, and DWG SHA-256 identities. The helper validates packet shape only; it does
not verify artifact bytes, receipt authenticity/completion, native custody, path
aliases, current file identity, mutation, or product acceptance. This is an
unmerged local implementation candidate, not canonical main status or CASE02
native acceptance.

Focused observation-root and legacy external-root tests passed (12); Ruff and
`git diff --check` passed. The authoritative verifier passed on this commit using
the existing Python 3.11 environment: .NET 261/261, offline IPC 128/128, Python
3,743 passed / 24 deselected / 86 subtests. Its expected causal-RED negative
oracle returned the intended failing assertion and the verifier classified that
oracle correctly. The B041 real-data test separately passed once with the
approved PDF whose SHA-256 matched the test constant; the verifier's own B041
probe remained SKIP because the environment variable was not inherited by that
run. Other private real-data gates were SKIP. AutoCAD/live/native readback,
hosted CI, and exact-head Security/Integration review were NOT RUN.

## Historical evidence

[Prior STATUS snapshot](history/status-before-bvtl-consolidation.md) preserves the
complete pre-consolidation certificates, diagnostic states, counts, SHAs, and
limitations unchanged. Its old "executing", "NOT RUN", cached frontier, and
current-main claims describe their recorded epochs, not today's queue or #461.
Prior `PROJECT` and `ARCHITECTURE` snapshots are in `docs/history/` as well.
Plans, handoffs, review records, and the earlier reuse inventory remain historical
evidence. Unchecked boxes are not current work. No historical record is rewritten
to manufacture a PASS, and no accepted drawing is modified by documentation cleanup.
