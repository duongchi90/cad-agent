# Five-Cell Parallel Execution Design

## Status

- Governance/design only.
- Exact base: `d71d0c97e28e03cb430f05589c8381b4ede70e66`.
- Coordinator Issue: #74.
- Coordinator PR: #75.
- No runtime scope is opened by this document.

## Goal

Increase delivery speed by running five isolated ChatGPT cells concurrently for all work that can be completed through GitHub, repository analysis, design, implementation, testing, research, and review, while assigning all machine-local AutoCAD Mechanical 2027 work to Codex Local on the project Windows machine.

The operating model retains one authoritative Master PO, one writer per overlapping file set, exact-base traceability, independent acceptance, and truthful live-evidence states.

## Selected approach

Use **one Master PO plus five ChatGPT cells plus one Codex Local operator**.

The Master PO owns cross-cell scope, dependency order, acceptance, merge order, and `main`. Each ChatGPT cell may act as a local PO/coder or reviewer only within its approved Issue and authority. Codex Local owns machine-local AutoCAD Mechanical execution under Issue #72. No cell or Codex Local may approve or merge its own work.

Rejected alternatives:

1. Five equal POs: rejected because scope, ownership, and acceptance can diverge.
2. ChatGPT as the AutoCAD live operator: rejected because it cannot directly inspect the Windows process, HWND, plugin, File IPC, local DWG files, DBMOD, or cleanup state.
3. Codex doing all repository planning and review: rejected because it leaves parallel cloud/GitHub capacity idle and weakens independent review.
4. Shared branch parallelism: rejected because it destroys one-writer traceability and increases conflict risk.

## Authority model

### Project owner

- Supplies private inputs, AutoCAD access, fixtures, and production-use approval.
- Resolves unresolved engineering intent.
- Authorizes access to any private drawing or production environment.

### Master PO

- Creates or amends Issues, exact bases, branches, and allowlists.
- Owns dependency graph, merge order, final acceptance, and `main` integration.
- Reviews exact final heads and hosted/live evidence.
- May stop or reassign any ChatGPT cell or Codex Local task.
- Does not turn `SKIP` or `NOT RUN` into `PASS`.

### ChatGPT execution cell

- Operates only on one assigned Issue or read-only review domain.
- May inspect, design, plan, implement, test, and locally review when its Issue authorizes those actions.
- Must use GitHub commit/diff/CI/evidence as authority.
- Must stop before final acceptance or merge.
- Does not claim machine-local AutoCAD evidence.

### Codex Local

- Runs on the project Windows machine.
- Owns AutoCAD Mechanical 2027 environment inspection, local .NET verification, File IPC/plugin checks, approved disposable fixture preparation, live S2C/S3B execution, and machine-local evidence collection under Issue #72.
- Has no repository write authority under Issue #72.
- May diagnose a reproducible defect, but implementation requires a separate Master-PO-authorized defect Issue, branch, allowlist, failing test, and rollback.
- Cannot approve its own live result or merge any defect fix.

## Initial ChatGPT cell allocation

### Cell 1 — Wave 1A writer/local PO

- Issue: #70.
- Current PR: #73.
- Branch: `planning/w1a-official-vision-codex-worker`.
- Write authority: only the exact #70 planning or later explicitly authorized runtime allowlist.
- Deliverable: design/plan or bounded runtime implementation, tests, draft PR, verification report.

### Cell 2 — Wave 1B writer/local PO

- Issue: #71.
- Branch: `planning/w1b-r1c-source-integrity-fusion`.
- Write authority: only the exact #71 planning or later explicitly authorized runtime allowlist.
- Deliverable: design/plan or bounded R1C implementation, tests, draft PR, verification report.

### Cell 3 — Wave 1 integration, CI, and evidence coordinator

- Issue: #79.
- Repository write authority: none by default.
- Deliverable: independent audits of exact bases/heads, changed paths, write-set overlap, hosted workflows, test counts, review state, PR-body consistency, stale-base risk, and merge-order implications.
- Does not operate AutoCAD Mechanical and does not edit writer branches.

### Cell 4 — Wave 1A official-interface research/red-team

- Issue: #76.
- Read-only repository access.
- Writes only GitHub Issue/PR comments or a Master-PO-approved research attachment.
- Audits official Codex SDK, App Server, and CLI fallback claims.
- Reviews Cell 1 for gaps, unsafe authority, unsupported capabilities, security, sandbox, lifecycle, and dependency risks.

### Cell 5 — Wave 1B reuse/source-integrity research/red-team

- Issue: #77.
- Read-only repository access.
- Writes only GitHub Issue/PR comments or a Master-PO-approved research attachment.
- Audits internal source-identity utilities and bounded external reusable components.
- Reviews Cell 2 for duplicate truth stores, hidden mutation, nondeterminism, provenance gaps, and licensing risks.

## Codex Local allocation

### AutoCAD Mechanical operator/coder assistant

- Issue: #72.
- Repository write authority: none under the live evidence Issue.
- Machine-local authority: inspect AutoCAD Mechanical 2027, process/HWND, active document, plugin, File IPC, local paths/hashes, approved disposable fixtures, live render, inspection, extraction, DBMOD, artifacts, cleanup, and immutable source/accepted CAD evidence.
- Deliverable: independent S2C and S3B `PASS`/`FAIL`/`SKIP`/`NOT RUN` evidence packet.
- A code defect is split into a fresh defect Issue before any repository edit.

## One-writer and operator matrix

| Domain | Writer/operator | Reviewers | Forbidden actors |
|---|---|---|---|
| #70 planning/runtime allowlist | ChatGPT Cell 1 | Cell 4, Cell 3, Master PO | Cells 2, 5; Codex Local unless separately authorized |
| #71 planning/runtime allowlist | ChatGPT Cell 2 | Cell 5, Cell 3, Master PO | Cells 1, 4; Codex Local unless separately authorized |
| GitHub integration/CI audit | none in repository; Cell 3 comments only | Master PO | Cell 3 editing writer branches |
| #72 AutoCAD live environment/evidence | Codex Local | Cell 3 evidence consistency audit, Master PO | ChatGPT cells claiming live execution |
| Official-interface research | none in repository; Cell 4 comments only | Master PO | repository writers adding research code without Issue |
| Source-integrity research | none in repository; Cell 5 comments only | Master PO | repository writers adding research code without Issue |
| `STATUS.md`, `HANDOFF.md`, roadmap | Master-PO-authorized integration task only | Master PO | all cells and Codex Local by default |
| `main` merge | Master PO | hosted CI and required independent reviews | all cells and Codex Local |

## Isolation rules

- Every writer cell uses its own branch and worktree.
- Branches start from the exact base named in the Issue.
- No cell merges `main` into its branch, rebases, squashes, amends reviewed commits, or force-pushes without a PO amendment.
- Research and integration cells do not push to writer branches.
- Codex Local does not modify repository files under Issue #72.
- Shared canonical documents are not edited unless explicitly allowlisted.
- A stale branch is handled by a new PO-authorized exact-base task, not silent rebasing.
- Local AutoCAD paths, credentials, customer filenames, and private bytes are not copied into GitHub comments; evidence is redacted while preserving hashes and identities.

## Prompt contract

Each ChatGPT cell prompt must be self-contained and include:

- repository and Issue;
- exact base and branch or explicit no-branch state;
- current authorization;
- exact create/modify/do-not-modify lists;
- required canonical documents and skills;
- reuse-first requirements;
- verification/evidence expected;
- stop conditions;
- completion-report schema;
- explicit statement that chat memory is not authority.

The Codex Local prompt additionally includes:

- accepted repository commit;
- AutoCAD Mechanical process/HWND/document identity;
- plugin/File IPC/LISP prerequisites;
- approved roots and disposable fixture rules;
- pre/post file hashes, DBMOD, timestamps, and cleanup;
- fresh-preflight requirement for every mutation;
- defect split protocol;
- explicit no-repository-write policy under Issue #72.

## Cross-review and integration flow

1. Writer cell opens a draft PR.
2. Paired red-team cell reviews read-only and posts findings.
3. Writer addresses valid findings with bounded follow-up commits.
4. Paired red-team rechecks only its domain.
5. Cell 3 audits exact head, diff, CI, review state, PR body, overlap, and stale-base risk.
6. Master PO audits the complete exact head and all evidence.
7. Only Master PO marks ready, accepts, and merges.

For AutoCAD live evidence:

1. Codex Local performs prerequisite inventory and fresh preflight.
2. Codex Local runs only approved disposable S2C/S3B operations.
3. Codex Local posts a redacted evidence packet on #72.
4. Cell 3 checks evidence consistency against repository/Issue state without claiming live execution.
5. Master PO assigns the final acceptance state.

A red-team or integration cell may recommend `PASS`, `CHANGES REQUIRED`, `BLOCKED`, or `REBASELINE REQUIRED`, but the recommendation is advisory.

## Evidence and completion reports

Every writer cell reports:

- Issue, PR, branch, exact base, starting and final heads;
- bounded commit list;
- exact changed-file list;
- focused and canonical verification results;
- hosted checks and synthetic merge SHA;
- retained `SKIP`/`NOT RUN` gates;
- worktree state;
- blockers and external assumptions.

Cell 3 reports:

- exact Issue/PR/base/head/synthetic merge;
- ancestry and ahead/behind state;
- allowlist and write-set overlap result;
- hosted workflow IDs, logs, test counts, and skips;
- unresolved review and paired red-team state;
- PR-body consistency;
- stale-base and merge-order risk;
- advisory verdict;
- confirmation of no repository writes.

Codex Local reports:

- AutoCAD Mechanical version/build, process/HWND/document;
- plugin/File IPC/LISP identity;
- approved fixtures and disposable status;
- exact commands/operations;
- pre/post identities, hashes, DBMOD, timestamps, and artifacts;
- cleanup and rollback state;
- independent S2C and S3B states;
- source/accepted CAD immutability;
- repository writes `NONE`;
- defect reproduction and retained `NOT RUN` gates.

Research cells report:

- inspected internal owners and external sources;
- exact versions/revisions and licenses;
- capability or reuse matrix;
- risks and unsupported claims;
- classification and recommendation;
- concrete review findings tied to design sections or PR lines.

## Conflict and stop conditions

A ChatGPT cell or Codex Local stops when:

- another actor has touched its owned write-set or local target;
- exact base, branch, ancestry, process, HWND, document, path, hash, revision, or approval is wrong;
- an allowlist expansion is required;
- two authorities or stores would be created;
- licensing, pinning, or reproducibility is unclear;
- private/source/accepted CAD could be modified without authorization;
- a required live prerequisite is missing;
- hosted, canonical, or local verification fails;
- cleanup or rollback cannot be guaranteed;
- the actor would need to approve or merge its own work.

The blocker is posted to the owning Issue for Master PO disposition.

## Merge order

- #70 and #71 planning PRs are independent and may be reviewed concurrently.
- Either may merge first if exact-head gates, paired red-team review, Cell 3 integration audit, and Master PO acceptance pass.
- The second PR is not silently rebased; Master PO decides whether it remains conflict-free or needs a bounded rebaseline.
- #72 live evidence does not merge and may complete independently through Codex Local.
- Runtime Issues are created only after the related planning PR is accepted.

## Post-planning reassignment

After #70 merges:

- Cell 1 becomes Wave 1A runtime writer when a fresh runtime Issue opens.
- Cell 4 remains Wave 1A test/security/red-team reviewer.

After #71 merges:

- Cell 2 becomes R1C runtime writer when a fresh runtime Issue opens.
- Cell 5 remains R1C determinism/provenance reviewer.

Cell 3 remains integration/CI/evidence coordinator across Wave 1.

Codex Local remains the AutoCAD Mechanical operator and may validate disposable runtime slices only when a specific Issue authorizes the operation.

## Acceptance criteria

- Five ChatGPT cells have explicit, non-overlapping write/review authority.
- Codex Local is the sole machine-local AutoCAD Mechanical operator under #72.
- One Master PO remains the only final acceptance and merge authority.
- Existing Wave 1 locks and exact bases are preserved.
- Research, CI audit, and local live preparation run concurrently without unauthorized production-code writes.
- Each actor has a self-contained prompt and completion report.
- No runtime capability is promoted by this governance design.
