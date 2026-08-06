# S3B Accepted Governance Rebaseline Design

Date: 2026-08-06

Issue: #66

Exact base: `a9968480258e01fda9d4dfbf01a27958b67747bc`

Branch: `governance/s3b-accepted-rebaseline`

## 1. Purpose

Refresh the two authoritative operational governance documents after PR #65
merged S3B exact-base Xref inspection and approved disposable extraction into
`main`.

This rebaseline records accepted facts only. It does not select, design,
unlock, or implement another runtime milestone.

## 2. Considered approaches

### A. Update only `STATUS.md` and `HANDOFF.md`

This matches the minimal pattern used by PR #62. It is fast, but the exact
post-S3B decision boundary would exist only in the Issue and PR discussion.

### B. Add a bounded design and plan, then update the two authoritative docs

This keeps the final runtime-facing documents concise while preserving an
auditable exact-base, allowlist, sequencing, verification, and rollback record.
It adds no runtime authority and uses the existing Superpowers documentation
structure.

### C. Create a new roadmap or governance subsystem

This would duplicate authority already owned by `STATUS.md`, `HANDOFF.md`, the
Issue, and Git history. It is rejected.

**Decision:** use approach B. The additional documents are bounded records,
not new governance owners.

## 3. Authoritative facts to record

The rebaseline must state:

- S3B implementation was accepted and merged through PR #65.
- The accepted S3B merge and current rebaseline base is
  `a9968480258e01fda9d4dfbf01a27958b67747bc`.
- Issue #64 is completed.
- The accepted runtime verification head was
  `9f5dc302643fdfae77cbda65dd6cdc0c8deccc59`.
- The record-only final branch head was
  `67c3496da313245fc9ceeee26814e099b32f2c87`.
- AutoCAD Mechanical S3B live acceptance remains `NOT RUN`.
- Hosted AutoCAD .NET remains `NOT RUN`.
- No private drawing or source-data acceptance is promoted.
- S3C, R1C SourceBundle/source-fusion, registry, revision, repair, verdict,
  publication, and OCR remain locked.
- No next runtime milestone is authorized by this rebaseline.

Unavailable-state `SKIP` evidence must never be described as live acceptance.

## 4. Document ownership and changes

### `docs/STATUS.md`

Replace the stale S3B planning-only governance section with a current section
that records S3B as accepted/merged, names the exact merge, preserves the
`NOT RUN` live state, and keeps every future runtime scope locked.

Do not rewrite unrelated historical status sections.

### `docs/HANDOFF.md`

Update the current operational handoff so that:

- PR #65 and merge `a9968480...` are the latest accepted implementation;
- S3B's accepted boundary and remaining live limitation are summarized;
- stale instructions to plan or implement S3B are removed;
- the next action is a future-slice selection gate requiring a separate Issue,
  exact base, branch, allowlist, verification gates, and PO authorization;
- no particular future runtime slice is selected.

### Design and plan records

The design and plan files document this bounded rebaseline workflow. They do
not become alternative status, roadmap, runtime, or acceptance authorities.

## 5. Exact allowlist

Create:

- `docs/superpowers/specs/2026-08-06-s3b-accepted-governance-rebaseline-design.md`
- `docs/superpowers/plans/2026-08-06-s3b-accepted-governance-rebaseline.md`

Modify:

- `docs/STATUS.md`
- `docs/HANDOFF.md`

Every other repository path is forbidden.

## 6. Sequencing and review gates

1. Commit this design only and stop for PO review.
2. After design acceptance, add the implementation plan only and stop again.
3. After plan acceptance, update `STATUS.md` and `HANDOFF.md` in one bounded
   documentation commit.
4. Run focused governance/document checks and the canonical verifier.
5. Open one PR to `main` with an exact four-path audit and the eight-part Reuse
   Declaration.
6. Keep the PR unmerged until final PO review.

No stage may use amend, squash, rebase, force-push, or a merge from another
branch without a new PO decision.

## 7. Verification design

Verification must distinguish repository integrity from unavailable live gates.

Required evidence:

- branch merge-base equals
  `a9968480258e01fda9d4dfbf01a27958b67747bc`;
- final changed-file list equals the four-path allowlist;
- no stale statement says S3B implementation is planning-only or locked;
- no statement promotes AutoCAD live, hosted AutoCAD .NET, or private data;
- all future runtime locks are present in both authoritative documents;
- focused documentation/governance checks pass;
- `scripts/verify.ps1` passes, with unavailable gates reported truthfully as
  `NOT RUN` or `SKIP`.

Hosted CI may verify the synthetic merge and documentation contracts. It may
not promote a gate that requires an operator-controlled AutoCAD Mechanical
session or approved private inputs.

## 8. Failure handling

Fail closed and stop when:

- any non-allowlisted path changes;
- `main` moves and the approved exact base is no longer the intended base;
- a document selects or unlocks a future runtime milestone;
- `NOT RUN` or `SKIP` is rewritten as acceptance;
- duplicate roadmap, status, registry, revision, repair, verdict, or
  publication authority is introduced;
- verification evidence cannot be reproduced.

Corrections must use a new bounded commit unless PO explicitly authorizes a
rewrite.

## 9. Rollback

Before merge, delete the branch or revert its bounded commits. After merge,
revert the governance merge commit. No data migration, artifact cleanup,
source-DWG action, or runtime rollback is required because the scope is
strictly documentation-only.

## 10. Acceptance outcome

Acceptance means only that `STATUS.md` and `HANDOFF.md` accurately reflect the
post-S3B repository state on the named exact base. It does not authorize S3C,
R1C, registry, revision, repair, verdict, publication, OCR, private-data use,
or any AutoCAD mutation or live execution.