# Design and Implementation Records

Files under `specs/` and `plans/` record approved intent at a point in time.
They do not replace the current ledger in `docs/STATUS.md`.

## Historical plans

Plans created before this foundation may contain unchecked boxes even when Git
history shows that some or all work shipped. Unchecked boxes are not status evidence.
Do not infer completion and do not bulk-check historical boxes without fresh command
and commit evidence.

## New record requirements

Every new design records approval date and supported scope. Every new
implementation plan records:

- Status: planned, executing, completed, or superseded
- Base SHA
- Completion Head SHA when completed
- Exact verification command and result
- Required private/live gates and whether each passed, skipped, or was not run

`Completion Head SHA` means the final implementation/evidence commit immediately
before a plan-only lifecycle-closing commit. This avoids asking a commit to
contain its own SHA.

When implementation completes, add the evidence to `docs/STATUS.md`; retain the
plan as the execution record.
