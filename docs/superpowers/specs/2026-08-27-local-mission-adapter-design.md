# Sealed Local Mission Adapter Design

Date: 2026-08-27
Status: APPROVED BY HUMAN OWNER
Issue: #288
Stacked base: `governance/operating-model-enforcement` at `729f005b5c1cad6f88245bb134b524be644c4855`

## 1. Goal

Harden the existing ChatGPT Local Executor so a self-hosted Windows runner can consume one already-compiled local mission without exposing an arbitrary shell-command bypass, without becoming a new authority owner, and without adding a second runner, transport, daemon, database, or persistent state store.

E1 is deliberately narrow. It supports exactly one typed capability: `OFFLINE_VERIFY`. Windows-specific probes and AutoCAD/live capabilities remain out of scope and require a separately approved extension.

## 2. Existing owner to reuse

The accepted owner is the existing chain:

```text
workflow_dispatch
  -> .github/workflows/chatgpt-local-executor.yml
  -> self-hosted Windows runner
  -> scripts/local-executor.ps1
  -> scripts/bootstrap.ps1
  -> scripts/verify.ps1
```

E1 does not create another executor. The current workflow's `command` input followed by `Invoke-Expression` is the bypass to remove.

## 3. Authority model

E1 preserves:

```text
Human Owner > CONTROL_WRITER_SOL > Local Solo Executor
```

GitHub/Issue #131 remains canonical authority. The local adapter may validate an attached derived control snapshot and an already-compiled mission, run an allowlisted deterministic capability, and emit evidence. It may not:

- mint or advance `CONTROL_SEQ`;
- authorize repository mutation, live AutoCAD, merge, or publication;
- infer missing Human approval;
- replace fresh GitHub reads with a local truth store;
- turn any mission field into executable PowerShell/shell text.

## 4. Stacked dependency

E1 depends on the verified but unmerged A-D contracts from PR #286:

- `cad_agent.control_snapshot.validate_control_snapshot`;
- `cad_agent.mission_contract.validate_local_mission`;
- `cad_agent.drawing_contracts.canonical_json_sha256`.

Therefore E1 is a stacked branch based on exact #286 head `729f005b5c1cad6f88245bb134b524be644c4855`, and its PR must target `governance/operating-model-enforcement`, not `main`.

## 5. Closed execution envelope

Add one pure contract module: `cad_agent/local_execution_envelope.py`.

Schema version:

```text
cad-local-execution-envelope-1.0
```

Closed fields:

```text
schema_version
capability
expected_mission_sha256
mission
control_snapshot
```

Allowed capability in E1:

```text
OFFLINE_VERIFY
```

Validation order:

1. envelope is a mapping with exactly the closed field set;
2. `schema_version` exactly matches E1;
3. `capability` is exactly `OFFLINE_VERIFY`;
4. `mission` and `control_snapshot` are mappings;
5. compute `canonical_json_sha256(mission)` and compare to `expected_mission_sha256`;
6. call `validate_local_mission(mission, control_snapshot=control_snapshot)`;
7. require returned mission `live_budget == 0`;
8. require returned mission `merge_authority is False`;
9. require returned mission `publication_authority is False`;
10. require `routing_classification == LOCAL_REPO_REQUIRED` for E1;
11. return a canonical normalized envelope plus derived `mission_sha256` and `control_state_sha256` for the script boundary.

Unknown fields and unknown capabilities fail closed.

The execution envelope is not persisted by the Python module. It is only validation material supplied by the runner.

## 6. Local branch/head binding

The local PowerShell executor receives:

```text
-MissionEnvelopePath <RUNNER_TEMP path>
-ExpectedBranch <exact branch>
-ExpectedSha <exact 40-char commit SHA>
```

Before bootstrap/verify it must:

1. resolve the repo root from `$PSScriptRoot`;
2. resolve and verify the envelope path is under `$env:RUNNER_TEMP`;
3. verify working tree branch exactly equals `ExpectedBranch`;
4. verify `git rev-parse HEAD` exactly equals `ExpectedSha` — no prefix matching;
5. invoke Python 3.11 to validate the sealed envelope through `cad_agent.local_execution_envelope`;
6. ensure the validated mission's `active_pr_head_sha` equals local exact HEAD when the mission has an active PR;
7. only then run the fixed authoritative offline commands.

No mission field is interpolated into a command line.

## 7. Workflow transport

Replace dispatch input `command` with closed inputs:

```text
expected_branch
expected_sha
mission_envelope_json
```

`expected_branch`, `expected_sha`, and `mission_envelope_json` are required.

The workflow must never place raw JSON inside a PowerShell program string. It supplies the JSON through an environment variable and materializes bytes under `$RUNNER_TEMP`, for example:

```powershell
$missionPath = Join-Path $env:RUNNER_TEMP "cad-agent-mission-envelope.json"
[System.IO.File]::WriteAllText($missionPath, $env:CAD_AGENT_MISSION_ENVELOPE_JSON, [System.Text.UTF8Encoding]::new($false))
```

Then call only:

```powershell
.\scripts\local-executor.ps1 `
  -ArtifactsDir $tempArtifacts `
  -MissionEnvelopePath $missionPath `
  -ExpectedBranch $env:CAD_AGENT_EXPECTED_BRANCH `
  -ExpectedSha $env:CAD_AGENT_EXPECTED_SHA
```

The workflow must contain neither `command` input nor `Invoke-Expression`.

## 8. Fixed `OFFLINE_VERIFY` execution

After all guards pass, the executor runs only:

```powershell
$python311 = py -3.11 -c "import sys; print(sys.executable)"
.\scripts\bootstrap.ps1 -PythonExe $python311
.\scripts\verify.ps1
```

E1 does not authorize AutoCAD, COM, ROT, UI, NETLOAD, File-IPC live work, production DXF mutation, merge, or publication.

## 9. Machine-readable terminal

Always attempt to write `$ArtifactsDir/mission-terminal.json`, including guard/validation failure cases after the artifact directory can be safely created.

Closed terminal fields:

```text
schema_version
mission_sha256
control_state_sha256
capability
local_branch
local_head_sha
result
bootstrap_exit_code
verify_exit_code
live_result
merge_authority
publication_authority
```

Terminal schema version:

```text
cad-local-mission-terminal-1.0
```

Allowed `result` values in E1:

```text
PASS
FAIL
```

`live_result` is always:

```text
NOT_RUN
```

`merge_authority` and `publication_authority` are always `false`.

The terminal must not contain a `control_seq` field and must not claim live acceptance.

If validation fails before mission identity is known, `mission_sha256` and `control_state_sha256` are the literal string `UNVALIDATED`.

## 10. Failure behavior

All envelope, path, branch, SHA, mission, and capability failures are fail-closed and occur before bootstrap/verify. A failed validation may emit diagnostic evidence but must not execute any mission-derived command.

The workflow artifact remains evidence only and is retained for one day as today unless separately changed.

## 11. Security invariants

- no `Invoke-Expression`;
- no `iex` alias;
- no `& <mission supplied string>`;
- no shell, PowerShell, Python, executable path, arguments, or script body field in the envelope;
- no payload write outside `$RUNNER_TEMP`;
- no prefix SHA acceptance;
- no local mutation authority inferred from mission presence;
- no live capability in E1;
- no secrets or private CAD bytes in the envelope;
- no persistent authority/checkpoint store.

## 12. Write-set

Modify only:

- `.github/workflows/chatgpt-local-executor.yml`
- `scripts/local-executor.ps1`

Create only:

- `cad_agent/local_execution_envelope.py`
- `tests/test_local_execution_envelope.py`
- `tests/test_chatgpt_local_executor_contract.py`
- `docs/superpowers/specs/2026-08-27-local-mission-adapter-design.md`
- `docs/superpowers/plans/2026-08-27-local-mission-adapter.md`

No other path may change under #288.

## 13. Acceptance

E1 is accepted for implementation verification only when:

- causal RED is recorded before the corresponding GREEN;
- envelope validation is deterministic and fail-closed;
- current arbitrary-command bypass is gone;
- only `OFFLINE_VERIFY` can execute;
- exact local branch/head binding is enforced before authoritative commands;
- mission material is runner-temp only;
- terminal evidence cannot imply authority;
- focused and full hosted verification pass on the exact head;
- independent security/operations review reports no unresolved P0/P1;
- AutoCAD/live is explicitly `NOT_RUN`;
- PR remains DRAFT and unmerged pending SOL disposition.
