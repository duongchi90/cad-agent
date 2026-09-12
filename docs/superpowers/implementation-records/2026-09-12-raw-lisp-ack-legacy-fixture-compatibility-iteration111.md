# Raw-LISP ACK Legacy-Fixture Compatibility — Iteration 111

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 candidate activation / raw-LISP delivery boundary  
Reviewed executor HEAD before this record: `8499ee3b349d3ba031c39ae53d9ec382f76c3fbd`

## Finding from authoritative verification

The first full `scripts/verify.ps1` run after iteration 110 failed six
existing `test_phase4.py` fixture tests before the independent active-document
boundary could be reached. Those fixtures intentionally provide an unclaimed
trigger; the existing constructor therefore sets `legacy_fixture_mode=True`.
The actual live CLI path uses `make_windows_dispatch_trigger`, which marks its
trigger claim-bound.

The failure was a fixture-compatibility regression, not evidence against the
ACK seam. It was resolved inside the existing raw-LISP opening owner by using
the existing mode distinction:

- claimed/live path: same-expression exact receiver/evaluation ACK remains
  mandatory;
- legacy fixture path: the prior enqueue-only raw-LISP call remains available
  so old offline fixtures can continue to characterize active-document and
  dispatcher behavior without fabricating a marker.

No second transport, managed open/activate subsystem, C# change, live call,
candidate activation, source/DXF/CAD mutation, or custody-policy change was
added.

## Focused evidence after compatibility repair

- New ACK tests: `4 passed`.
- Opening regression: `44 passed`, `6` subtests.
- Previously failing phase-4 fixtures: `6 passed`, `30` deselected.
- Windows-trigger non-causal-red regression: `19 passed`, `3` subtests.
- The intentional Windows causal-red remains unchanged and is still expected
  to show that enqueue `TRUE` is not receiver consumption.

The next bounded action is a fresh clean-tree full verification. Live
acceptance remains explicitly stopped until offline verification and a fresh
SOL review are complete.

## Canonical checkpoint

```text
STATE=IMPLEMENTED
EVIDENCE=This record; fresh focused ACK/opening 44 passed; phase-4 compatibility 6 passed; Windows-trigger non-causal-red 19 passed; iteration-110 full verify exposed exactly six legacy-fixture failures
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=AUTHORITATIVE_FULL_VERIFY_AFTER_LEGACY_FIXTURE_COMPATIBILITY_REPAIR
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of the legacy_fixture_mode compatibility repair, then rerun clean-tree scripts/verify.ps1; no live acceptance epoch yet
HUMAN_GATE=NO
```

