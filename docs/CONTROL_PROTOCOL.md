# CAD Agent — SOL / Luna Control & Audit Protocol

Status: owner-approved governance protocol.

Protocol version: **1.4**.

This document defines the control-plane contract used by SOL and Luna / Codex Desktop for baton ownership, Audit, live-action authorization, evidence retention, parallel-lane isolation, and exactly-once terminal consumption. It complements `docs/AI_OPERATING_MODEL.md`; it does not expand product/runtime authority by itself.

## 1. Canonical scan order

Every SOL/Audit wake follows this order for the relevant lane:

1. fresh `main`;
2. canonical HOT STATE for the active lane/frontier;
3. newest terminal/action after that HOT STATE;
4. current PR/head/CI only when relevant;
5. determine `NEXT_OWNER`;
6. act only for that owner.

GitHub current state beats chat memory, PR body, stale handoff text, and older comments. If there is no material delta and the current owner is already executing the correct packet, Audit writes nothing.

## 2. Baton

`NEXT_OWNER` is exactly one of:

- `SOL`
- `Luna / Codex Desktop`

No third baton owner is valid. Human Owner is not a relay. When Human action is genuinely required, it is represented as a bounded gate condition on the owning lane; `NEXT_OWNER` remains SOL or Luna / Codex Desktop. Satisfying a Human gate never grants authority beyond the exact waiting packet.

## 3. Required action-packet fields

Every new SOL action packet declares:

```text
CONTROL_PROTOCOL_VERSION
CONTROL_SEQ
LANE_ID
AUTHORITY_ID
CONSUMES_TERMINAL or PREDECESSOR_AUTHORITY
FRESH_MAIN
PINNED_MAIN=<sha|NONE>
NEXT_OWNER
ACTION_CLASS
LIVE_AUTHORITY=YES|NO
ATTEMPT_BUDGET=<integer>
STOP_REPO_WRITE=YES|NO
STOP_LIVE=YES|NO
STOP_PERSISTENT_MUTATION=YES|NO
HARD_LOCKS
EXPECTED_TERMINAL
```

When a Human action is required, the packet also declares the exact `HUMAN_GATE` and the observable condition that satisfies it. Human interaction is a gate, not a baton transfer.

When artifacts or local files matter, the packet also freezes exact literal paths, lengths, and SHA-256 identities.

Missing or contradictory required fields fail closed as `PACKET_CONTRADICTION`; Luna returns to SOL rather than inferring broader authority.

## 4. Stop vocabulary

- `STOP_REPO_WRITE`: no source/test/project/dependency/Git/PR-content mutation except explicitly named governance metadata actions.
- `STOP_LIVE`: no AutoCAD/COM/NETLOAD/File-IPC/provider/private/live execution.
- `STOP_PERSISTENT_MUTATION`: no persistent environment/profile/registry/service/security/trust/printer/driver/system mutation.
- `STOP_ALL`: all three are `YES`.

The legacy standalone phrase `STOP_WRITE` is deprecated for new packets because it is ambiguous about live execution.

## 5. Live-action carve-outs

A live action is executable only when the packet makes authority explicit. Normally this means:

```text
LIVE_AUTHORITY=YES
ATTEMPT_BUDGET>=1
STOP_LIVE=NO
```

If an older `STOP_LIVE` must be overridden for one bounded action, the packet must state:

```text
SUPERSEDES_PRIOR_STOP_LIVE=<comment ids>
FOR_THIS_ACTION_ONLY=YES
```

A carve-out never unlocks camera/render/File-IPC/R6/R7/merge or a second attempt unless those actions are separately named.

Once any part of an authorized live attempt begins, its attempt budget is consumed unless the packet explicitly defines a pre-attempt guard whose failure occurs before live execution.

## 6. Exactly-once terminal consumption

A terminal has only one controlling SOL consumer within its `LANE_ID`.

The earliest valid consumer records `CONSUMER_OF=<terminal id>` and becomes controlling for that lane. A later consumer of the same terminal is `VOID_FOR_CONTROL` and must not create a parallel execution branch from that terminal.

Audit may post one `CONTROL_RESOLUTION` identifying the winner. It must not union authorities or evidence from a void branch.

### 6.1 Parallel-lane isolation

Independent lanes may execute concurrently. Exactly-once terminal consumption does **not** serialize unrelated work.

Parallel execution is allowed only when all of the following are true:

- each lane has a distinct stable `LANE_ID` and its own HOT STATE;
- repository writers have disjoint write-sets, or all but one overlapping lane are read-only;
- no two lanes mutate the same AutoCAD process/session/document, File-IPC channel, candidate artifact, or other live resource concurrently;
- neither lane changes an exact input pinned by another active lane;
- cross-lane dependencies are explicit rather than inferred from chat chronology.

An exact-main live lane with `PINNED_MAIN=<sha>` blocks merge/ref movement of `main` while that pin is active, but it does **not** block independent branch-only commits, PR review, hosted CI, documentation work, or offline tests whose write-set and runtime resources do not overlap the live lane. Those parallel lanes must remain unmerged until moving `main` is explicitly safe.

A terminal in one lane cannot be consumed as authority in another lane unless the first lane has terminated and a later packet explicitly records the cross-lane dependency/handoff.

## 7. Chronology without timestamp dependence

GitHub connector timestamps can be absent and very long Issue threads can be truncated. Authority chronology therefore does not depend on timestamps alone.

Use, in order:

1. explicit predecessor/consumer links within the same `LANE_ID`;
2. `CONTROL_SEQ` within that lane;
3. exact SHA/head/artifact identities;
4. canonical HOT STATE for that lane;
5. comment-ID ordering only as a fallback when explicit links cannot resolve the relation.

Never compare `CONTROL_SEQ` values from different lanes as if they formed one global sequence.

## 8. Canonical HOT STATE

Maintain one canonical HOT STATE per active lane/frontier. It contains only the minimum current control facts:

- `LANE_ID`;
- fresh main and any exact `PINNED_MAIN`;
- active PR/head when relevant;
- latest accepted terminal;
- controlling decision;
- current owner;
- exact next trigger/action class;
- live/write/persistent-mutation authority;
- attempt budget;
- repository write-set and live-resource identity when concurrency matters;
- hard locks.

HOT STATE is an index/pointer, not a replacement for underlying evidence. PR body and historical handoff text are not current authority when they disagree with HOT STATE plus fresh GitHub state.

## 9. Audit anti-churn

`NO_MATERIAL_DELTA => NO_COMMENT`.

Audit does not regenerate packets just to restate existing constraints. One technical terminal gets one controlling disposition in its lane. A governance clarification that changes no executable scope must state `NO_NEW_EXECUTION_ACTION=YES`.

Stale, duplicate, and void evidence is labeled explicitly and never rolls the frontier backward.

## 10. Luna ACK for live/persistent actions

Before any live or persistent-mutation action, Luna records a compact ACK:

```text
ACK_AUTHORITY
CONTROL_SEQ
LANE_ID
LIVE_ALLOWED
ATTEMPT_BUDGET
```

Include exact literal artifacts/paths when applicable. If the ACK cannot be made consistent with the packet, Luna returns `PACKET_CONTRADICTION` without executing.

Offline/read-only packets do not require ACK unless explicitly requested.

## 11. Terminal evidence completeness

For local/live work, retain when applicable:

- `LANE_ID` and exact authority/control sequence;
- requested literal path and observed returned identity (`FullName` / Name);
- command/API boundary reached and exact completion/failure;
- DLL/deps/fixture literal path + length + SHA-256;
- PID/session/HWND identity;
- trace provider/config + event-loss + size gate;
- cleanup result and survivor count;
- repository parity;
- every material `NOT_RUN`.

Never infer an unretained value. Missing causal evidence is `EVIDENCE_INSUFFICIENT`, not a defect conclusion.

## 12. Artifact retention

An accepted local artifact epoch remains retained until either:

- a successor artifact epoch is accepted by SOL; or
- the owning PR/task is merged, abandoned, or explicitly releases retention.

Artifact authority is `{literal path, length, SHA256}`. Do not derive/search for a replacement path from a commit SHA when a literal canonical path is frozen, and never substitute stale bytes.

## 13. Dual review

Issue #131 standing rule comment `5308943608` remains controlling.

When SOL requires two independent reviews:

1. freeze one canonical evidence set;
2. complete Pass A and finalize its verdict/findings;
3. complete Pass B on the same frozen evidence without exposing Pass A's verdict/findings to B before B is final;
4. reconcile only after both are independently final.

Evidence drift re-epochs both reviews. Luna is not reviewer #2 merely to manufacture independence.

## 14. Communication contract

SOL decisions state what **is authorized** before listing prohibitions. Luna terminals state the **first causal boundary reached** before secondary diagnostics.

`PASS`, `BLOCKED`, `PRECONDITION_BLOCKED`, and `EVIDENCE_INSUFFICIENT` are distinct states and must not be used interchangeably.

Every action packet and terminal ends with exactly one `NEXT_OWNER`. A Human gate may pause that owner but does not replace it.

When GitHub is writable, no party should require the Human Owner to copy/paste control messages between SOL and Luna.

## 15. Protocol adoption

Protocol 1.4 is prospective. Adoption does not automatically re-epoch or broaden an already-running technical packet. A current action remains governed by its controlling technical decision until it terminates, unless a later explicit control resolution changes executable scope.
