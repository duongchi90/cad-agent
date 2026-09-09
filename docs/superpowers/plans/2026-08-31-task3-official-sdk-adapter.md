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
- PR #334 merged normally at `cac069c45ea44ae09bd1c2062476b0febb4a37cb`.
  Its exact implementation head was
  `42bdf11e256c7b68018962fbcab9142e3798074c`.
- Hosted checks/reuse and the canonical verifier passed before merge. PR #332
  remains OPEN/DRAFT/evidence-only and was not changed or merged.
- No live AutoCAD, NETLOAD, M2 replay, or R5/R6 mutation is part of Task3
  verification. After integration, the next boundary is one fresh disposable
  provider-backed M3 LINE epoch with a new provider thread. The current
  machine has no running AutoCAD/FileIPC receiver, so that epoch is not run.

## Task3 authenticated CODEX_HOME custody successor

- Status: **Executing** under Issue #336, successor to the closed adapter
  boundary. Exact base is current `main` `e8386342d4a7bdab7ee12eb7b163f573e6b2df02`;
  implementation branch is `codex/task3-auth-custody-gap`.
- Measurement-first result: the existing `prepare_worker_environment` owner
  created a fresh root
  `C:\temp\cad-agent-m3-auth-custody-20260831-01` with exact home
  `...\codex-home`. Official `codex-cli 0.144.4` login status returned exit
  `0` using ChatGPT. The privacy-safe post-login home inventory contained
  `9` entries, `5` files, `4244` bytes, and no `config.toml`, `.env`,
  instruction/AGENTS file, plugin/marketplace, MCP configuration, or
  reparse/symlink entry. Credential contents and credential-derived content
  hashes were not read or recorded in public evidence; private in-memory
  hashes are used only for pre-launch drift detection.
- The bounded repair is on commits `9b73656dcc805bae6df837b11bc7f3536596662f`,
  `ff4ebb3ed60cc41b1eeeebcc75366513a91a030f`, and
  `799260177ba3b3f0449f4982968b9136daca093f`, plus repair
  `f7f1038f7ad81c5ef3758dc6251df817a536cd13`. It adds a server-issued,
  immutable privacy-safe home manifest, exact executable hash/version and
  observed official login-status binding, canonical Task3 authenticated start,
  one-shot consumption, fail-closed path/ambient/reparse/drift checks, and
  exact-home credential-state purge coupled to zero-survivor cleanup. No
  credential bytes enter environment, control frames, handoff, or evidence.
- Focused custody/worker/policy verification passed `177` tests. The final
  canonical verifier on `f7f1038` passed the offline gate with `3067 passed`,
  `18 deselected`, `72 subtests`, dotnet IPC `117/0/0`, real-data `2 skipped`,
  and AutoCAD unavailable `14 skipped`; the intentional causal RED probe was
  recorded as expected failure. `M2_RETEST=NO` and `NETLOAD_REQUIRED=NO`.
- Remaining boundary: obtain a NEW exact authenticated home and use it through
  canonical Task3 start to obtain genuine pre-R5 provider-backed evidence
  before any M3 mutation. Every authenticated home must be purged and never
  reused after its attempt.

## Executable-role repair after first authenticated attempt

- The first fresh same-home login succeeded, but canonical Task3 START failed
  before child creation with `WORKER_AUTHORITY_MISMATCH`. The failure was a
  real causal boundary, not provider evidence: custody attested the official
  `codex.exe`, while `Task3ProcessBoundary` launches the trusted Python child.
  The process owner incorrectly compared those two executable roles.
- RED: a focused test using distinct provider and child-launcher files failed
  with `WORKER_EXECUTABLE_IDENTITY_MISMATCH` on the old validator. GREEN:
  commit `f7f1038f7ad81c5ef3758dc6251df817a536cd13` revalidates the custody
  provider path/hash separately and validates the child launcher through the
  existing launch owner. Focused suite: `177 passed`.
- Canonical verifier on `f7f1038` passed exit `0`: `3067` offline tests,
  `117/0/0` dotnet IPC, expected causal RED, and no live AutoCAD/M2 gate.
- The authenticated root was purged after the failed attempt and is not
  reusable. After hosted exact-head GREEN, prepare a NEW home and require one
  new direct official login before a genuine provider-backed pre-R5 turn.

## Follow-up execution note (2026-08-31)

PR #337 is hosted-green at the previous exact head
`4df15664cfdcbe40ab378b2ca92976e3a08fe65a`; head `f7f1038` needs fresh
hosted checks and remains DRAFT/unmerged until the provider-backed pre-R5
boundary is genuine. The latest same-home login succeeded, but canonical
start exposed an executable-role mismatch before child creation: official
`codex.exe` custody was compared with the trusted Python launcher. It is
explicitly non-evidence; the exact root was purged. The distinct-role RED test
and minimal GREEN repair are on `f7f1038`.

The prepared packet `C:\temp\prepare_and_run_m3_auth.py` issues a NEW exact
path with `cwd == disposable_root`, keeps the auth attestation in-process
across official login/status and canonical Task3 START plus one provider turn.
The prior authenticated home is not reusable. No credential bytes were
copied, read, or emitted; `M2_RETEST=NO` and `NETLOAD_REQUIRED=NO`.
