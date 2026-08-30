# M2 Loaded-Plugin Binary Identity Design

**Approval date:** 2026-08-30

**Supported scope:** AutoCAD Mechanical 2027, the existing C# `health` IPC
owner, and the M2 opt-in live harness. The Human Owner's current M2 execution
instruction is the approval source for this bounded security hardening.

## Goal

Make the health response prove the binary that is actually loaded for the
executing `OperationDispatcher`, so M2 can compare that identity with the exact
Release DLL it expects and fail closed on missing, spoofed, or stale identity.

## Design

`OperationDispatcher.DispatchHealth` passes
`typeof(OperationDispatcher).Assembly` to one internal identity helper. The
helper obtains the assembly's own non-empty absolute `Location`, opens that file
read-only, computes SHA-256 from its bytes, and returns the normalized path and
lowercase hash. The health payload adds `plugin_binary_path` and
`plugin_binary_sha256` while retaining `plugin_version`.

The helper accepts no request value, expected hash, configured path, or caller
session label. A missing/empty assembly location, missing file, or unreadable
file raises an error; the existing dispatcher error boundary returns a failed
health result. The Python M2 harness remains responsible for comparing the
reported hash to its exact current build artifact and rejecting a stale
expected hash.

## Safety and compatibility

- The change is read-only and does not load, unload, replace, or mutate a DLL.
- Existing C# transport, request, result, and AutoCAD document behavior is
  unchanged except that health now fails closed when its own binary identity
  cannot be measured.
- No benchmark store, telemetry, second transport, or CAD truth owner is added.
- Tests cover actual assembly identity, missing identity, caller-supplied hash
  non-authority, and deterministic hash formatting. Existing Python M2 tests
  cover expected-hash mismatch and stale identity rejection.

## Verification and live boundary

Run the focused C# tests, focused M2 Python tests, Ruff, and the authoritative
offline verifier. If the normal Release output is locked by the active AutoCAD
process, build/test with an isolated output path; never kill AutoCAD or
overwrite its loaded DLL. Live M2 remains blocked until the operator-approved
NETLOAD/session state is available and the health response proves this hash.
