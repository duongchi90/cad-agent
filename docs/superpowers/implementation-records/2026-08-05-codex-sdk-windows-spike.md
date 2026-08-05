# Codex SDK Windows Compatibility Spike

Status: completed for the Issue #48 compatibility-spike scope; no production
Codex bridge or repair-planner integration was enabled.

## Identity and scope

- Issue: #48, S1 Codex SDK Windows compatibility adapter and disposable probe.
- Exact base SHA: `5d6074a2969894367df2e5d70b7a362c99e43c61`.
- Branch: `task/s1-codex-sdk-windows-compat`.
- Supported host observed: Windows 10 Pro, version `2009`, OS build `19045`.
- Python observed: `3.11.9`.
- Changed files: the four files allowlisted by Issue #48 only.
- Dependency lock: unchanged; the SDK was installed only in a disposable
  virtual environment outside the repository.

## Adapter behavior

`agent_lib/codex_sdk_compat.py` is an optional, lazy, fail-closed boundary.
Inspection imports metadata only and reports stable, path-redacted facts. It
does not construct a Codex client, authenticate, start a model turn, access a
repository, or call repair logic. Compatibility requires the official
`openai-codex` import, Python 3.11, Windows, valid SDK metadata, and a real
`codex_cli_bin` runtime file located beneath the installed runtime package.

The probe uses only standard-library process and JSON APIs. Its start mode
launches the bundled app-server with stdin closed, a disposable temporary
working directory, and an environment limited to process-start variables. It
never sends initialize, login, account, thread, model, turn, file, or repair
requests. Output is deterministic UTF-8 JSON with sorted keys and no absolute
paths, credentials, tokens, or account details.

## Disposable official SDK probe

The external environment was created outside the repository and was not added
to the project lock. The command path is redacted here as
`<disposable-external-venv>` so this record contains no workstation path.

Installed package result:

- `openai-codex==0.144.4`.
- `openai-codex-cli-bin==0.144.4` (the SDK's pinned runtime dependency).
- `pydantic==2.13.4` was installed as the SDK's external environment support
  dependency.

Inspection command and result:

```powershell
<disposable-external-venv>\Scripts\python.exe scripts/probe_codex_sdk_windows.py --mode inspect
```

Exit code: `0`.

```json
{"inspection":{"import_available":true,"os":"Windows","python_version":"3.11.9","reasons":[],"runtime":{"available":true,"classification":"bundled"},"sdk_version":"0.144.4","status":"compatible"},"mode":"inspect"}
```

Disposable runtime-start command and result:

```powershell
<disposable-external-venv>\Scripts\python.exe scripts/probe_codex_sdk_windows.py --mode start --timeout-seconds 2
```

Exit code: `0`. The runtime started and closed cleanly with return code `0`;
because stdin was intentionally closed, the app-server exited without an
initialize request. No login, model turn, workspace write, repository write,
repair execution, or credential access was performed.

```json
{"inspection":{"import_available":true,"os":"Windows","python_version":"3.11.9","reasons":[],"runtime":{"available":true,"classification":"bundled"},"sdk_version":"0.144.4","status":"compatible"},"mode":"start","runtime_start":{"returncode":0,"status":"started_and_closed","success":true}}
```

The repository's normal environment intentionally lacks the optional SDK. Its
inspection-only probe returned exit code `2` with `missing_import` and
`missing_runtime`; this is the expected fail-closed result, not a pass.

## Verification evidence

Focused contract suite:

```text
14 passed, 0 skipped
```

The focused tests cover missing import, supported fake runtime, unsupported
Windows/Python metadata, missing/malformed/unapproved runtime paths,
deterministic UTF-8 JSON, timeout and startup failures (including a hanging
runtime), clean runtime exit, and inspection non-invocation of
authentication/model APIs.

Ruff passed for the three Python implementation/probe files. The architecture
boundary checker passed with no new violation. `git diff --check` passed.

Required specialized gates:

- Private real-data gate: `NOT RUN` (not in scope and no approved private input).
- AutoCAD Mechanical live gate: `NOT RUN` (not in scope; no live mutation).
- External model/login gate: `NOT RUN` by design; no authentication or model
  call was attempted.

The canonical verifier is run only on the clean committed candidate because
its contract rejects a dirty tree. Its exact result is reported with the final
commit and PR provenance; no unavailable gate is described as a pass.

## Reuse and rollback

- Existing capability inspected: `agent_lib` advisory proposal/apply
  separation, standard repository verification, and the supported Windows
  Python 3.11 environment.
- Existing API reused: Python `importlib`, `importlib.metadata`, `pathlib`,
  `subprocess`, and deterministic JSON APIs; existing pytest/Ruff/architecture
  and verifier commands.
- Adapter required: one lazy optional compatibility adapter under `agent_lib`.
- New capability genuinely missing: a fail-closed Windows compatibility seam
  and reproducible disposable probe for the official SDK.
- Files allowed to change: the four Issue #48 allowlisted files only.
- Files forbidden to duplicate: Codex transport/CLI protocol, proposal/apply
  logic, repair executor, AutoCAD transport, verdict, manifest/checkpoint,
  revision store, publisher, dependency files, and existing CLI behavior.
- Compatibility behavior: absent, unsupported, malformed, or unapproved SDK
  state is explicitly incompatible; production paths remain unchanged.
- Migration and rollback path: revert the single bounded S1 commit. No
  dependency state or production runtime capability is promoted.
