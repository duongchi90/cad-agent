# CAD Agent Private GitHub Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Initialize the extracted CAD Agent project as a local Git repository and publish its initial commit to a private GitHub repository named `cad-agent`.

**Architecture:** The project remains in `C:\Users\duong\cad_agent`. Git tracks source code, tests, schemas, and documentation while `.gitignore` excludes local Python environments, cache, editor state, build output, and likely secret files. GitHub is the private remote; authentication is performed by the account owner through GitHub's sign-in flow.

**Tech Stack:** Git for Windows 2.55.0.3, GitHub private repositories, PowerShell, Python project files.

## Global Constraints

- Repository name: `cad-agent`.
- Repository visibility: private.
- Never commit `.env`, private keys, certificates, or a `secrets/` directory.
- Preserve the supplied project files; do not modify application behavior.

---

### Task 1: Validate and initialize the local Git repository

**Files:**
- Create: `.git/` (Git metadata)
- Verify: `.gitignore`
- Verify: `docs/superpowers/specs/2026-07-19-github-private-import-design.md`
- Verify: `docs/superpowers/plans/2026-07-19-github-private-import.md`

**Interfaces:**
- Consumes: Extracted project rooted at `C:\Users\duong\cad_agent`.
- Produces: A `main` branch with a clean initial commit.

- [ ] **Step 1: Inspect files selected for the initial commit**

Run:

```powershell
& 'C:\Program Files\Git\cmd\git.exe' -C 'C:\Users\duong\cad_agent' status --short
```

Expected: Git is not initialized yet, or a list containing source, tests, documentation, `.gitignore`, and no ignored secret files.

- [ ] **Step 2: Initialize Git and stage the project**

Run:

```powershell
$git = 'C:\Program Files\Git\cmd\git.exe'
& $git -C 'C:\Users\duong\cad_agent' init -b main
& $git -C 'C:\Users\duong\cad_agent' add --all
& $git -C 'C:\Users\duong\cad_agent' status --short
```

Expected: The staged list does not contain `.env`, `*.key`, `*.pem`, `secrets/`, `__pycache__/`, or `.venv/`.

- [ ] **Step 3: Create and verify the initial commit**

Run:

```powershell
$git = 'C:\Program Files\Git\cmd\git.exe'
& $git -C 'C:\Users\duong\cad_agent' commit -m 'Initial import'
& $git -C 'C:\Users\duong\cad_agent' log -1 --oneline
```

Expected: The latest commit message is `Initial import`.

### Task 2: Create and connect the private GitHub remote

**Files:**
- Modify: `.git/config` (remote `origin` only)

**Interfaces:**
- Consumes: Local `main` branch with the initial commit.
- Produces: `origin` pointing to the private GitHub repository and an uploaded `main` branch.

- [ ] **Step 1: Create the private repository while signed in to GitHub**

Open GitHub's new-repository page, create a repository named `cad-agent`, select **Private**, and leave README, `.gitignore`, and license unchecked because the local project already contains these files.

Expected: GitHub displays a clone URL in the form `https://github.com/<account>/cad-agent.git`.

- [ ] **Step 2: Add the remote and push main**

Run after replacing `<account>` with the GitHub account name:

```powershell
$git = 'C:\Program Files\Git\cmd\git.exe'
& $git -C 'C:\Users\duong\cad_agent' remote add origin 'https://github.com/<account>/cad-agent.git'
& $git -C 'C:\Users\duong\cad_agent' push -u origin main
```

Expected: GitHub authentication completes and `main` is set to track `origin/main`.

- [ ] **Step 3: Verify private remote state**

Run:

```powershell
$git = 'C:\Program Files\Git\cmd\git.exe'
& $git -C 'C:\Users\duong\cad_agent' remote -v
& $git -C 'C:\Users\duong\cad_agent' status --short --branch
```

Expected: `origin` uses the `cad-agent` GitHub URL and branch output shows `main...origin/main` with no pending files.
