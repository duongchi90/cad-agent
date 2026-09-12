# Raw-LISP Consumption ACK Implementation — Iteration 110

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 candidate activation / raw-LISP delivery boundary  
Reviewed executor HEAD before this record: `b9ca10b9f5496a4f16bbe886087492e1d1746c1a`

## Authorization and scope

Fresh SOL review returned `VERDICT=CLEAR_CONTINUE` and accepted the
iteration-109 design for one bounded TDD implementation mission. The exact
production write set remained `mcp_integration_lib/mcp_client.py`; focused
opening tests and evidence/docs were also allowed. No live AutoCAD epoch,
candidate activation, health/FileIPC call, source/DXF/CAD mutation, managed
dispatcher/schema change, or custody-policy change was authorized.

## Implementation

- Added a private `_send_raw_lisp_with_ack` seam inside the existing
  `FileIPCLiveMCPClient` raw-LISP owner.
- The seam allocates one UUID-owned marker path under the validated IPC root,
  appends the existing fixed-token marker writer as the final form of the same
  owner-built `progn`, sends exactly once through the existing raw-LISP
  trigger, and accepts receiver/evaluation only after exact token/path
  readback within the existing timeout.
- Marker cleanup runs on success, timeout, trigger error, and other terminal
  paths while the IPC root remains safe. Missing or wrong marker is
  `RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED`; it cannot fall through to
  the existing command fallback retry.
- `drawing_open` keeps active-document identity and managed dispatcher checks
  independent from the receiver/evaluation ACK. The low-level Windows trigger
  remains enqueue-only and its return contract is unchanged.

## TDD and focused evidence

- RED before production change: four new opening ACK tests failed because the
  old owner returned success without a receiver marker.
- GREEN: focused ACK tests passed `4/4`; opening regression passed `44/44`
  with `6` subtests; Windows-trigger regression passed `19/19` excluding the
  intentional causal-red test, with `3` subtests.
- The intentional causal-red remains expected: `PostMessageW=TRUE` with no
  handler consumption still fails its negative oracle (`1 failed, 19
  passed` when included), proving enqueue is not receiver ACK.
- Ruff passed for the changed production/test files and `git diff --check`
  passed.
- Full authoritative `scripts/verify.ps1` is the next bounded gate and has
  not yet run for this implementation.

## Canonical checkpoint

```text
STATE=IMPLEMENTED
EVIDENCE=This record; focused ACK/opening tests 44 passed; Windows-trigger regression 19 passed excluding intentional causal-red; ruff passed; git diff --check passed
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=AUTHORITATIVE_FULL_VERIFY_AFTER_ACK_IMPLEMENTATION
NEXT_SINGLE_BOUNDED_ACTION=Run clean-tree scripts/verify.ps1; stop after offline verification and do not run the live acceptance epoch yet
HUMAN_GATE=NO
```

