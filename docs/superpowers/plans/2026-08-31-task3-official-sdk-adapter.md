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

## SDK 0.144.4 evidence

The installed official package was inspected from the disposable venv:

- `Codex.thread_start(...)` has no server-supplied `thread_id` parameter and
  returns a provider-generated `Thread.id`.
- `thread_resume` can validate an already-known ID, but the existing canonical
  `start` path binds its expected identity before the child request.
- `ThreadReadResponse` exposes only a thread record. The public `Thread` and
  `ThreadReadResponse` models do not expose the effective approval policy,
  sandbox roots/write policy, config identity, or server instruction-source
  identities required by `validate_provider_effective_attestation`.
- The existing `AdapterRequest` has no source-thread identity for a truthful
  `thread_fork` operation.

These are mandatory current Task 3/Task 5 invariants, not optional metadata.
Returning request fields as observed attestation would manufacture provider
evidence and violate #311's explicit no-echo rule.

## Decision

`SDK_CONTRACT_GAP`: no production adapter was written and no contract was
weakened. The existing `LazyOfficialSdkAdapter`, Task 3 process custody,
request/result validators, Task 6 issuance, and all AutoCAD/FileIPC/R5/R6
owners remain unchanged. M2 is not retested; NETLOAD is not required.

The next implementation boundary is a separately measured official SDK or
existing-owner seam that can bind the provider-generated thread identity and
truthfully expose every required effective policy/attestation field. Until
that evidence exists, the canonical child must remain fail-closed.
