# Review Packet

- **Task ID:** required identifier
- **Reviewer role:** `SECURITY_REDTEAM` or `INTEGRATION_CI` for mandatory Codex reviews
- **Request ID / controlling attempt ID:** unique to this role and packet
- **Current main SHA:** required current commit
- **Base SHA:** required 40-character commit
- **Head SHA:** required 40-character commit
- **Tree SHA:** required exact tree for the head
- **Diff scope:** required paths or attached patch
- **Canonical context:** required inline excerpts or uploaded files
- **Evidence delivery:** self-contained packet plus uploaded attachments; local-only paths are invalid

## Acceptance criteria

Copy the approved criteria without rewriting them.

## Test evidence

Provide exact command, exit code, environment, pass/fail/skip/warning counts,
and inline output or an uploaded artifact.

## Attachment manifest

Use one immutable evidence manifest per exact HEAD and share that same manifest with both reviewers. For every uploaded file, record its file name, purpose, byte count, and SHA-256. Include current main/base/head/tree, changed paths and blob SHAs, focused/canonical verification receipts, required hosted checks, applicable V7/native evidence, limitations, and NOT_RUN. Do not copy one reviewer's conclusions into the other role's packet.
If no attachment is required, state `None` and inline all evidence.

## Independence and V7

Each reviewer uses a fresh context, independently reads the bound source/evidence, and freezes its initial role-specific verdict before seeing the other reviewer's findings. Verify effective model and effort from runtime evidence; a mismatch or missing record is `NOT_VERIFIED`. On HEAD/base/main change, mark the affected verdict stale. No self-approval, reviewer production/native mutation, or automatic merge.

When applicable, preserve #392 V7: `INTEGRATION_CI` owns its independent Pass A/Pass B double pass, deriving both required sections in each pass from the same exact identity, freezing A before B and comparing only after both reviewer roles are frozen. V7 remains an independently required double-pass condition; record its own exact-head receipt. Neither role receipt alone waives V7.

## Known not-run gates

List each gate and why it did not run. An empty list must say `None`.

## Requested output

Use one repeatable `REVIEW_FINDING.md` block per finding inside a single reviewer
report; do not provide a numeric score.
