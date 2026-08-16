# CAD Agent Status

> [!IMPORTANT]
> **Routing index — not live project state.**
>
> Mutable project state is owned by GitHub, not by this document. Do **not** use
> `docs/STATUS.md` to decide current `main`, active owner/baton, blockers, merge
> readiness, live authority, or next action.
>
> For any current-state decision, fresh-read in this order:
> 1. Issue [#131](https://github.com/duongchi90/cad-agent/issues/131) and the newest applicable authority/control comment;
> 2. actual current `main`;
> 3. open PR heads/synthetics and their current CI/reuse/reviewer state;
> 4. the newest task-specific evidence/authority comments.
>
> Newer GitHub evidence always supersedes historical wording in repository docs.
> This file is not a scheduler, currentness store, merge authority, or live-action
> authority.

## Historical evidence ledger

The former status ledger is preserved byte-for-byte in
[`docs/STATUS_HISTORY.md`](STATUS_HISTORY.md). It contains SHA-bound evidence
snapshots from the epochs in which they were recorded.

Terms in that ledger such as `current`, `locked`, `next`, `before merge`,
`Executing`, `PASS`, `FAIL`, `SKIP`, and `NOT RUN` are scoped to their recorded
section/epoch unless newer GitHub evidence explicitly re-validates them. Do not
rewrite old snapshots merely to make them look current; preserve them as audit
history.

## Stable status vocabulary

- **Verified:** the named command ran successfully on the named commit and environment.
- **Partially verified:** deterministic coverage passed, but a required gate did not run on the same candidate.
- **Unverified:** no reproducible evidence supports the named claim.
- **NOT RUN:** the gate was intentionally not executed; this is never a pass.
- **SKIP:** an unavailable-state or intentionally skipped probe; this is not acceptance evidence unless a controlling contract explicitly says otherwise.
