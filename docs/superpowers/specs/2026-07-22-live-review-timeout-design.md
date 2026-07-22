# Dense Live-Review Timeout Design

**Status:** Approved by the user's optimization request on 2026-07-22

## Evidence

The staged page 5 DXF from the approved private PDF has 485 live-reviewable
entities. The existing `mechanical-review` client uses a fixed 10-second File
IPC timeout, which expires during `entity:list` on this dense drawing. The
same read-only review passes with a 60-second transport timeout: 485 structural
and 485 geometry checks, with no mismatch or warning.

## Design

- Add an explicit positive `--timeout-s` option to `mechanical-review` and
  `mechanical-repair`, defaulting to the present 10 seconds.
- Pass the selected timeout only to the File IPC client; do not change review,
  repair, DXF, or save behavior.
- Reject zero or negative values before a live command is sent.

## Acceptance criteria

1. Default behavior remains 10 seconds.
2. A supplied timeout reaches the File IPC client exactly.
3. A dense staged drawing can be reviewed through the standard CLI with an
   explicitly selected timeout, without any repair or save.
