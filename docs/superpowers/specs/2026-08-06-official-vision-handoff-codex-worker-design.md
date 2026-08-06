# Official Vision Handoff and Codex Worker Control Design

Status: PO-approved planning design under Issue #70. This document authorizes
design and future planning only; it does not authorize runtime, dependency,
model, or AutoCAD changes.

Date: 2026-08-06

Issue: #70 — Wave 1A official vision handoff and Codex worker control.

Exact planning base: `d71d0c97e28e03cb430f05589c8381b4ede70e66`.

Planning branch: `planning/w1a-official-vision-codex-worker`.

Planning allowlist: this file and
`docs/superpowers/plans/2026-08-06-official-vision-handoff-codex-worker.md`
only.

## 1. Decision summary

Wave 1A will define one closed, hash-bound `vision-handoff` boundary and one
thin worker-control seam. The future primary transport is the official OpenAI
Codex Python SDK. The official App Server is a secondary interface only when a
reproducible compatibility spike proves that the SDK lacks a required
capability. `codex exec --json` is a bounded disposable/compatibility fallback.
MCP is experimental interoperability only and is not a production transport.

The ownership rule is strict:

```text
ChatGPT/PO vision and approved intent
  -> closed vision-handoff with identities, scope, policy, and expiry
  -> CAD Agent validation and evidence binding
  -> official Codex worker control
  -> schema-bound drawing/repair-plan output
  -> CAD Agent validation and approval gates
  -> existing deterministic CAD and AutoCAD boundaries in later slices
```

Codex is a bounded worker, not a CAD authority. It cannot produce a visual
PASS, engineering approval, CAD truth, AutoCAD mutation authorization, or
publication authorization.

## 2. Scope and non-goals

### 2.1 In scope for the future implementation slice

- A closed `vision-handoff` identity and validation model.
- Source, accepted-base, drawing, IR, evidence, and revision hash binding.
- Component, view, region, sheet, entity, datum, and protected-constraint scope.
- Explicit allowed and forbidden operation classes.
- Owner/PO approval references, expiry, single-use, and stale-evidence rules.
- A thin official SDK worker adapter with start/resume/fork and bounded turns.
- Event capture, steering where officially supported, interrupt, cancellation,
  timeout, cleanup, and deterministic failure mapping.
- Disposable workspace and sandbox authority rules.
- Schema-bound drawing/repair-plan output with no verdict or publication power.
- Fake-adapter and disposable-repository tests before any real model call.
- A compatibility matrix and dependency/pinning gate.
- Secret-free telemetry and evidence packets.
- Migration and rollback rules.

### 2.2 Explicit non-goals and locks

This design does not authorize:

- a production Codex SDK dependency or lock-file change;
- a real model call, customer/private-data run, or production Codex turn;
- AutoCAD or File IPC mutation;
- a new OCR, semantic solver, DXF/DWG writer, dispatcher, gateway, registry,
  revision store, repair executor, verdict authority, publisher, or MCP
  transport;
- a visual PASS, engineering verdict, publication, or automatic approval;
- mutation of source CAD, accepted CAD, private data, or canonical status docs;
- implementation in `agent_lib` or any other runtime package in this planning
  PR.

The first future runtime slice remains disposable and non-AutoCAD. Any live
defect must become a separate bounded Issue.

## 3. Authority and trust model

### 3.1 Owner and PO

The owner supplies engineering truth, approved private inputs, measurements,
fixtures, and high-risk decisions. The PO materializes approved intent,
defines scope and acceptance criteria, and reviews the exact GitHub head. The
PO may not invent measurements, live results, or publication authority.

### 3.2 CAD Agent

CAD Agent owns handoff validation, identity/hash verification, scope and
protected-constraint enforcement, evidence freshness, output contract
validation, run artifacts, and routing to existing deterministic executors.
`cad_agent` remains the manifest/checkpoint owner. Existing package boundaries
remain authoritative.

### 3.3 Codex

Codex owns worker execution inside the official interface: thread lifecycle,
turn execution, supported events, sandbox configuration, and structured output
production. Its output is untrusted until CAD Agent validation passes. A Codex
message or tool event never becomes engineering truth by itself.

### 3.4 Existing CAD and AutoCAD authorities

`primitive_ir_lib`, `semantic_ir_lib`, `agent_lib`, `dxf_builder_lib`,
`mcp_integration_lib`, the .NET/File IPC boundary, existing manifests,
checkpoints, review contracts, and AutoCAD evidence remain the authorities for
their existing responsibilities.

## 4. Internal reuse dossier

The future implementation must reuse these existing boundaries before adding a
new adapter:

| Capability | Existing owner/API | Required reuse | Evidence/tests |
| --- | --- | --- | --- |
| Advisory proposal | `agent_lib.batch_agent.run_agent` | Keep worker output advisory and separate from apply | `agent_lib/tests/test_batch_agent.py`, `agent_lib/tests/test_run.py` |
| Explicit application gate | `agent_lib.batch_agent.apply_agent_report`, `agent_lib.run._apply_report_with_approval` | Do not let a worker call mutate IR or CAD directly | `agent_lib/tests/test_run.py` |
| Auditable report | `agent_lib.models.AgentReport`, `AgentTask`, `AgentAction`, `Evidence` | Reuse action/evidence identity patterns; do not create a second action authority | `agent_lib/tests/test_models.py`, `agent_lib/tests/test_run.py` |
| Hash-bound report storage | `agent_lib.io_utils.save_document`, `load_agent_report` | Preserve deterministic UTF-8 serialization and separately approved reload | `agent_lib/tests/test_io_utils.py`, `agent_lib/tests/test_run.py` |
| SDK compatibility | `agent_lib.codex_sdk_compat`, `scripts/probe_codex_sdk_windows.py` | Extend only through a separately approved compatibility task; remain optional/lazy/fail-closed | `agent_lib/tests/test_codex_sdk_compat.py` |
| Manifest/checkpoint authority | `cad_agent.manifest`, `cad_agent.checkpoint`, `cad_agent.visual_evidence` | Bind handoff to existing run/evidence identity; do not add a manifest store | `tests/test_cad_agent_source_bundle_manifest.py`, `tests/test_visual_evidence.py` |
| Contract validation | `cad_agent.visual_contracts.validate_visual_contract` | Reuse strict required/extra-key, identifier, SHA-256, finite-value, and freshness checks | `tests/test_visual_supervisor_contracts.py`, `tests/test_visual_supervisor_contract_policy.py` |
| Visual review/repair plans | `contracts/visual-supervisor/visual-review.schema.json`, `repair-plan.schema.json` | Codex may emit only schema-bound plans; visual verdict remains independent | contract tests under `tests/` |
| Operating rules | `AGENTS.md`, `docs/AI_OPERATING_MODEL.md`, `docs/ARCHITECTURE.md` | Preserve one-writer, no custom transport, approval, and fail-closed rules | repository verifier and Reuse Declaration |

The future dossier must record the exact consumer, contract, test, and
acceptance gate for every selected API. If an existing owner is insufficient,
the gap must be stated before a new adapter is authorized.

## 5. External reuse and compatibility audit

Audit snapshot: 2026-08-06. The production repository remains dependency
unchanged. The S1 disposable environment recorded
`openai-codex==0.144.4`, `openai-codex-cli-bin==0.144.4`, and
`pydantic==2.13.4`. This is historical compatibility evidence only and is not
a planning-PR pin.

### 5.1 Primary: official OpenAI Codex Python SDK

Source: [`openai/codex/sdk/python`](https://github.com/openai/codex/tree/main/sdk/python),
the [official Codex SDK documentation](https://developers.openai.com/codex/sdk),
and the repository's [Apache-2.0 license](https://github.com/openai/codex/blob/main/LICENSE).
The observed historical runtime tag is `rust-v0.144.4` at
`632c07017ed17f00ca6d911b754683dee785af69`. The observed repository `main`
head during this audit was `57f42a81131ccf5933e7ec5dc659c381eeb5d72b`; a
future compatibility run must record the exact installed package, runtime,
repository revision, and generated schema revision it used.

The SDK is OpenAI-maintained, Apache-2.0 licensed, requires Python 3.10 or
later, and publishes a pinned Codex CLI runtime dependency. The official
interface provides local Codex lifecycle, thread start/resume, bounded turns,
sandbox selection, progress/result handling, and structured-output capability
as documented by the SDK. The source tree contains SDK tests and examples.

Classification: `SPIKE_ONLY` now; future `EXTEND_WITH_ADAPTER` only after the
compatibility matrix passes on the supported Windows/Python environment.

Benefits: highest API fit, official lifecycle ownership, no custom transport,
and a smaller CAD Agent surface. Costs: beta/API drift risk, a bundled native
CLI runtime, `pydantic` dependency cost, Windows packaging risk, and the need
to separate account/authentication from evidence logging. Security requires
least-privilege sandboxing, secret-free telemetry, no untrusted code sharing
the credential environment, and a disposable workspace for first runs.

Benchmark before promotion: clean client start/close, thread start/resume/fork,
one bounded turn, structured output, event capture, interrupt, timeout,
cleanup, workspace containment, and repeatability across two fresh disposable
environments. Record latency, output validity, event completeness, and process
cleanup. Rollback is removing the optional adapter and returning to advisory
offline behavior; existing CAD APIs remain unchanged.

### 5.2 Secondary: official Codex App Server

Source: [`openai/codex/codex-rs/app-server`](https://github.com/openai/codex/tree/main/codex-rs/app-server),
the [official App Server documentation](https://developers.openai.com/codex/app-server),
and the repository license above. The exact runtime revision and generated
JSON Schema bundle must be recorded by the future spike. The App Server is
official and Apache-2.0 licensed. It exposes JSON-RPC lifecycle primitives,
thread start/resume/fork, turn events, interrupt, approvals, and sandbox
configuration. Its wire framing, schema, and version behavior are owned by
the official runtime, not by CAD Agent.

Classification: `SPIKE_ONLY`; promote only for a named SDK gap reproduced by a
test. Direct protocol ownership is not a default architecture decision.

Benefits: the most complete lifecycle/event surface and a clear escape hatch
for missing SDK features. Costs: JSON-RPC protocol/version maintenance,
framing and backpressure handling, larger security surface, and more code that
could accidentally become a custom transport. WebSocket mode is experimental
and unsupported for production; the future adapter should prefer the official
SDK or local stdio only when a gap is proven.

Benchmark: the same lifecycle capability matrix as the SDK, plus malformed
message handling, event ordering, bounded queues, process ownership, and
cleanup. Rollback is disabling the App Server path and using the SDK or
disposable fallback.

### 5.3 Bounded fallback: official `codex exec --json`

Source: the [official Codex CLI non-interactive interface](https://developers.openai.com/codex/non-interactive-mode)
and the open-source repository license above. The compatibility run must record
the exact CLI version/revision. JSONL mode exposes thread,
turn, item, error, command, file-change, and final events, and the CLI supports
explicit read-only or workspace-write sandbox settings and schema-bound final
output.

Classification: `SPIKE_ONLY` and bounded compatibility fallback; never the
primary production transport for the closed loop.

Benefits: low integration cost for disposable probes and CI-style jobs. Costs:
process startup, weaker reusable-thread ergonomics than the SDK, parsing and
partial-stream handling, and fewer typed lifecycle guarantees. The fallback
must be disabled unless explicitly selected by a capability matrix and must
never silently widen permissions.

Benchmark: one disposable `--json` run, schema output, event completeness,
bounded timeout/cancel, explicit sandbox, no source writes, and deterministic
failure mapping. Rollback is removing the fallback selection; no CAD state is
dependent on it.

### 5.4 MCP

MCP is classified `SPIKE_ONLY` for interoperability or experiments. It is not
the production Codex worker transport in Wave 1A. A future MCP experiment must
have its own Issue, server allowlist, authentication/security review, data
boundary, and rollback.

## 6. Closed `vision-handoff` contract

The handoff is a closed object: unknown keys, missing required fields,
unrecognized enum values, non-canonical hashes, non-finite numbers, and
unbound paths fail validation. The future implementation must define a schema
version and canonical UTF-8 JSON hash. No contract file is added by this
planning PR.

### 6.1 Required identity and policy content

The contract must bind:

```text
schema_version
handoff_id / program_id / run_id / request_id
created_at / expires_at / single_use
source and accepted-base identities
drawing/Primitive IR/Semantic IR/evidence identities where present
component/view/region/sheet/entity scope
owner intent and engineering objective
confirmed/reference/derived/conflicting/unresolved dimensions
protected datums, geometry, dimensions, constraints, layers, blocks, handles
allowed operation classes
forbidden mutation classes
disposable workspace roots and write policy
expected output contract IDs and versions
required verification gates
approval reference and approval authority
handoff canonical hash
```

Every file identity includes a role, SHA-256, byte length when available,
revision identity when available, and immutable/read-only classification. A
path is a redacted reference, never a substitute for the hash. Source and
accepted CAD are always read-only. The first runtime slice permits writes only
inside an empty disposable candidate root.

### 6.2 Field ownership

Caller/PO supplies: intent, approved scope, source/evidence references,
protected constraints, allowed operation classes, forbidden operations,
expected output contract, acceptance gates, and approval reference.

CAD Agent/server supplies or verifies: handoff/request IDs, canonical
serialization and hash, creation/expiry timestamps, input hashes observed at
validation time, normalized scope, effective sandbox roots, lifecycle status,
event sequence, consumption state, stale/expiry decision, and cleanup result.

Codex never supplies authority fields. It may return only worker events and a
schema-bound output candidate. Any caller-provided field that conflicts with a
server-verified value is rejected rather than overwritten silently.

### 6.3 Lifecycle and stale evidence

The future lifecycle is:

```text
CREATED -> VALIDATED -> APPROVED -> RUNNING -> OUTPUT_VALIDATED -> CONSUMED
                  \-> REJECTED / EXPIRED / STALE / CANCELLED / FAILED
```

The exact status names may be frozen in the future schema, but the semantics
must remain closed. A handoff is stale when any bound source, accepted-base,
drawing revision, IR artifact, evidence artifact, scope, approval, or contract
version differs from the validated identity. Expired, stale, already-consumed,
or scope-incomplete handoffs cannot start or resume a turn. A fork must bind a
new handoff identity and cannot inherit approval silently.

## 7. Worker-control boundary

The future adapter exposes a stable CAD Agent seam while hiding provider
details. Exact SDK method names are resolved by the compatibility spike and
are not guessed in a planning-only change.

Conceptual operations:

```text
start_thread(validated_handoff, workspace_policy) -> thread_identity
resume_thread(thread_identity, validated_handoff) -> thread_identity
fork_thread(thread_identity, validated_handoff) -> thread_identity
run_bounded_turn(thread_identity, prompt, output_contract, limits) -> worker_result
steer_turn(thread_identity, steering_input) -> accepted_or_rejected
interrupt_turn(thread_identity) -> interrupt_result
cancel_turn(thread_identity) -> cancel_result
close_worker() -> cleanup_result
```

The adapter must not expose a generic unrestricted command runner or a CAD
mutation callback. It returns a normalized result containing thread/turn
identities, ordered redacted events, output status, schema-bound candidate,
usage metadata when safe, failure code, and cleanup status.

### 7.1 Bounded execution

Every turn has explicit limits for wall time, event count, event bytes, output
bytes, command count, and writable-root containment. Defaults are owned by
CAD Agent policy, not inferred from model output. A limit violation interrupts
the turn, records the limit failure, cleans up, and rejects the output.

### 7.2 Event capture and partial events

Events are captured in order with a local sequence number and provider event
type. The packet records only redacted metadata, hashes, sizes, status, and
safe summaries. It excludes API keys, auth tokens, private source bytes,
customer paths, raw prompts containing private data, and unrestricted model
reasoning.

Unknown event types, duplicate sequence numbers, sequence gaps, malformed
payloads, truncated streams, or a missing terminal event produce
`PARTIAL_EVENTS` or `INVALID_EVENTS` and no accepted output. Partial evidence
may be retained for diagnosis but cannot satisfy a gate.

### 7.3 Timeout, interrupt, cancellation, and cleanup

- Timeout sends the official interrupt/cancel operation when supported,
  records `TURN_TIMEOUT`, waits only within a second bounded cleanup budget,
  and rejects output.
- Explicit interrupt records `INTERRUPTED`; it never becomes a successful
  plan unless a later, fresh approved turn completes normally.
- Cancellation records `CANCELLED`, invalidates the turn, and prevents resume
  from treating a partial suffix as a completed plan.
- Cleanup closes the thread/client/process and verifies that no child runtime
  remains in the disposable process set. Cleanup failure is a separate
  `CLEANUP_FAILED` failure and blocks promotion.
- A failed cleanup never triggers an automatic retry with broader permissions.

### 7.4 Failure mapping

The normalized failure set must include at least:

```text
INVALID_HANDOFF, STALE_HANDOFF, EXPIRED_HANDOFF, REUSED_HANDOFF,
SDK_UNAVAILABLE, AUTH_UNAVAILABLE, THREAD_START_FAILED, THREAD_RESUME_FAILED,
THREAD_FORK_FAILED, TURN_FAILED, TURN_TIMEOUT, INTERRUPTED, CANCELLED,
EVENT_LIMIT, INVALID_EVENTS, PARTIAL_EVENTS, INVALID_OUTPUT,
SCHEMA_MISMATCH, WORKSPACE_VIOLATION, POLICY_DENIED, CLEANUP_FAILED
```

Unknown provider errors map to a closed `PROVIDER_FAILURE` record with the
provider code redacted/normalized. No error is converted into PASS or a
retry with wider scope.

## 8. Workspace, sandbox, and file authority

The first future runtime slice uses a disposable repository and an explicit
workspace root. The adapter must prove:

- source and accepted CAD roots are read-only and outside writable roots;
- the candidate root is canonical, empty or disposable, and containment-checked;
- the effective sandbox is read-only unless the test explicitly requires
  `workspace_write` inside the disposable root;
- absolute-path escapes, junction/reparse escapes, symlink escapes, and writes
  outside the approved root fail closed;
- AutoCAD executables, File IPC directories, customer paths, private fixtures,
  and credentials are not in the first runtime environment;
- no output file is published over an existing source or accepted artifact.

The official SDK owns process/auth/session lifecycle. CAD Agent owns the
allowlist, root containment, evidence identity, and post-run cleanup gate.

## 9. Schema-bound output and authority gate

Codex may return a drawing plan or repair plan only when:

- the declared schema ID/version is allowlisted by the validated handoff;
- required fields and no-extra-key rules pass;
- targets resolve to the handoff scope;
- operations are in the allowed operation class set;
- protected entities, datums, dimensions, layers, blocks, and constraints are
  not altered or deleted;
- expected input hashes and evidence identities remain fresh;
- the output contains no visual verdict, engineering approval, publish token,
  AutoCAD command, arbitrary path, or unrestricted code payload.

The existing `visual-review` contract remains the only visual-verdict carrier.
The existing `repair-plan` contract remains a bounded operation description
without PASS or publication authority. A future drawing-plan contract must be
separately reviewed if the existing contracts cannot express the need; it is
not invented in this PR.

Validation failure returns `INVALID_OUTPUT` or `SCHEMA_MISMATCH`, preserves the
redacted event packet for diagnosis, and performs no CAD or AutoCAD action.

## 10. First runtime slice and tests

The first implementation issue must start with a fake adapter and disposable
repository tests. It must not call a real model, authenticate against a
customer account, access private data, or mutate AutoCAD.

Required test groups:

1. Closed handoff validation: missing/extra fields, malformed hashes,
   conflicting identities, expired/stale/reused approvals, scope mismatch,
   forbidden operation, and canonical hash determinism.
2. Fake lifecycle: start, resume, fork, bounded turn, steering acceptance or
   rejection, interrupt, cancellation, timeout, cleanup, and failure mapping.
3. Event safety: ordering, duplicate/gap/unknown events, byte/event limits,
   partial streams, missing terminal event, redaction, and no-secret packets.
4. Workspace safety: allowed disposable write, source/accepted-root refusal,
   path escape refusal, existing-artifact no-overwrite, and cleanup.
5. Output safety: valid schema-bound plan, unknown schema, extra key, invalid
   operation, protected-target mutation, stale evidence, verdict/publication
   field, and invalid JSON.
6. Compatibility probe: package/runtime/platform metadata, exact versions and
   revisions, clean start/close, and all unavailable states represented as
   `SKIP`, `FAIL`, or `NOT RUN`, never as PASS.

The first runtime acceptance packet must show zero AutoCAD mutation and zero
private-data access. A real SDK/model test is a later gate requiring separate
authorization.

## 11. Compatibility matrix and pinning gate

Before any production dependency change, record this matrix for every tested
candidate:

| Field | Required value |
| --- | --- |
| Python | exact executable/version and supported Windows build |
| SDK | package name, exact version, source, wheel hash if available |
| CLI runtime | exact package/version and bundled executable identity |
| OpenAI repository | exact tag/commit and generated schema revision |
| License | license and attribution obligations |
| Platform | Windows/Python support and native runtime behavior |
| Tests | focused counts, lifecycle results, failures and skips |
| Security | auth boundary, sandbox, secret handling, process cleanup |
| Dependencies | direct/transitive packages, lock impact, deployment cost |
| Benchmark | latency, event completeness, structured-output validity, repeatability |
| Migration | enablement flag, staged rollout, evidence compatibility |
| Rollback | exact disable/revert path with existing CAD behavior preserved |

No package is pinned because a planning document says it is preferred. A
separate implementation issue must include the matrix, security review,
focused tests, hosted checks, and PO approval.

## 12. Telemetry and evidence packet

The future evidence packet may contain only:

```text
handoff/run/thread/turn identifiers
schema and adapter versions
source/evidence hashes and byte sizes
effective policy and sandbox class
event counts, types, sequence status, and timestamps
bounded usage/latency metadata
output schema/status/hash
failure and cleanup status
verification command identities and results
```

It must not contain API keys, bearer tokens, cookies, account identifiers,
private drawing bytes, source excerpts, customer absolute paths, unrestricted
prompts, raw chain-of-thought, or secret-bearing environment values. Redaction
failure is a gate failure.

## 13. Proposed future runtime allowlist

The following is a proposal for a later implementation Issue, not permission
to change these paths in Wave 1A:

### Candidate create paths

- `contracts/vision-handoff/vision-handoff.schema.json`
- `cad_agent/vision_handoff.py`
- `agent_lib/codex_worker.py`
- `agent_lib/tests/test_codex_worker.py`
- `tests/test_vision_handoff.py`
- one disposable compatibility probe under `scripts/`, if the existing S1
  probe cannot be extended without widening its scope.

### Candidate modify paths, only if the later Issue explicitly allows them

- `cad_agent/visual_contracts.py` for shared validation primitives only;
- `agent_lib/codex_sdk_compat.py` for compatibility metadata only;
- existing test registries or verifier wiring only when the later allowlist
  names the exact lines and the change is required for the new boundary.

### Do not modify

- `primitive_ir_lib`, `semantic_ir_lib`, `dxf_builder_lib` behavior;
- `agent_lib/advisor.py`, `batch_agent.py`, `models.py`, `run.py`, or
  `io_utils.py` authority behavior;
- existing manifests, checkpoints, registry/revision stores, repair executor,
  verdict, publisher, OCR, solver, or File IPC/.NET dispatcher;
- source CAD, accepted CAD, private data, dependencies, locks, workflows,
  `docs/STATUS.md`, and `docs/HANDOFF.md`;
- any Wave 1B or Wave 1C path.

## 14. Wave ownership and overlap matrix

| Area | Wave 1A | Wave 1B | Wave 1C |
| --- | --- | --- | --- |
| Planning docs | official vision/worker docs only | R1C docs only | no repository changes |
| Future runtime owner | handoff and Codex worker adapter | SourceBundle byte integrity/fusion | operator environment/live evidence |
| `agent_lib` worker-control paths | reserved to Wave 1A future Issue | forbidden | forbidden |
| SourceBundle/manifest fusion | consume existing references only | sole owner | read-only/fixture use only |
| AutoCAD/File IPC/source/accepted CAD | forbidden in first slice | forbidden | source/accepted immutable; disposable candidates only |
| STATUS/HANDOFF | forbidden | forbidden | forbidden |

If a future task needs a shared path outside this matrix, it stops and opens a
coordination decision before editing. No branch may silently take ownership
from another wave.

## 15. Migration and rollback

Migration proceeds in gates:

1. planning-only documents and reuse dossier;
2. fake adapter and contract tests;
3. disposable external SDK compatibility matrix;
4. hosted synthetic worker-control checks with no real CAD;
5. disposable candidate flow with read-only CAD evidence;
6. only later, separately authorized live/private/model gates.

The adapter remains optional and fail-closed when the SDK, runtime, platform,
auth, schema, or workspace policy is unavailable. Disablement returns the
existing deterministic/advisory behavior; it does not route around approvals.
Rollback removes the adapter/configuration and reverts its bounded commits.
No source, accepted drawing, manifest authority, or existing executor depends
on the worker adapter for readability or safety.

## 16. Acceptance criteria for Issue #70

Issue #70 is complete only when:

- the final diff contains exactly the two allowlisted planning documents;
- the SDK-first decision and App Server/CLI/MCP alternatives are explicit;
- internal and official external reuse audits record exact owners, APIs,
  revisions, licenses, maintenance, platform, tests, security, dependencies,
  benchmark, migration, and rollback;
- handoff ownership, hashes, scope, protected constraints, approval, expiry,
  stale rejection, and no-extra-key behavior are testable in the future;
- worker lifecycle, events, steering, interrupt, timeout, cancel, cleanup,
  partial events, invalid output, and fail-closed mapping are specified;
- sandbox, disposable repository, no-real-model, and no-AutoCAD-first-slice
  boundaries are explicit;
- proposed future create/modify/do-not-modify paths and the Wave 1B/Wave 1C
  overlap matrix are present;
- no runtime, dependency, model, private-data, or AutoCAD gate is described as
  run or passed by this planning PR;
- focused documentation/reuse checks, canonical verifier, hosted checks, and
  Reuse Declaration checks are run on the final exact head;
- a draft PR is opened and left open for PO re-review.
