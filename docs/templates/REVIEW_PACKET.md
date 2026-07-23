# Review Packet

- **Task ID:** required identifier
- **Reviewer role:** requirements/architecture, correctness/test, or security/operations
- **Base SHA:** required 40-character commit
- **Head SHA:** required 40-character commit
- **Diff scope:** required paths or attached patch
- **Canonical context:** required inline excerpts or uploaded files
- **Evidence delivery:** self-contained packet plus uploaded attachments; local-only paths are invalid

## Acceptance criteria

Copy the approved criteria without rewriting them.

## Test evidence

Provide exact command, exit code, environment, pass/fail/skip/warning counts,
and inline output or an uploaded artifact.

## Attachment manifest

For every uploaded file, record its file name, purpose, byte count, and SHA-256.
If no attachment is required, state `None` and inline all evidence.

## Known not-run gates

List each gate and why it did not run. An empty list must say `None`.

## Requested output

Use one repeatable `REVIEW_FINDING.md` block per finding inside a single reviewer
report; do not provide a numeric score.
