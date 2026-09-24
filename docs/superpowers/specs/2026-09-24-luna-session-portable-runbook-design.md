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
9. Execute the smallest bounded action. A required review that is still
   pending holds only the affected mutation/promotion lane. `WAIT_SAFE` is a
   coordination label, not a project stop condition, approval, or replacement
   for the continuation/failover contract in Issue #305. Keep the exact gated
   head frozen, continue safe non-overlapping/read-only work, consume a
   required verdict once it exists, and use the channel-agnostic PO failover
   when a review channel is known unresponsive. Do not use Human as a relay or
   poll continuously. Do not mutate the gated head except to resolve a current
   material finding.
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

Issue #305 owns the canonical Luna continuation/resume contract. The tracked
template and validator must preserve its current minimum retained context;
this design does not define a competing exact-field schema:

```text
GOAL
CURRENT_MAIN
CURRENT_HEAD
ACTIVE_PR
DONE
ACCEPTED_EVIDENCE_REFS
FIRST_UNSATISFIED_BOUNDARY
CURRENT_RISK
ACTIVE_WRITESET
LIVE_LOCK_STATE
UNACKED_CURRENT_ADVISORIES
NEXT_ACTION
```

The validator must retain every field required by the current #305 contract,
reject blank values and obvious placeholders, and fail closed for any
unreconciled contract change. Supplemental summary fields are permitted only
as non-authoritative views; they must not replace or discard canonical context.
Currentness is re-established by fresh GitHub/Git reads, never inferred from a
cached resume value. Coordination labels such as `COMPLETED`,
`MATERIAL_FINDING`, `REVIEW_PENDING`, and `SAFE_NEXT_PREP` are not approval
identities and cannot make a prior verdict current.

## Proposed interfaces

Add one PowerShell entry point, `scripts/luna-session.ps1`, with these bounded
actions:

- `Start`: print the runbook, repository identity, Git cleanliness, and the
  next required read-only checks.
- `Doctor`: validate available local tools and report actionable blockers.
- `BuildPlugin`: require the exact current clean source head, invoke the
  existing solution's clean Release x64 build owner, then print the observed
  source head/tree, derived DLL path, and SHA-256 without loading it.
- `Packet`: establish exact clean HEAD-to-DLL provenance in the same
  invocation before printing a load packet. Rebuild through the existing
  solution and hash the resulting DLL; do not trust a pre-existing DLL merely
  because its path or current bytes are known. If the current clean source
  head cannot be bound to those bytes, fail closed. This run-scoped proof
  requires no persistent provenance store.
- `ValidateResume -ResumeState <path>`: validate and retain the current
  canonical #305 minimum context without changing Git or AutoCAD state.

The script must fail closed on unknown actions, missing files, dirty-source
build requests, unsupported product boundaries, or missing required tools.

## Verification and acceptance

The contract test must prove that:

- the runbook names the canonical docs and authoritative scripts;
- the runbook preserves the current #305 minimum resume context and makes
  WAIT_SAFE/failover semantics defer to that canonical continuation contract;
- the script derives paths from its repository root;
- the script names the existing solution, DLL output, LSP, and commands;
- no private path, API key, conversation ID, HWND, or PID is required in the
  tracked interface;
- invalid resume state is rejected and a complete state is accepted;
- a missing canonical #305 field is rejected and supplemental coordination
  labels cannot substitute for canonical context or fresh verdicts;
- Packet fails closed on dirty/stale/unproven source-to-DLL provenance and
  binds its printed SHA to a clean exact-head build in the same invocation;
- the script does not duplicate `scripts\\verify.ps1` test selection.

Run focused tests first, then `scripts\\verify.ps1` with the appropriate live
gate explicitly recorded. `git diff --check` and a clean-tree check are
required before commit.

## Completion record

The implementation plan must record the approval date, implementation head,
verification command/result, and any unavailable private/live gates. The
runbook is stable policy; current GitHub state and current plugin SHA remain
fresh runtime evidence and must not be copied into the stable policy file.
