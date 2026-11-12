# Native dimension approved-value consumer repair

> Execute inline with `superpowers:executing-plans`; no subagents.

Status: executing; material review and merge remain pending.

Base SHA: `c5739dad9511ba538481f5fce57a364b8de17d8b`.

Authorization date: 2026-10-07. Human autonomous scope permits the smallest
existing-owner repair after a reachable causal RED. Canonical discriminator:
[#488 comment6040810185](https://github.com/duongchi90/cad-agent/issues/488#issuecomment-6040810185).

## Goal and scope

The packaged `mechanical-review` caller must reject a native measurement that
contradicts its existing exact `approved_value_mm`, even when it matches the
builder's recorded measurement or has a numeric display override. Reuse
`mcp_integration_lib.reviewer2`'s existing dimension check and numeric comparison.
An absent or null approved value retains the legacy/reference/display-only path. The exact source comparison uses absolute tolerance; existing geometry comparison defaults stay unchanged.
Do not change extraction, solving, schemas, transports, or non-XY measurement.

## Execution ledger

- [x] Bind current main and caller: CLI -> hash-bound evidence -> `review_live`
  -> `review_dxf_live` -> report and exit decision. Substitute only native transport.
- [x] Validate synthetic IR and build real DXFs. Exact79/native80/display79
  wrongly passes this caller while existing headless truth guard rejects it.
- [x] Run baseline: `python -m pytest mcp_integration_lib/tests/test_phase4.py -q`:
  36 passed.
- [x] Add caller regression first: `python -m pytest
  tests/test_cad_agent_live_dimension_guard.py -q`: 2 failures, 2 passes. The two
  exact mismatches returned exit0 instead of exit1; controls passed.
- [x] Add the six-line approved-value check in the existing dimension loop.
- [x] Focused GREEN: new caller tests plus `test_phase4.py`: 40 passed; changed
  Python surfaces pass Ruff.
- [x] Commit bounded changes at `4cf7966`; authoritative verifier found test-owner architecture violations (3415 other tests passed).
- [x] Move native transport tests into `mcp_integration_lib/tests/` and DXF fixture work into existing `dxf_builder_lib/tests/dxf_test_support.py`; preserve architecture rules. 46 focused/architecture tests pass, Ruff passes.
- [x] Corrected clean head `b513432`: authoritative verifier PASS; 3416 Python tests plus 74 subtests, 128 IPC tests and 261 .NET tests. Specialized unavailable probes remain skipped; no live PASS inferred.
- [x] Native consumer controls through actual FileIPC with existing exact-root COM trigger callbacks: wrong exact rejected, correct exact/display-only retained. Default Windows receiver remains blocked by `WINDOW_RECEIVER_AMBIGUOUS`, not PASS.
- [x] Self-review found inherited relative tolerance accepts a large exact mismatch. Add legal large-value caller regression: 1 expected RED. Restrict only approved-value comparison to absolute tolerance; 47 focused/architecture tests and Ruff pass.
- [ ] Verify the final absolute-tolerance head; rerun native callbacks and publish material review packet.
- [ ] Bind hosted checks and independent Security Redteam + Integration CI to
  exact BASE/HEAD. Do not merge while required material clearance is pending.

## Evidence limits and review focus

Native transport in the causal discriminator is the existing test client;
neither reviewer nor acceptance verdict is mocked. This is a staged caller RED,
not a live AutoCAD result. Record live/specialized gates separately, including
NOT RUN and skipped states. Preserve frozen source experiments and evaluator
isolation. Source-approved mismatch, correct exact measurement, legacy null
authority and numeric display overrides are the principal regression controls.
