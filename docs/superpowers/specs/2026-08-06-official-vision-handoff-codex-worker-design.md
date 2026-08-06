# Official Vision Handoff and Codex Worker Control Design

Status: planning design under Issue #70. This document authorizes design and
future planning only. It does not authorize runtime code, dependencies, model
calls, private-data use, AutoCAD, File IPC, publication, or production turns.

Date: 2026-08-06

Issue: #70 — Wave 1A official vision handoff and Codex worker control.

Exact planning base: `d71d0c97e28e03cb430f05589c8381b4ede70e66`.

Planning branch: `planning/w1a-official-vision-codex-worker`.

Planning allowlist: this file and
`docs/superpowers/plans/2026-08-06-official-vision-handoff-codex-worker.md`
only.

## 1. Decision summary

Wave 1A selects an **SDK-first thin adapter**:

1. The official OpenAI Codex Python SDK is the primary worker-control
   interface after a separate compatibility and security gate.
2. Direct Codex App Server use is permitted only for a named SDK capability
   gap reproduced against an exact version and approved by the Master PO.
3. `codex exec --json` is a bounded disposable compatibility fallback only.
4. MCP and third-party bridges remain experimental/interoperability-only and
   are not production transports.

The authority path is:

```text
ChatGPT/PO approved vision and evidence
  -> closed, hash-bound vision-handoff
  -> CAD Agent identity, policy, approval, freshness, and schema validation
  -> isolated official Codex worker process
  -> schema-bound drawing/repair-plan candidate and redacted events
  -> CAD Agent local validation against the same immutable schema snapshot
  -> existing approval gates
  -> later deterministic CAD/AutoCAD boundaries under separate authorization
```

Codex is an untrusted bounded worker. It has no visual PASS, CAD truth,
engineering approval, AutoCAD mutation, repair-application, publication, or
scope-expansion authority.

## 2. Scope and locks

### 2.1 Future implementation scope proposed by this design

- A closed `vision-handoff` contract with canonical identity and hash.
- Source, accepted-base, IR, evidence, revision, scope, and approval binding.
- Protected constraints and explicit allowed/forbidden operation classes.
- Immutable output-schema bytes, canonical SHA-256, and validator-version
  binding with TOCTOU protection.
- A provider-independent worker interface backed by the official SDK.
- Thread start/resume/fork, bounded turns, events, steering when supported,
  interrupt, normalized local cancellation, timeout, and cleanup.
- A sanitized worker subprocess with an allowlisted environment, isolated
  disposable `CODEX_HOME`, controlled cwd, and attested instruction sources.
- Explicit deny-all provider approvals and non-experimental SDK initialization.
- Read-only-by-default sandboxing and disposable workspace-write tests only.
- Schema-bound drawing/repair-plan output and fail-closed validation.
- Windows process-tree supervision and cleanup evidence.
- Compatibility, dependency, telemetry/privacy, migration, and rollback gates.

### 2.2 Explicit non-goals

This planning PR does not authorize:

- a production SDK pin or lock-file change;
- a real model turn, authentication change, customer/private-data run, or
  production credential use;
- AutoCAD, File IPC, source CAD, accepted CAD, or publication mutation;
- a new OCR engine, semantic solver, DXF/DWG writer, dispatcher, gateway,
  manifest/checkpoint store, registry, revision store, repair executor,
  verdict authority, publisher, or custom transport;
- direct App Server use without a proven SDK gap;
- `Sandbox.full_access`, provider auto-review, experimental APIs, inherited
  MCP servers, inherited writable roots, or unsafe CLI bypass flags;
- caller-selected schema paths, mutable schema references, or provider-selected
  validators;
- modification of `STATUS.md`, `HANDOFF.md`, workflows, tests, runtime code, or
  dependencies in Issue #70.

The first future runtime slice remains fake/disposable, no-real-model, and
non-AutoCAD.

## 3. Authority and trust model

### 3.1 Owner and Master PO

The owner supplies engineering truth and approves private inputs or high-risk
operations. The Master PO owns roadmap, scope, acceptance, and merge. ChatGPT
may materialize approved intent but may not invent measurements, live results,
security guarantees, or publication authority.

### 3.2 CAD Agent

CAD Agent owns:

- handoff creation and canonical serialization;
- server-observed hashes and identity binding;
- scope, protected constraints, and operation policy;
- approval references, expiry, single-use, and stale rejection;
- immutable output-schema snapshot, canonical hash, and validator identity;
- effective workspace and sandbox policy;
- provider configuration and instruction-source attestation;
- output validation, evidence packets, and failure mapping;
- routing to existing deterministic executors only after later approvals.

`cad_agent.manifest` and `cad_agent.visual_evidence` remain the verified
manifest/source/evidence identity owners. No exact `cad_agent.checkpoint`
module was resolved at the accepted base, so this design does not claim one.
Checkpoint/resume ownership must be tied to an exact path and symbol in a
future implementation Issue before reuse is asserted.

### 3.3 Codex worker

Codex owns only bounded provider execution and may return:

- provider thread/turn identifiers;
- ordered redacted events;
- one schema-bound drawing/repair-plan candidate;
- normalized usage/latency metadata when safe;
- provider failure information after redaction.

Provider output remains untrusted until all CAD Agent gates pass. A provider
event, message, command result, approval callback, schema path, validator
claim, or thread history never becomes engineering truth by itself.

### 3.4 Existing CAD authorities

`primitive_ir_lib`, `semantic_ir_lib`, `agent_lib`, `dxf_builder_lib`,
`mcp_integration_lib`, existing visual contracts, File IPC/.NET, and AutoCAD
evidence retain their current responsibilities. Wave 1A must not duplicate or
silently bypass them.

## 4. Internal reuse dossier

| Capability | Existing owner/API | Classification | Required use/evidence |
| --- | --- | --- | --- |
| Advisory proposal | `agent_lib.batch_agent.run_agent` | `REUSE_AS_IS` | Worker output remains advisory; tests in `agent_lib/tests/test_batch_agent.py` and `test_run.py` |
| Separate application | `agent_lib.batch_agent.apply_agent_report` | `REUSE_AS_IS` | Provider events can never call apply directly |
| Hash-bound approval | `agent_lib.run._validate_agent_action_approval`, `_apply_report_with_approval` | `REUSE_AS_IS` | Preserve literal approval, report hash, and input hashes; extend `agent_lib/tests/test_run.py` |
| Auditable actions/evidence | `agent_lib.models.AgentReport`, `AgentTask`, `AgentAction`, `Evidence` | `EXTEND_WITH_ADAPTER` | Reuse action/evidence identity patterns; no second action authority |
| Deterministic report I/O | `agent_lib.io_utils.save_document`, `load_agent_report` | `EXTEND_WITH_ADAPTER` | Reuse canonical UTF-8/hash patterns |
| Historical SDK evidence | `agent_lib.codex_sdk_compat`, `scripts/probe_codex_sdk_windows.py` | `EXTEND_WITH_TEST` | Optional/lazy/fail-closed; not a production turn runner |
| SDK tests | `agent_lib/tests/test_codex_sdk_compat.py` | `EXTEND_WITH_TEST` | Preserve missing/malformed/unapproved runtime and no-auth/no-model assertions |
| Manifest/source identity | `cad_agent.manifest` | `EXTEND_WITH_ADAPTER` | Reuse conflict refusal, source binding, atomic persistence, and hash checks |
| Fresh evidence | `cad_agent.visual_evidence` | `EXTEND_WITH_ADAPTER` | Reuse exact-byte snapshots, reparse-point refusal, freshness, and no-change checks |
| Closed validation | `cad_agent.visual_contracts.validate_visual_contract` | `EXTEND_WITH_ADAPTER` | Reuse no-extra-key, identifier, SHA-256, finite-value, and policy checks |
| Existing repair plan | `contracts/visual-supervisor/repair-plan.schema.json` | `REUSE_AS_IS` | Snapshot exact canonical schema bytes; validate bounded operations; no PASS/publication authority |
| Custom Codex transport | none approved | `REJECT` | Do not build |
| MCP primary transport | not approved | `REJECT` | Experimental/interoperability only |

Every future runtime Issue must name exact paths, symbols, tests, consumers, and
acceptance gates. An unresolved owner is recorded as unresolved, not invented.

## 5. Official external reuse audit

Audit snapshot: 2026-08-06.

Official source baseline: `openai/codex@57f42a81131ccf5933e7ec5dc659c381eeb5d72b`,
Apache-2.0. Historical S1 evidence used `openai-codex==0.144.4`,
`openai-codex-cli-bin==0.144.4`, and `pydantic==2.13.4`; the historical
`rust-v0.144.4` release commit is
`8c68d4c87dc54d38861f5114e920c3de2efa5876`, while
`632c07017ed17f00ca6d911b754683dee785af69` is the annotated tag object.
These values are evidence only, not a production pin.

### 5.1 Official Python SDK — selected primary

Classification: `SPIKE_ONLY` now; future `EXTEND_WITH_ADAPTER` only after the
compatibility/security matrix passes.

The audited public API exposes typed thread start/resume/fork, structured
output, event streaming, steering, and interrupt. The audited defaults also
create security obligations:

- thread start defaults to `ApprovalMode.auto_review`;
- `CodexConfig.experimental_api` defaults to `True`;
- the local app-server process is launched from `os.environ.copy()` plus
  overrides;
- existing Codex authentication/configuration may be reused;
- sandbox presets do not independently prove exact writable-root containment;
- SDK close handles the direct app-server process but does not by itself prove
  descendant process-tree cleanup;
- no distinct public provider cancel method was established in the audited API.

Therefore the future adapter must explicitly set deny-all approvals, disable
experimental APIs, run the SDK inside a sanitized supervised worker process,
and prove effective policy and process cleanup.

Structured-output support does not transfer schema authority to the provider.
CAD Agent must pass an immutable canonical schema snapshot and validate the
result locally against the same bytes and hash.

### 5.2 Direct App Server — secondary only

Classification: `SPIKE_ONLY` for a named SDK gap.

Direct App Server use must be local disposable stdio only and version-bound to
the tested runtime and generated schemas. The following remain forbidden:

- WebSocket, remote, or unix listeners;
- direct command-execution surfaces;
- experimental process spawning;
- direct MCP invocation;
- full-access sandboxing;
- remote code-mode hosts;
- unrelated experimental APIs.

A missing SDK evidence surface is a named gap, not automatic App Server
authorization. A separate PO amendment is required.

### 5.3 `codex exec --json` — bounded fallback

Classification: `SPIKE_ONLY` disposable compatibility fallback.

Any future invocation must require:

```text
--ephemeral
--ignore-user-config
--strict-config
explicit read-only sandbox
exact --output-schema pointing to the immutable run-scoped schema snapshot
```

It must forbid:

```text
--dangerously-bypass-approvals-and-sandbox
--ignore-rules
--skip-git-repo-check
--last
caller-selected arbitrary sessions
```

JSONL processing must discard or redact raw reasoning, prompts, private source
bytes, customer paths, secret-bearing command output, tokens, and credentials.
Timeout/cancellation is process-level and must not be reported as SDK
interrupt semantics.

### 5.4 MCP and third-party bridges

Classification: `REJECT` as Wave 1A production transport. A future experiment
requires its own Issue, authentication/data-boundary review, allowlist, and
rollback.

## 6. Closed `vision-handoff`

The contract is a closed object. Unknown keys, missing required fields,
unknown enums, non-canonical hashes, non-finite values, conflicting identities,
unbound paths, caller/provider authority fields, or mutable schema references
fail validation.

### 6.1 Required content

```text
schema_version
handoff_id / program_id / run_id / request_id
created_at / expires_at / single_use
source and accepted-base identities
IR, drawing, evidence, and revision identities when present
component/view/region/sheet/entity scope
owner intent and engineering objective
confirmed/reference/derived/conflicting/unresolved dimensions
protected datums, geometry, dimensions, constraints, layers, blocks, handles
allowed operation classes
forbidden mutation classes
disposable workspace roots and write policy
output_schema_id
output_schema_version
output_schema_sha256
output_validator_version
required verification gates
approval reference and authority
instruction-source identities
provider/model/config identity requirements
handoff canonical hash
```

Each file identity includes role, SHA-256, byte length when available,
revision identity when available, and immutable/read-only classification. A
path reference never substitutes for a hash.

The output schema fields are server-owned. Before the turn, CAD Agent resolves
an allowlisted contract, canonicalizes its exact bytes, computes
`output_schema_sha256`, records `output_validator_version`, and stores an
immutable run-scoped snapshot. That exact snapshot—not a later path lookup—is
passed to the SDK/App Server/CLI and reused for local output validation.

### 6.2 Field ownership

Caller/PO may supply approved intent, scope proposals, evidence references,
protected constraints, allowed/forbidden operations, expected output contract
intent, acceptance gates, and approval reference.

CAD Agent creates or verifies all authority fields: canonical IDs/hash,
creation/expiry, observed input hashes, normalized scope, immutable schema
snapshot/hash/validator version, effective workspace, provider policy,
instruction-source list, consumption state, and cleanup result. Conflicting
caller values are rejected rather than silently replaced.

Codex may never supply or modify authority fields.

### 6.3 Lifecycle and thread binding

```text
CREATED -> VALIDATED -> APPROVED -> RUNNING -> OUTPUT_VALIDATED -> CONSUMED
                  \-> REJECTED / EXPIRED / STALE / CANCELLED / FAILED
```

Start/resume/fork requires a server-owned binding across:

```text
handoff_id + handoff_hash + run_id + thread_id + adapter_version
+ model/config identity + instruction-source identity + sandbox policy
+ output_schema_sha256 + output_validator_version
```

A caller-supplied thread ID alone is never sufficient. Resume/fork must reject
foreign or stale history and reapply deny-all approval, controlled cwd,
explicit sandbox, effective-policy attestation, and the immutable output
schema binding. Fork creates a new handoff and approval. First real probes are
ephemeral.

## 7. Worker-control boundary

Conceptual provider-independent API:

```text
start_thread(validated_handoff, worker_policy) -> thread_identity
resume_thread(bound_thread_identity, validated_handoff) -> thread_identity
fork_thread(bound_thread_identity, new_validated_handoff) -> thread_identity
run_bounded_turn(thread_identity, prompt_ref, schema_snapshot, limits) -> worker_result
steer_turn(thread_identity, steering_input) -> accepted_or_rejected
interrupt_turn(thread_identity) -> interrupt_result
cancel_turn(thread_identity) -> normalized_cancel_result
close_worker() -> cleanup_result
```

`cancel_turn` is a CAD Agent normalized local operation, not a claimed distinct
provider primitive:

```text
mark CANCELLED -> send official interrupt -> reject all partial/final output
-> bounded cleanup -> process-tree verification
```

Every start/resume/fork/turn must explicitly apply:

- `ApprovalMode.deny_all`;
- `experimental_api=False`;
- controlled cwd and isolated `CODEX_HOME`;
- explicit sandbox and no inherited writable roots;
- exact model/config/instruction identity;
- immutable output-schema bytes/hash and validator version;
- wall-time, event-count, event-byte, output-byte, and command-count limits.

No provider-side review, permission request, automatic approval, schema path,
or validator claim may satisfy CAD Agent approval or validation.

## 8. Environment, authentication, instructions, and sandbox

Before any real SDK turn, CAD Agent must launch a dedicated worker subprocess
whose environment is constructed from an allowlist, not the user session.
The SDK's child app-server then inherits only that sanitized environment.

The gate must:

- exclude unrelated API keys, tokens, proxy credentials, cookies, telemetry
  configuration, MCP servers, and writable roots;
- use a fresh disposable `CODEX_HOME` and controlled configuration;
- use a controlled cwd and disposable repository;
- bind and hash the effective global/project instruction-source list;
- reject unexpected `AGENTS.md`, user rules, project rules, or configuration;
- keep private/customer prompts and files out of the first slices;
- record account mode and authentication source without logging secrets.

If the SDK cannot expose sufficient effective-policy or instruction-source
evidence, record a named SDK gap and stop. Do not silently widen permissions or
switch to App Server.

Sandbox rules:

- `Sandbox.full_access` is forbidden in Wave 1A;
- real compatibility probes default to `read_only`;
- `workspace_write` is tested only in an empty disposable root;
- no inherited writable roots are permitted;
- effective policy is re-attested after resume/fork and before each turn;
- source and accepted CAD are always outside writable roots;
- path traversal, symlink, junction, and reparse-point escapes fail closed;
- existing artifacts and schema snapshots are never overwritten.

## 9. Events, failures, and cleanup

Events are ordered with local sequence numbers and redacted before storage.
Unknown types, duplicates, gaps, malformed payloads, truncated streams,
missing terminal events, or output after interrupt/cancel/timeout produce no
accepted plan.

Minimum normalized failures:

```text
INVALID_HANDOFF, STALE_HANDOFF, EXPIRED_HANDOFF, REUSED_HANDOFF,
SDK_UNAVAILABLE, AUTH_UNAVAILABLE, INSTRUCTION_SOURCE_MISMATCH,
PROVIDER_POLICY_MISMATCH, THREAD_START_FAILED, THREAD_RESUME_FAILED,
THREAD_FORK_FAILED, TURN_FAILED, TURN_TIMEOUT, INTERRUPTED, CANCELLED,
EVENT_LIMIT, INVALID_EVENTS, PARTIAL_EVENTS, INVALID_OUTPUT,
SCHEMA_MISMATCH, WORKSPACE_VIOLATION, POLICY_DENIED, CLEANUP_FAILED,
PROVIDER_FAILURE
```

Cleanup uses a bounded Windows process-tree supervisor, preferably a disposable
Job Object or equivalent tested mechanism. SDK `close()` alone is not cleanup
proof. Any surviving descendant process produces `CLEANUP_FAILED` and blocks
promotion. No failure triggers broader permissions or an automatic retry.

## 10. Immutable schema-bound output

Before a turn, CAD Agent must:

1. resolve the allowlisted output schema by server-owned registry identity;
2. read and canonicalize the exact schema bytes once;
3. calculate and bind `output_schema_sha256`;
4. bind `output_schema_id`, `output_schema_version`, and
   `output_validator_version`;
5. persist an immutable run-scoped schema snapshot;
6. pass those exact bytes to the provider;
7. locally validate returned output against the same snapshot and validator.

A worker plan is accepted only when:

- schema ID/version/hash/validator match the handoff binding;
- the immutable snapshot is unchanged from pre-turn through local validation;
- required/no-extra-key validation passes;
- targets resolve to handoff scope;
- operations are allowed and protected targets are unchanged;
- all hashes, evidence, approval, provider policy, and instruction identities
  remain fresh;
- no visual verdict, engineering approval, publication token, arbitrary path,
  AutoCAD command, unrestricted code payload, or provider authority field is
  present;
- the terminal event is complete and cleanup succeeds.

The following fail as `SCHEMA_MISMATCH` with no executor call:

- same schema ID/version but changed bytes;
- changed canonicalization result;
- mutable schema path or symlink/reparse replacement;
- schema file replacement between provider invocation and local validation;
- validator-version drift;
- provider output validated against different bytes than those passed to the
  provider;
- TOCTOU mutation of the schema snapshot or registry target.

Existing `repair-plan` validation is reused. A new drawing-plan contract, if
needed, requires a separate contract review. Invalid output performs no
executor, CAD, File IPC, or AutoCAD action.

## 11. Compatibility and dependency gate

Before any production dependency change, record:

| Field | Required evidence |
| --- | --- |
| Python/Windows | exact executable, version, OS build, and architecture |
| SDK/runtime | package, version, wheel/runtime hash, source tag/commit |
| Generated schemas | exact provider schema revision and compatibility result |
| Output contract | exact canonical bytes/hash and local validator version |
| Approval | explicit deny-all on start/resume/fork/turn |
| Experimental API | explicitly disabled |
| Environment | allowlisted variables and isolated `CODEX_HOME` |
| Instructions | exact source list and hashes |
| Sandbox | explicit effective policy and no inherited writable roots |
| Lifecycle | start/resume/fork/stream/steer/interrupt/local-cancel |
| Cleanup | Windows process-tree evidence with no surviving descendants |
| Security | auth boundary, secrets, telemetry, process and file authority |
| Dependencies | direct/transitive packages, lock and deployment cost |
| Benchmark | latency, event completeness, output validity, repeatability |
| Migration/rollback | enablement flag and exact disable/revert path |

No package is pinned by this planning PR. App Server and CLI fallback remain
`NOT RUN` unless a named need exists.

## 12. Telemetry and privacy gate

Local evidence redaction is separate from upstream service, account,
compliance, or OpenTelemetry behavior. Before any private-data or real-model
gate, record and approve:

- account/authentication mode;
- client identity;
- telemetry and compliance configuration;
- data classification;
- prompt/tool/file transmission assumptions;
- retention and access assumptions;
- local evidence fields and redaction tests.

Private data remains `NOT RUN` until this review is accepted. Evidence packets
must exclude secrets, raw chain-of-thought, raw private prompts/files, customer
absolute paths, unrestricted command output, and secret-bearing environment
values.

## 13. Proposed future runtime allowlist

This is a proposal, not authorization.

### Candidate create paths

- `contracts/vision-handoff/vision-handoff.schema.json`
- `cad_agent/vision_handoff.py`
- `agent_lib/codex_worker.py`
- `agent_lib/codex_worker_process.py`
- `agent_lib/tests/test_codex_worker.py`
- `agent_lib/tests/test_codex_worker_events.py`
- `tests/test_vision_handoff.py`
- `tests/test_vision_handoff_contract.py`
- `tests/test_vision_handoff_workspace.py`
- `tests/test_codex_worker_output.py`

### Candidate modify paths only when separately authorized

- `agent_lib/codex_sdk_compat.py` for compatibility metadata only;
- `cad_agent/visual_contracts.py` for shared validation primitives only;
- an existing verifier registry when exact lines and necessity are approved.

### Do not modify

- existing proposal/apply authority;
- Primitive/Semantic IR, DXF/DWG, File IPC/.NET, AutoCAD behavior;
- SourceBundle/fusion, registry, revision, repair executor, verdict, publisher;
- dependencies, lock files, workflows, `STATUS.md`, or `HANDOFF.md`;
- source CAD, accepted CAD, private data, or another wave's paths.

## 14. One-writer overlap matrix

| Area | Wave 1A | Wave 1B | Wave 1C |
| --- | --- | --- | --- |
| Planning docs | official handoff/worker docs only | R1C docs only | no repository writes |
| Future runtime | handoff, isolated Codex worker, output validation | source integrity/fusion | live environment/evidence only by default |
| `agent_lib` worker paths | sole owner after runtime authorization | forbidden | forbidden |
| SourceBundle/fusion | consume identities only | sole owner | read-only fixture use |
| AutoCAD/File IPC | forbidden in first slice | forbidden | disposable candidate/live evidence only |
| `STATUS.md`/`HANDOFF.md` | forbidden | forbidden | forbidden |

Any shared-path need stops for a coordination amendment before editing.

## 15. Migration and rollback

Migration gates:

1. planning and red-team acceptance;
2. closed contract and fake worker tests;
3. isolated subprocess, deny-all, sandbox, schema snapshot, and process-tree
   tests;
4. disposable SDK compatibility matrix with no private data or AutoCAD;
5. schema-bound synthetic plan validation against immutable bytes;
6. separately authorized real-model and later CAD gates.

Rollback disables/removes the optional worker adapter and returns to existing
deterministic/advisory behavior. Existing CAD data, manifests, IR, contracts,
and executors remain readable and unchanged. No provider state is required to
recover project truth.

## 16. Issue #70 acceptance criteria

Issue #70 planning is acceptable only when:

- final diff contains exactly the two planning documents;
- SDK-first architecture and alternatives are explicit;
- internal/external reuse owners are exact or explicitly unresolved;
- deny-all approval, disabled experimental API, isolated environment,
  instruction attestation, sandbox re-attestation, thread binding, normalized
  cancellation, process-tree cleanup, CLI/App Server hardening, and telemetry
  review are specified;
- server-owned schema ID/version/hash/validator binding, immutable schema
  snapshot, same-bytes provider/local validation, schema-drift/TOCTOU refusal,
  and focused tests are explicit;
- first slice remains fake/disposable, no-real-model, no-private-data, and
  non-AutoCAD;
- runtime create/modify/do-not-modify paths and overlap matrix are explicit;
- focused docs/reuse checks, exact allowlist audit, hosted tests, and Reuse
  Declaration pass on the final exact head;
- PR remains draft for Cell 4 re-review and Master PO acceptance.
