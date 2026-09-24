# Luna Session Runbook

This is the portable, repository-owned entry point for preparing a Luna/CAD
Agent session on a supported Windows workstation. It documents the existing
owners; it does not automate AutoCAD or supersede project policy.

## Read first

- Product and scope: [`PROJECT.md`](PROJECT.md)
- Architecture: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Verified status: [`STATUS.md`](STATUS.md)
- Quality gates: [`QUALITY.md`](QUALITY.md)
- AI roles and authority: [`AI_OPERATING_MODEL.md`](AI_OPERATING_MODEL.md)
- Approved design: [`portable runbook design`](superpowers/specs/2026-09-24-luna-session-portable-runbook-design.md)
- Implementation record: [`implementation plan`](superpowers/plans/2026-09-24-luna-session-portable-runbook.md)
- Canonical continuation context: GitHub Issue [#305](https://github.com/duongchi90/cad-agent/issues/305)

Mutable GitHub state, exact heads, reviews, CI, runtime identity, and artifact
hashes must be freshly observed when used. This stable document and the resume
template are not evidence that any current gate has passed.

## Supported boundary and owners

Use the repository's Windows, Python 3.11, AutoCAD Mechanical 2027, and
Tesseract 5.4.0.20240606 environment. Reuse:

- `scripts/bootstrap.ps1` for the Python environment;
- `scripts/verify.ps1` as the sole authoritative verification selector;
- `autocad_plugin/CadAgent.AutoCAD2027.sln` for the existing plugin build;
- `mcp_integration_lib/mcp_dispatch.lsp` and `CADAGENT_DISPATCH` for the
  existing dispatcher;
- Issue #305 and current GitHub PR/CI/review evidence for durable continuation.

Do not add another dispatcher, test selector, transport, resume store, token,
issuer, registry, authority, or control plane. Do not commit machine paths,
credentials, session/conversation IDs, PIDs/HWNDs, private inputs, or live
artifacts.

## Local command planner

From any directory in the checkout, run the existing entry point:

```powershell
.\scripts\luna-session.ps1 Start
.\scripts\luna-session.ps1 Doctor
.\scripts\luna-session.ps1 BuildPlugin
.\scripts\luna-session.ps1 Packet
.\scripts\luna-session.ps1 ValidateResume -ResumeState <path-to-local-json>
```

The script derives the repository root from its own location. `Start` reports
the local repository identity and cleanliness and identifies the fresh
read-only checks still needed. A cached `origin/main` ref is not fresh GitHub
evidence. `Doctor` reports available tool versions and missing prerequisites;
it never launches, attaches to, or controls AutoCAD.

`BuildPlugin` and `Packet` require a clean exact source head. `Packet` performs
the existing solution's clean Release x64 build in the same invocation,
confirms the exact source head/tree did not change, derives the DLL path, and
prints that build output's SHA-256. It fails closed if cleanliness, source
currentness, build success, output existence, or the source-to-DLL binding
cannot be proven. A pre-existing DLL or a SHA copied from an earlier run is
not accepted as current provenance. The proof is run-scoped and is not saved
to a new state store.

`ValidateResume` checks the current #305 canonical field set and rejects
malformed JSON, missing or blank fields, obvious placeholders, or a changed
canonical contract that has not been reconciled. Coordination labels such as
`COMPLETED`, `MATERIAL_FINDING`, `REVIEW_PENDING`, and `SAFE_NEXT_PREP` are
not approvals and cannot replace canonical context or fresh evidence. The
tracked blank template at [`templates/luna-resume-state.json`](templates/luna-resume-state.json)
is a shape example, not a valid resume record.

Use `scripts/verify.ps1` for full verification; do not copy its pytest
selection into this tool. Report missing prerequisite states as `BLOCKER`,
`SKIP`, or `NOT RUN` as appropriate. Never relabel an unavailable live/private
gate as `PASS`.

## Manual AutoCAD load sequence

Only an operator performs this sequence after independently checking the
current task's authorization, exact candidate identity, and required live
preconditions. The `Packet` action prints instructions; it does not execute
any of them:

```text
NETLOAD <derived-repo>\autocad_plugin\CadAgent.AutoCAD2027\bin\x64\Release\net10.0-windows\CadAgent.AutoCAD2027.dll
APPLOAD <derived-repo>\mcp_integration_lib\mcp_dispatch.lsp
Load Once
CADAGENT_HEALTH
```

Never run `NETLOAD`, `APPLOAD`, `Load Once`, or `CADAGENT_HEALTH` from the
PowerShell helper. It must not send FileIPC requests, manipulate the AutoCAD
UI/process, create or modify a drawing, or infer target identity from a
window title. Live FileIPC/CAD work still requires its applicable exact-head
reviews, a disposable candidate where authorized, an exclusive live lane,
and truthful readback/save-reopen evidence. Accepted/source drawings remain
non-targetable unless a distinct approval explicitly changes that boundary.

## Resuming work

Start each material boundary by freshly reading canonical `main`, the active
issue/PR, CI and required verdicts, plus the exact local `HEAD` and worktree
status. Use the #305 template to preserve the retained context, but reconcile
every mutable value against its current owner. Keep satisfying evidence; do
not repeat a gate solely because a new session started. A pending review holds
only the affected lane: continue safe, disjoint read-only preparation and
consume each current verdict once. Use the established channel-agnostic PO
failover for an unresponsive review channel; do not use a Human relay.

## Temporary files and cleanup

Any caller-supplied resume JSON and build outputs remain local. The tool does
not delete old Temp directories or any uncertain file. Preserve AutoCAD
recovery files (`.sv$`) and customer/source drawings. Cleanup is a separate
operation that requires exact target resolution and applicable authority.
