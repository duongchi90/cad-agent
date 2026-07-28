# Agent Action Approval Design

**Status:** Approved by delegated user authority on 2026-07-28

**Target:** Windows, Python 3.11, AutoCAD Mechanical 2027

## Goal

Make every ordinary Agent entry point advisory and non-mutating by default.
Applying an `AgentReport` to Primitive or Semantic IR must require an explicit,
auditable operator approval while preserving the existing manual
`apply_agent_report()` library API.

## Considered approaches

1. Keep automatic application and add an interactive prompt. This is rejected
   because it is unsafe in automation and does not produce reproducible approval
   evidence.
2. Remove application from the runners completely. This is safe but makes an
   approved end-to-end run unnecessarily awkward.
3. Keep report generation as the default and add a two-part application gate.
   This is selected because it is safe in unattended runs and still supports an
   explicit approved workflow.

## Design

- `agent_lib.run.run()` generates and saves the Agent report but does not call
  `apply_agent_report()` by default.
- Application requires both the literal confirmation
  `--confirm-agent-actions APPLY` and a non-empty
  `--agent-action-approval` reference. Supplying only one or any other literal
  is rejected before report generation or IR mutation.
- The programmatic runner exposes the same two inputs. The approval gate is a
  small independently tested function that records whether application was
  requested, whether it occurred, the action count, the approval reference,
  and the application summary.
- Every successful runner writes `agent_application.json` beside
  `agent_report.json`. The application record is advisory/default-safe when no
  approval was supplied and approval-bound when actions were applied.
- The synthetic demo remains non-mutating and writes the same application
  record. It demonstrates advice generation, not an implicit approval shortcut.
- DXF generation uses the unchanged IR in the default path and the explicitly
  approved mutated IR in the approved path.
- `agent_lib.batch_agent.apply_agent_report()` remains unchanged for callers
  that already provide their own approval and audit boundary.

## Boundaries

- This gate controls Agent changes to in-memory Primitive/Semantic IR. It does
  not authorize AutoCAD production drawing mutation.
- Existing Mechanical repair backup, confirmation, live review, and second
  review gates remain mandatory and separate.
- The approval reference is operator-supplied audit text; the runner does not
  claim to authenticate an external approval system.
- OCR/font correction and fidelity reconstruction are outside this slice.

## Acceptance criteria

1. Tests prove that the default gate never invokes `apply_agent_report()` and
   leaves every action unapplied.
2. Tests prove that partial or invalid approval is rejected without mutation.
3. Tests prove that `APPLY` plus a non-empty approval reference invokes the
   existing application API and records approval evidence.
4. The demo contains no automatic application path.
5. Architecture/status documentation describes the approved advisory default.
6. Focused tests and `scripts/verify.ps1` pass.
