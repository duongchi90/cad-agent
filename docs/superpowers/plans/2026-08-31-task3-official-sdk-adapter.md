# Task 3 official SDK adapter — measured contract gap

Date: 2026-08-31

## Basis and authorized scope

- Fresh `origin/main`: `b06e533bbcbe7221e7c3ad9234e8497f9b422ec8`.
- Branch: `runtime/m3-task3-official-sdk-adapter`.
- Consumed #311 `SOL_ADAPTER_AUTHORIZATION_V1` comment `5471766748` and #301
  advisory comment `5471768285`.
- The authorized write-set was limited to `agent_lib/codex_worker.py`, its
  focused tests, `docs/STATUS.md`, the M3 live packet, and this plan.

## Causal RED

The exact canonical child control seam was exercised with a valid immutable
`AdapterRequest` using the disposable provider venv
`C:\temp\cad-agent-m3-provider-venv-20260831` and the current
`_unsupported_official_adapter_factory`. It returned:

```text
{"_worker_error":"WORKER_SDK_INCOMPATIBLE"}
```

The failure occurs in the child before a provider result can reach the Task 6
issuance owner. No caller-created result or non-canonical process boundary was
accepted.

## Low-level refinement measurement

The official low-level `CodexClient.thread_start()` seam was exercised from
the exact 0.144.4 disposable venv with a fresh `CODEX_HOME`, no
`OPENAI_API_KEY`, and no copied account files. It returned a typed and
serialized `ThreadStartResponse`:

```text
approvalPolicy=never
approvalsReviewer=user
cwd=C:\temp\cad-agent-live-b06e
instructionSources=[C:\temp\cad-agent-live-b06e\AGENTS.md]
model=gpt-5
modelProvider=openai
sandbox={networkAccess:false,type:readOnly}
thread.id=01a05534-7493-7e42-97a2-fb15e778691b
thread.cliVersion=0.144.4
thread.ephemeral=true
```

The reported instruction path canonicalized to the same file and its actual
bytes hashed to
`80dd3987983e13b4b296ad9fbbc170e816e7ba4432850378f21bcdc72d40363d`
(`4490` bytes). This proves the low-level seam exposes provider-observed
instruction paths and enough typed policy/model/cwd/thread fields to measure
them; the earlier high-level-only conclusion was superseded.

The exact remaining repository gaps are:

1. The observed path/hash has no provider-returned `source_id` or `role`, and
   the current authority expects ordered `{source_id, role, sha256}` entries.
   No canonical path-to-authority mapping exists, so matching `AGENTS.md` to
   `system`/`project` by caller claim would be fabricated.
2. The response contains no `config_sha256`; #311 requires that value to stay
   server/request-owned and explicitly forbids experimental `config/read`.
3. The provider generates `thread.id` after `thread_start`, while the repo
   binds `observed_thread_id` before the child request. A disposable
   `thread_resume` against the ephemeral start returned `no rollout found`,
   confirming that start/resume cannot silently bridge this lifecycle.
4. The low-level fork API accepts a source thread ID, but the existing
   `AdapterRequest` carries no source-thread identity for a truthful fork.

The outbound request explicitly serialized `approvalPolicy=never` and
`sandbox=workspace-write`, while the provider response observed
`approvalsReviewer=user` and `sandbox.type=readOnly`; this effective-policy
delta also cannot be treated as a PASS for the existing disposable-write
binding.

## Decision

`EXACT_REMAINING_GAP`: the official low-level seam is proven, but the first
repo acceptance boundary remains an exact fail-closed mapping of provider
instruction paths to authority identities plus a provider-observed config
identity and post-generation thread binding. No production adapter was
written and no contract was weakened. The existing `LazyOfficialSdkAdapter`,
Task 3 process custody, request/result validators, Task 6 issuance, and all
AutoCAD/FileIPC/R5/R6 owners remain unchanged. M2 is not retested; NETLOAD is
not required.

The next implementation boundary is a separately measured official SDK or
existing-owner seam that can bind the provider-generated thread identity and
truthfully expose every required effective policy/attestation field. Until
that evidence exists, the canonical child must remain fail-closed.
