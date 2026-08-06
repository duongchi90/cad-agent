# S3B Accepted Governance Rebaseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the authoritative governance documents so they accurately record S3B as accepted/merged while keeping all future runtime scopes locked.

**Architecture:** This is a documentation-only rebaseline on exact base `a9968480258e01fda9d4dfbf01a27958b67747bc`. The design and plan remain audit records; `docs/STATUS.md` and `docs/HANDOFF.md` remain the only operational status/handoff authorities.

**Tech Stack:** Markdown, Git, GitHub pull requests, existing repository verification scripts.

## Global Constraints

- Exact base: `a9968480258e01fda9d4dfbf01a27958b67747bc`.
- Branch: `governance/s3b-accepted-rebaseline`.
- Allowed paths are exactly the four paths listed in Issue #66.
- No runtime, schema, test, fixture, File IPC, AutoCAD, SourceBundle, source-fusion, registry, revision, repair, verdict, publication, OCR, dependency, lock-file, workflow, accepted/private/live-artifact change.
- S3B implementation is accepted through PR #65 and merge `a9968480258e01fda9d4dfbf01a27958b67747bc`.
- AutoCAD Mechanical S3B live acceptance and hosted AutoCAD .NET remain `NOT RUN`.
- S3C, R1C SourceBundle/source-fusion, registry, revision, repair, verdict, publication, and OCR remain `LOCKED`.
- No next runtime milestone is selected or unlocked.
- Do not amend, squash, rebase, force-push, or merge another branch without a new PO decision.

---

### Task 1: Rebaseline `docs/STATUS.md`

**Files:**
- Modify: `docs/STATUS.md`

**Interfaces:**
- Consumes: accepted S3B facts from PR #65, Issue #64, and merge `a9968480...`.
- Produces: the current high-level repository status used by reviewers and coding agents.

- [ ] **Step 1: Replace only the stale S3B planning section**

Replace `## Roadmap and governance gate — S2C accepted; S3B planning only (2026-08-06)` with a section titled `## Roadmap and governance gate — S3B accepted; future runtime locked (2026-08-06)` that states:

```markdown
- S3B implementation is accepted through PR #65 and merge `a9968480258e01fda9d4dfbf01a27958b67747bc`.
- Issue #64 is completed.
- Runtime verification head: `9f5dc302643fdfae77cbda65dd6cdc0c8deccc59`.
- Record-only final head: `67c3496da313245fc9ceeee26814e099b32f2c87`.
- AutoCAD Mechanical S3B live acceptance: **NOT RUN**.
- Hosted AutoCAD .NET: **NOT RUN**.
- No private drawing/source-data acceptance is promoted.
- S3C, R1C SourceBundle/source-fusion, registry, revision, repair, verdict, publication, and OCR remain **locked**.
- No next runtime milestone is selected by this rebaseline.
```

- [ ] **Step 2: Preserve unrelated historical sections**

Confirm that all sections before and after the replaced S3B governance section remain byte-for-byte unchanged.

- [ ] **Step 3: Run focused status assertions**

Run:

```powershell
$body = Get-Content -Raw docs/STATUS.md
if ($body -notmatch 'S3B accepted; future runtime locked') { throw 'missing S3B accepted heading' }
if ($body -match 'S3B planning only') { throw 'stale S3B planning heading remains' }
if ($body -notmatch 'a9968480258e01fda9d4dfbf01a27958b67747bc') { throw 'missing accepted merge' }
if ($body -notmatch 'AutoCAD Mechanical S3B live acceptance: \*\*NOT RUN\*\*') { throw 'missing truthful live gate' }
if ($body -notmatch 'S3C.*locked') { throw 'missing retained locks' }
```

Expected: exit `0`.

- [ ] **Step 4: Commit the authoritative docs update together with Task 2**

Do not commit yet; Task 1 and Task 2 must land in one bounded docs commit.

### Task 2: Rebaseline `docs/HANDOFF.md`

**Files:**
- Modify: `docs/HANDOFF.md`

**Interfaces:**
- Consumes: the accepted S3B merge and current repository locks.
- Produces: the operational handoff used to start the next governance or implementation slice.

- [ ] **Step 1: Update the latest accepted implementation block**

Set the latest accepted implementation merge to `a9968480258e01fda9d4dfbf01a27958b67747bc`, name PR #65, and retain S2C/S3A/R1A/R1B as historical accepted milestones.

- [ ] **Step 2: Replace stale S3B planning instructions**

Replace the S3B planning-only and locked-before-S3B-live sections with a concise accepted S3B section that records:

```markdown
- exact-base Xref inspection and approved extraction are accepted on PR #65;
- source Xref and accepted DWG remain immutable;
- extraction is limited to new disposable candidates;
- only translation, rotation, and positive uniform scale are permitted;
- fresh server-owned live preflight remains mandatory before mutation;
- AutoCAD Mechanical live acceptance remains NOT RUN.
```

- [ ] **Step 3: Set the next action to a future-slice selection gate**

The final next-action section must require a new Issue, exact base, branch, allowlist, verification gates, and PO authorization. It must not name S3C, R1C, or any other runtime slice as selected.

- [ ] **Step 4: Run focused handoff assertions**

Run:

```powershell
$body = Get-Content -Raw docs/HANDOFF.md
if ($body -notmatch 'a9968480258e01fda9d4dfbf01a27958b67747bc') { throw 'missing latest accepted merge' }
if ($body -notmatch 'PR #65') { throw 'missing accepted PR' }
if ($body -match 'Next authorized slice — S3B planning only') { throw 'stale S3B planning section remains' }
if ($body -notmatch 'AutoCAD Mechanical.*NOT RUN') { throw 'missing live limitation' }
if ($body -notmatch 'separate Issue.*exact base.*branch.*allowlist') { throw 'missing future-slice gate' }
```

Expected: exit `0`.

- [ ] **Step 5: Commit both authoritative documents**

```powershell
git add docs/STATUS.md docs/HANDOFF.md
git commit -m "docs: rebaseline governance after S3B acceptance"
```

### Task 3: Verify, audit, and open the governance PR

**Files:**
- Verify only: all four allowlisted paths.

**Interfaces:**
- Consumes: design commit, plan commit, and authoritative docs commit.
- Produces: one reviewable governance PR to `main`.

- [ ] **Step 1: Verify exact base and changed-file allowlist**

Run:

```powershell
git merge-base HEAD a9968480258e01fda9d4dfbf01a27958b67747bc
git diff --name-only a9968480258e01fda9d4dfbf01a27958b67747bc...HEAD
```

Expected merge-base: exactly `a9968480258e01fda9d4dfbf01a27958b67747bc`.

Expected changed paths, no others:

```text
docs/HANDOFF.md
docs/STATUS.md
docs/superpowers/plans/2026-08-06-s3b-accepted-governance-rebaseline.md
docs/superpowers/specs/2026-08-06-s3b-accepted-governance-rebaseline-design.md
```

- [ ] **Step 2: Run canonical verification**

Run:

```powershell
.\scripts\verify.ps1
```

Expected: exit `0`; live/private prerequisites remain truthful `NOT RUN` or `SKIP`.

- [ ] **Step 3: Push normally**

```powershell
git push -u origin governance/s3b-accepted-rebaseline
```

- [ ] **Step 4: Open one PR to `main`**

Use title:

```text
[Governance] Rebaseline after S3B acceptance; keep future runtime locked
```

The PR body must include:

- Issue #66;
- exact base and final head;
- exact four-path audit;
- focused and canonical verification evidence;
- AutoCAD Mechanical live and hosted AutoCAD .NET as `NOT RUN`;
- all retained locks;
- the eight exact Reuse Declaration labels required by CI.

- [ ] **Step 5: Stop for PO final review**

Keep the PR open and unmerged. Do not select or begin any future runtime slice.
