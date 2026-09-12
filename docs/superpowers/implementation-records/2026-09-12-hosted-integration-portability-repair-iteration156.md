# Hosted Integration Portability Repair — Iteration 156

Date: 2026-09-12 (Asia/Saigon)
Issue: exact-head hosted verification failures after evaluator-entry ACK repair
Base under repair: `3638e29e3c7a0068c27103e414472aca72574543`

## Trigger and first real failure

The exact-head GitHub Actions run `34679437929` failed in the existing
`offline-tests` job with three failures. The first measured Integration
boundary was the hosted verification contract, not the evaluator-entry
runtime:

1. The bundle test required the existing Release x64 plugin DLL, while the
   hosted workflow intentionally invoked `verify.ps1 -SkipAutoCADDotNet` and
   therefore did not run the build owner that produces that DLL.
2. Two startup tests compared Windows paths lexically. The hosted runner
   exposed the same temporary directory through short-name and canonical-name
   spellings (`RUNNER~1` versus `runneradmin`).

## Bounded repair

- The bundle assertion now reports `SKIP` when its existing .NET build artifact
  is absent; the full verifier remains the owner that runs it after the build.
- The two test assertions compare resolved path identity, preserving the
  production startup expression and marker-root behavior.
- The new record removes `git diff --check` trailing whitespace.
- No production runtime, public schema, transport, source/DXF/CAD/candidate,
  provider/M2, or SourceCustody HMAC/identity-key policy changed.

## Verification before hosted replay

Focused gate: `49 passed, 6 subtests`; Ruff PASS; `git diff --check` PASS.
After the bounded commit, the authoritative full gate completed successfully:
Release x64 build succeeded; C# `238 passed`; .NET IPC `134 passed`; offline
JUnit `3412` with zero failures/errors; causal RED `1` expected failure;
real-data `2 SKIP`; AutoCAD `17 SKIP`; live/M2 `NOT RUN`.

```text
STATE=OFFLINE_GREEN_HOSTED_REPLAY_PENDING
MATERIAL_FINDING=HOSTED_INTEGRATION_CONTRACT_REPAIRED_WITHOUT_PRODUCTION_CHANGE
FIRST_UNSATISFIED_BOUNDARY=EXACT_HEAD_HOSTED_VERIFICATION_TERMINAL_PASS
NEXT_SINGLE_BOUNDED_ACTION=Push the clean bounded commit and inspect the exact-head hosted verification check; restart #392 on the resulting exact HEAD
HUMAN_GATE=NO
```
