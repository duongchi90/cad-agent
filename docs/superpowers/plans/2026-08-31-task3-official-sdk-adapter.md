# M3 Task3 official SDK adapter and two-phase start binding

## Boundary

Issue #333 closes the refined Task3 gap identified by #301 and #311: the
canonical child must start the official provider before the server can bind a
provider thread identity. This is a START_ONLY successor. Resume and fork are
not part of this plan and remain fail-closed.

The implementation uses only the existing Task3 process owner,
`LazyOfficialSdkAdapter`, request/result validation, and cleanup path. It does
not add a provider service, transport, queue, store, retry daemon, result
schema, or any AutoCAD/FileIPC/plugin/R5/R6 behavior.

## Contract

1. Validate server-owned handoff, authority, disposable root/cwd, model,
   approval, sandbox maximum, schema, and expected instruction sources before
   launching the child.
2. Launch the canonical child without a provider thread ID.
3. Inside the child, use the low-level official `openai-codex` 0.144.4
   `CodexClient.thread_start` seam with explicit `approvalPolicy=never`, exact
   model/provider/cwd, `workspace-write` request, and ephemeral start.
4. Normalize only typed provider-returned start facts. Bind the immutable
   `BoundWorkerThread` and worker context from the provider-generated ID after
   start succeeds.
5. Revalidate the observed provider policy and exact instruction-source
   mapping before accepting the binding. A stricter provider `readOnly` policy
   is valid; any authority widening or ambiguous source mapping is not.
6. Keep request/server custody separate from provider observation. In
   particular, config hash, experimental API mode, schema/hash/validator, and
   authority source IDs/roles are not provider-observed fields unless the
   official response actually supplies them.

## RED/GREEN evidence

- Causal RED before implementation:
  `test_two_phase_provider_start_binding_surface_is_present` and
  `test_start_codex_worker_does_not_accept_a_prebound_provider_thread` failed
  against the prior implementation. The canonical path lacked the binding
  seam and exposed the pre-bound `binding` start parameter.
- Focused GREEN: the Task3 binding suite, worker suite, and instruction-policy
  suite passed `128` tests. Adversarial coverage includes provider ID binding,
  missing/extra observation fields, policy and sandbox drift, source path
  escape, reparse/symlink, hash drift, duplicate ambiguity, and cleanup.
- Nearest offline regression passed `3059` tests with `18` deselected and
  `72` subtests. The existing Task6 event suite passed `161` tests after a
  compatibility-only fallback for legacy test seams; no owner contract was
  widened.

## Isolated official runtime evidence

The approved disposable environment contained exactly `openai-codex 0.144.4`.
The direct low-level start and the complete host-side bind both succeeded in
fresh disposable CODEX_HOME directories with parent API keys, auth files,
profiles, and session tokens excluded. The normalized provider facts included:

- provider-generated thread IDs used as the bound/session identity;
- model `gpt-5`, provider `openai`, and the exact disposable cwd;
- approval policy `never` and reviewer `user`;
- no-network effective `readOnly` sandbox with no writable roots;
- one canonical instruction-source path whose actual bytes matched the one
  expected authority SHA-256;
- no `config_sha256` in provider observation.

The first negative real probe used an authority model not returned by the
provider and was rejected as a policy mismatch. This confirms the binding
does not promote caller claims. The successful bind result was then cleaned
up; it was not reused for a later candidate or epoch.

## Current integration state

- Base: current `main` at `b06e533bbcbe7221e7c3ad9234e8497f9b422ec8`.
- Implementation branch: `runtime/m3-task3-two-phase-start`.
- PR #332 remains DRAFT and unmerged; this plan does not add code to it.
- Candidate implementation head before the documentation commit:
  `96479e1c08df3d7ccf3c39a8b9f7ded563b44261`.
- The canonical verifier must pass on the final exact head, followed by
  hosted checks/reuse and a fresh governance read before merge.
- No live AutoCAD, NETLOAD, M2 replay, or R5/R6 mutation is part of Task3
  verification. After integration, the next boundary is one fresh disposable
  provider-backed M3 LINE epoch with a new provider thread.
