# Codex Bridge Reuse Decision

Date: 2026-08-04
Status: approved
Applies to: Visual Supervisor rollout, especially VS-T4 and VS-T5

## Decision

The CAD Agent will not build a custom Codex transport, JSONL subprocess protocol, thread store, or approval protocol unless the official Codex interfaces are proven insufficient.

Preferred integration order:

1. Official Codex Python SDK, verified on the supported Windows/Python environment.
2. Official Codex App Server protocol only for capabilities not exposed by the Python SDK.
3. `codex exec --json` as a bounded compatibility fallback.
4. MCP only for experiments or external-agent interoperability, not as the production closed-loop transport.

The independent multimodal Visual Supervisor remains a separate reviewer. The CAD Agent Python orchestrator passes validated evidence and contracts to Codex and receives a schema-bound Repair Plan. Codex does not receive visual-pass or publication authority.

## Reused responsibilities

Use the official Codex integration for:

- process and server lifecycle;
- authentication/session reuse;
- thread start, resume, and fork;
- turn start, streaming, steering, interrupt, and completion;
- command/file-change/tool-call events;
- sandbox and approval configuration;
- local image inputs where supported;
- structured output binding to the Repair Plan schema;
- transport retries and protocol framing already provided by the official client.

Do not reimplement these capabilities in CAD Agent unless an execution-time spike records a concrete missing capability or reproducible defect.

## CAD Agent-owned responsibilities

CAD Agent still owns:

- `dimension-register.json`;
- `geometry-comparison.json`;
- `visual-review.json`;
- CAD-specific `repair-plan.json`;
- evidence hashes and stale-evidence rejection;
- region, view, and sheet state machines;
- prompt/evidence assembly for Codex;
- conversion of Codex events into run artifacts;
- entity, datum, dimension, and constraint protection;
- AutoCAD render, entity-map, and measurement operations;
- best-candidate selection;
- publication authorization, backup, reopen verification, and rollback.

## Required Windows compatibility spike

Before implementing the production Codex bridge, add a disposable spike that records exact Python, Codex SDK, Codex CLI/App Server, and Windows versions.

The spike must prove:

1. start and close one Codex client cleanly;
2. start one read-only thread in a disposable repository;
3. complete one plain-text turn;
4. complete one turn with JSON Schema structured output;
5. complete one turn with a local image input when supported;
6. complete one `workspace_write` turn in a disposable repository;
7. receive command and file-change events;
8. interrupt one controlled long-running turn;
9. resume the same thread;
10. leave the production CAD repository and all customer data unchanged.

Each capability is recorded as `PASS`, `FAIL`, `SKIP`, or `NOT RUN`. A failed version may be pinned away from, but the project must not respond by immediately writing a replacement protocol.

## Rollout amendment

The rollout is amended as follows:

- VS-T0 remains unchanged and creates contracts only.
- Add `VS-T4A — Codex SDK Windows Compatibility Spike` before the production bridge.
- Rename the production bridge slice to `VS-T4B — Official Codex Bridge`.
- The multimodal reviewer adapter remains a separate slice and may be implemented in parallel after VS-T0.
- VS-T5 consumes the official bridge and produces a validated Repair Plan; it does not own process transport.

## Production boundary

Recommended production flow:

```text
Visual Supervisor API
  -> validated visual-review.json
  -> CAD Agent orchestrator
  -> official Codex Python SDK
  -> Codex thread with schema-bound repair-plan output
  -> CAD Agent contract and authority validation
  -> existing AutoCAD .NET/File IPC executor
  -> fresh render and measurement evidence
  -> independent Visual Supervisor review
```

The official integration is a transport and worker-control dependency, not a source of CAD truth. All Codex output remains untrusted until CAD Agent validators and post-mutation AutoCAD evidence pass.
