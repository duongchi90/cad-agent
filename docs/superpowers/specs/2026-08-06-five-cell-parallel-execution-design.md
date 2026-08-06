# Five-Cell Parallel Execution Design

## Status

- Governance/design only.
- Exact base: `d71d0c97e28e03cb430f05589c8381b4ede70e66`.
- Coordinator Issue: #74.
- No runtime scope is opened by this document.

## Goal

Increase delivery speed by running five isolated ChatGPT/Codex work cells concurrently while retaining one authoritative Product Owner, one writer per overlapping file set, exact-base traceability, and independent acceptance.

## Selected approach

Use **one Master PO plus five execution cells**.

The Master PO owns cross-cell scope, dependency order, acceptance, merge order, and `main`. Each cell may act as a local PO/coder for its own approved Issue: it may inspect, design, plan, implement, test, and locally review within its exact branch and allowlist. A cell may not approve or merge its own work.

Rejected alternatives:

1. Five equal POs: rejected because scope, ownership, and acceptance can diverge.
2. Five coders with all review serialized: safe but leaves research and review capacity idle.
3. Shared branch parallelism: rejected because it destroys one-writer traceability and increases conflict risk.

## Authority model

### Project owner

- Supplies private inputs, AutoCAD access, fixtures, and production-use approval.
- Resolves unresolved engineering intent.

### Master PO

- Creates or amends Issues, exact bases, branches, and allowlists.
- Owns dependency graph, merge order, final acceptance, and `main` integration.
- Reviews exact final heads and hosted evidence.
- May stop or reassign any cell.
- Does not turn `SKIP` or `NOT RUN` into `PASS`.

### Execution cell

- Operates only on one assigned Issue or read-only review domain.
- May design, plan, code, test, and perform local review in that scope.
- Must use GitHub commit/diff/CI/evidence as authority.
- Must stop before acceptance or merge.

## Initial cell allocation

### Cell 1 — Wave 1A writer

- Issue: #70.
- Branch: `planning/w1a-official-vision-codex-worker`.
- Write authority: only the two #70 planning documents.
- Deliverable: design, plan, draft PR, verification report.

### Cell 2 — Wave 1B writer

- Issue: #71.
- Branch: `planning/w1b-r1c-source-integrity-fusion`.
- Write authority: only the two #71 planning documents.
- Deliverable: design, plan, draft PR, verification report.

### Cell 3 — Wave 1C live operator

- Issue: #72.
- Repository write authority: none.
- Deliverable: prerequisite inventory and truthful S2C/S3B live evidence packet.

### Cell 4 — Wave 1A official-interface research/red-team

- Read-only repository access.
- Writes only GitHub Issue/PR comments or a Master-PO-approved research attachment.
- Audits official Codex SDK, App Server, and CLI fallback claims.
- Reviews Cell 1 for gaps, unsafe authority, unsupported capabilities, and dependency risks.

### Cell 5 — Wave 1B reuse/source-integrity research/red-team

- Read-only repository access.
- Writes only GitHub Issue/PR comments or a Master-PO-approved research attachment.
- Audits internal source-identity utilities and external reusable components.
- Reviews Cell 2 for duplicate truth stores, hidden mutation, nondeterminism, and licensing risks.

## One-writer matrix

| Domain | Writer | Reviewers | Forbidden writers |
|---|---|---|---|
| #70 planning files | Cell 1 | Cell 4, Master PO | Cells 2, 3, 5 |
| #71 planning files | Cell 2 | Cell 5, Master PO | Cells 1, 3, 4 |
| #72 live evidence | Cell 3/operator | Master PO | Cells 1, 2, 4, 5 |
| Official-interface research | none in repository | Cell 4 | all repository writers |
| Source-integrity research | none in repository | Cell 5 | all repository writers |
| `STATUS.md`, `HANDOFF.md`, roadmap | Master PO-authorized integration task only | Master PO | all five cells by default |
| `main` merge | Master PO | hosted CI | all cells |

## Isolation rules

- Every writer cell uses its own branch and worktree.
- Branches start from the exact base named in the Issue.
- No cell merges `main` into its branch, rebases, squashes, amends reviewed commits, or force-pushes without a PO amendment.
- Research cells do not push to writer branches.
- Shared canonical documents are not edited by execution cells unless explicitly allowlisted.
- A stale branch is handled by a new PO-authorized exact-base task, not silent rebasing.

## Prompt contract

Each cell prompt must be self-contained and include:

- repository and Issue;
- exact base and branch or explicit no-branch state;
- current authorization;
- exact create/modify/do-not-modify lists;
- required documents and skills;
- reuse-first requirements;
- commands and evidence expected;
- stop conditions;
- completion-report schema;
- explicit statement that chat memory is not authority.

## Cross-review flow

1. Writer opens a draft PR.
2. Paired red-team cell reviews read-only and posts findings.
3. Writer addresses valid findings with bounded follow-up commits.
4. Paired red-team rechecks only its review domain.
5. Master PO audits the entire exact head, diff, CI, and issue compliance.
6. Only Master PO accepts and merges.

A red-team cell may recommend `PASS`, `CHANGES REQUIRED`, or `BLOCKED` for its domain, but this is advisory and not final acceptance.

## Evidence and completion report

Every writer cell reports:

- Issue, PR, branch, exact base, starting and final heads;
- bounded commit list;
- exact changed-file list;
- focused and canonical verification results;
- hosted checks and synthetic merge SHA;
- retained `SKIP`/`NOT RUN` gates;
- worktree state;
- blockers and external assumptions.

The live operator reports:

- environment/prerequisite inventory;
- exact operations;
- pre/post identities and hashes;
- artifacts and cleanup;
- independent S2C and S3B states;
- confirmation of no repository or source/accepted-CAD mutation.

Research cells report:

- inspected internal owners and external sources;
- exact versions/revisions and licenses;
- capability or reuse matrix;
- risks and unsupported claims;
- classification and recommendation;
- concrete review findings tied to design sections or PR lines.

## Conflict and stop conditions

A cell stops when:

- another cell has touched its write-set;
- exact base, branch, or ancestry is wrong;
- an allowlist expansion is required;
- two authorities or stores would be created;
- licensing, pinning, or reproducibility is unclear;
- private/source/accepted CAD could be modified without authorization;
- a required live prerequisite is missing;
- hosted or canonical verification fails;
- the cell would need to approve or merge its own work.

The cell posts the blocker and waits for Master PO disposition.

## Merge order

- #70 and #71 planning PRs are independent and may be reviewed concurrently.
- Either may merge first if its exact-head gates pass.
- The second PR is not silently rebased; Master PO decides whether it remains conflict-free or needs a bounded rebaseline.
- #72 evidence does not merge and may complete independently.
- Runtime Issues are created only after the related planning PR is accepted.

## Post-planning reassignment

After #70 merges:

- Cell 1 becomes Wave 1A runtime writer.
- Cell 4 becomes Wave 1A test/security/red-team reviewer.

After #71 merges:

- Cell 2 becomes R1C runtime writer.
- Cell 5 becomes R1C determinism/provenance reviewer.

Cell 3 remains live operator and may validate disposable runtime slices when separately authorized.

## Acceptance criteria

- Five cells have explicit, non-overlapping write authority.
- One Master PO remains the only final acceptance and merge authority.
- Existing Wave 1 locks and exact bases are preserved.
- Research and live preparation run concurrently without production-code writes.
- Each cell has a self-contained prompt and completion report.
- No runtime capability is promoted by this governance design.
