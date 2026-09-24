# Luna Session Portable Runbook and CAD Load Contract

**Status:** APPROVED FOR SPECIFICATION

**Approval date:** 2026-09-24

**Approved scope:** Persist the Luna/SOL continuation protocol, portable
machine prerequisites, exact CadAgent build/load instructions, and resumable
checkpoint contract in the repository. Add a small local validation tool that
derives machine-specific paths at runtime. Do not add a production transport,
second dispatcher, second state store, or automatic AutoCAD UI driver.

## Problem

Each new session can lose operational context: which repository state is
current, which prerequisites are required, where the current CadAgent DLL is
built, how the existing LSP dispatcher is loaded, what Luna may do while SOL
is silent, and which facts must be preserved for a later session. Chat history
is not a durable interface and paths from an earlier machine or live epoch must
not be treated as current.

## Goals

1. A fresh machine can clone the repository and discover the required workflow
   from tracked files.
2. The workflow derives the repository root, current exact Git head, build
   output, and dispatcher path instead of hardcoding a workstation path.
3. The workflow records the exact plugin artifact path and SHA-256 after a
   successful Release x64 build.
4. The workflow prints the bounded manual AutoCAD sequence:

   ```text
   NETLOAD <derived-repo>\\autocad_plugin\\CadAgent.AutoCAD2027\\bin\\x64\\Release\\net10.0-windows\\CadAgent.AutoCAD2027.dll
   APPLOAD <derived-repo>\\mcp_integration_lib\\mcp_dispatch.lsp
   Load Once
   CADAGENT_HEALTH
   ```

5. A new session can reconstruct work from a stable resume-state contract and
   fresh GitHub/Git state without repeating satisfying evidence.
6. Missing local prerequisites are reported as `BLOCKER`, `SKIP`, or
   `NOT RUN`; the tool must not invent a pass or ask for a broad human relay.

## Non-goals and safety boundaries

- No automatic `NETLOAD`, `APPLOAD`, AutoCAD UI control, process control, or
  production drawing mutation.
- No custom Codex/ChatGPT/SOL transport. Direct messaging remains optional;
  GitHub remains the durable evidence and verdict authority.
- No API keys, conversation IDs, HWND/PID values, private drawings, accepted
  DXFs, generated live artifacts, or machine-specific secrets in Git.
- No use of the historical `C:\\temp\\cad-agent-m2-plugin-identity` artifact
  as the current plugin. A live packet may name an immutable artifact only when
  its exact source head and SHA are fresh and explicitly bound.
- No duplicate pytest selection. The authoritative `scripts\\verify.ps1`
  remains the verification owner.
- Cleanup of old temporary directories is a separate, explicitly resolved
  operation; this feature does not delete files implicitly.

## Existing owners to reuse

| Need | Existing owner |
| --- | --- |
| Python environment | `scripts/bootstrap.ps1` |
| Full verification | `scripts/verify.ps1` |
| AutoCAD plugin build | `autocad_plugin/CadAgent.AutoCAD2027.sln` |
| Managed dispatcher | `autocad_plugin/CadAgent.AutoCAD2027` |
| AutoLISP dispatcher | `mcp_integration_lib/mcp_dispatch.lsp` |
| AutoCAD command | `CADAGENT_DISPATCH` |
| Product pipeline resume | existing `cad_agent` manifest/checkpoint resume |
| Durable project status | GitHub issues, PRs, CI, and tracked status docs |

The new tool is only a thin session/runbook validator and command planner. It
must not reimplement any of these owners.

## Portable workflow

The tracked workflow is:

1. Read the runbook and canonical project documents.
2. Resolve the repository root from the script location.
3. Read local Git branch, exact `HEAD`, worktree cleanliness, and the remote
   main ref without treating cached refs as fresh GitHub evidence.
4. Validate Windows, PowerShell, Python 3.11, .NET SDK, Tesseract 5.4, and
   the AutoCAD Mechanical 2027 boundary when a live gate is requested.
5. Use the existing bootstrap and verification owners as appropriate.
6. Build the plugin from the exact selected clean source head with Release x64
   configuration. Derive the output path from the repository root and compute
   its SHA-256.
7. Print the manual `NETLOAD`/`APPLOAD` packet and the post-load health check.
8. Fresh-read the active GitHub issue/PR/CI and current review boundary before
   material work. Never use a stale mutable SHA or chat-only verdict.
9. Execute the smallest bounded action. If SOL is silent, freeze the exact
   reviewed state and enter `WAIT_SAFE`; continue only non-overlapping
   read-only preparation and do not poll continuously.
10. At every meaningful checkpoint, update the durable GitHub evidence and
    preserve the resume-state fields below.

## Machine-specific values

Machine-specific values are discovered or supplied locally and are never
committed:

- absolute repository root;
- installed AutoCAD path and observed process identity;
- temporary IPC directory;
- observed AutoCAD HWND/PID;
- private input PDF/DWG paths and hashes;
- API credentials and connector configuration.

The tool may display these values for the current run, but must not write them
to tracked documentation or use a caller-provided HWND/PID as runtime proof.

## Resume-state contract

The tracked template and validator must require these fields exactly:

```text
MAIN
HEAD
ACTIVE_ISSUE
ACTIVE_PR
BOUNDARY
COMPLETED
EVIDENCE_REFS
MATERIAL_FINDING
REVIEW_PENDING
SAFE_NEXT_PREP
```

`HEAD`, `MAIN`, and evidence references must be exact values observed from the
current run. The contract must reject blank values and obvious placeholders,
but it must not assert that a cached value is still current. Freshness is
re-established by the next session's GitHub/Git read.

## Proposed interfaces

Add one PowerShell entry point, `scripts/luna-session.ps1`, with these bounded
actions:

- `Start`: print the runbook, repository identity, Git cleanliness, and the
  next required read-only checks.
- `Doctor`: validate available local tools and report actionable blockers.
- `BuildPlugin`: invoke the existing Release x64 build owner, then print the
  derived DLL path and SHA-256 without loading it.
- `Packet`: print the exact manual AutoCAD load packet for the built DLL and
  repository LSP.
- `ValidateResume -ResumeState <path>`: validate the ten required resume
  fields without changing Git or AutoCAD state.

The script must fail closed on unknown actions, missing files, dirty-source
build requests, unsupported product boundaries, or missing required tools.

## Verification and acceptance

The contract test must prove that:

- the runbook names the canonical docs and authoritative scripts;
- the runbook contains the ten resume fields and WAIT_SAFE rules;
- the script derives paths from its repository root;
- the script names the existing solution, DLL output, LSP, and commands;
- no private path, API key, conversation ID, HWND, or PID is required in the
  tracked interface;
- invalid resume state is rejected and a complete state is accepted;
- the script does not duplicate `scripts\\verify.ps1` test selection.

Run focused tests first, then `scripts\\verify.ps1` with the appropriate live
gate explicitly recorded. `git diff --check` and a clean-tree check are
required before commit.

## Completion record

The implementation plan must record the approval date, implementation head,
verification command/result, and any unavailable private/live gates. The
runbook is stable policy; current GitHub state and current plugin SHA remain
fresh runtime evidence and must not be copied into the stable policy file.
