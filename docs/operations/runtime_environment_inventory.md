# CAD Agent Runtime Environment Inventory

## Scope and authority

This is one bounded, read-only forensic snapshot of the Windows, AutoCAD Mechanical, .NET, AutoLISP/FileIPC, MCP/local-executor, drawing, and evidence topology observed on 2026-09-19 (Asia/Saigon). It is documentation, not runtime authority, a registry, resolver, watcher, daemon, queue, bridge, or control plane. No CAD file, trust setting, runtime file, process, or environment binding was changed.

GitHub is canonical for repository/product state. Fresh-read sources were `origin/main`, issues [#291](https://github.com/duongchi90/cad-agent/issues/291), [#305](https://github.com/duongchi90/cad-agent/issues/305), [#429](https://github.com/duongchi90/cad-agent/issues/429), and [#409](https://github.com/duongchi90/cad-agent/issues/409), plus local files and live read-only process/filesystem evidence. Private CAD/source artifacts remain outside Git.

Classification vocabulary: `CANONICAL`, `ACTIVE`, `APPROVED`, `DISPOSABLE`, `HISTORICAL`, `STALE`, `UNKNOWN`. A claim of `CURRENTLY_LOADED` requires process/module or equivalent runtime evidence; an on-disk file is not evidence of loading.

## Current summary

| Field | Value |
|---|---|
| `LAST_VERIFIED` | 2026-09-19, Asia/Saigon |
| Repository | `C:\Users\dkv\Downloads\cad-agent-merge` |
| Current branch / HEAD | `codex/dimension-native-placement-green-20260918` / `b203e743c2b8a88a318123b6813c526358bf9023` |
| Fresh `origin/main` | `8c1b9b2807f2c69b111783752802cf03a9ccf3c2` |
| AutoCAD | AutoCAD Mechanical 2027 / AutoCAD 2027, PID `21320`, HWND `525948` (`EPHEMERAL_SESSION_FACT`) |
| Active drawing | `C:\Users\dkv\Downloads\BVTL.dwg`, title `BVTL.dwg`; path proven, hash not readable while locked |
| Loaded CAD Agent DLL | `UNKNOWN / NOT_OBSERVED`; no `CadAgent.AutoCAD2027.dll` module appeared in the AutoCAD module census |
| Trusted/runtime dispatcher LSP | `C:\cad-agent\trusted-dispatcher\mcp_dispatch.lsp`; SHA256 `D80190A1621963E420B8E90566B1F858EEB3775C8FEE86B70352AA6FBE2CB222`; source/deployed hash equality and fresh raw-LISP execution proof in #409/5738282459 |
| FileIPC / .NET IPC | `UNKNOWN / NOT_VERIFIED` active roots; both code defaults are `C:\temp`, environment overrides are unset |
| Secrets | `SECRETS_RECORDED=NO`; token-bearing environment variable names were observed but values were not read or stored |

## Workspace and Git

| Field | Value |
|---|---|
| `REPO` | `duongchi90/cad-agent` |
| `PRIMARY_WORKTREE` | `C:\Users\dkv\Downloads\cad-agent-merge` — `ACTIVE` |
| `REMOTE` | `origin = https://github.com/duongchi90/cad-agent.git` |
| `CURRENT_BRANCH` | `codex/dimension-native-placement-green-20260918` |
| `CURRENT_HEAD` | `b203e743c2b8a88a318123b6813c526358bf9023` |
| `CURRENT_MAIN` | `8c1b9b2807f2c69b111783752802cf03a9ccf3c2` |
| `WORKTREE_STATUS` | clean before this documentation change; branch was equal to its remote before this commit |
| `OTHER_KNOWN_WORKTREES` | Listed below; no worktree was deleted or modified. |

The following linked worktrees were present at verification. Detached dated/live/build/verify worktrees are `HISTORICAL` unless a future checkpoint proves otherwise; branch-attached alternate worktrees are `UNKNOWN`; the primary worktree above is `ACTIVE`.

| Path | HEAD / branch evidence | Status |
|---|---|---|
| `C:\temp\cad-agent-current-main-live-20260905-01`; `C:\temp\cad-agent-live-73d79`; `C:\temp\cad-agent-m3-disposable-acceptance-3c60460`; `C:\temp\cad-agent-m3-disposable-acceptance-9fd3701`; `C:\temp\cad-agent-m4-live-close-current-20260904-01`; `C:\temp\cad-agent-main-current-20260902-17`; `C:\temp\cad-agent-main-df964-readonly-20260915`; `C:\temp\cad-agent-phase4-current-main-20260906-01`; `C:\temp\cad-agent-phase4-native-current-20260905-01`; `C:\temp\cad-agent-real-pdf-current-main-iter78`; `C:\temp\cad-agent-release-verify-20260909-01`; `C:\temp\cad-agent-release-verify-remediation-20260909-01`; `C:\temp\cad-agent-verify-iteration71`; `C:\temp\cad-agent-verify-iteration75` | Detached commits; exact HEADs are in `git worktree list --porcelain` at verification | `HISTORICAL` |
| `C:\temp\cad-agent-mechanical-pilot-binding-pr437-red-20260916`; `C:\temp\cad-agent-mechanical-pilot-binding-red-20260916`; `C:\temp\cad-agent-mechanical-pilot-build-binding-red-20260916`; `C:\temp\cad-agent-mechanical-pilot-external-binding-20260916`; `C:\temp\cad-agent-mechanical-pilot-external-binding-red-20260916`; `C:\temp\cad-agent-page1-main-binding-20260916`; `C:\temp\cad-agent-page1-main-oracle-20260916`; `C:\temp\cad-agent-page1-offline-20260916`; `C:\temp\cad-agent-plugin-main-build-edee-20260916`; `C:\temp\cad-agent-pr433-green-20260916`; `C:\temp\cad-agent-primitive-ir-validator-20260916`; `C:\temp\cad-agent-r3-candidate-swap-red-20260916`; `C:\temp\cad-agent-r3-external-provenance-20260916`; `C:\temp\cad-agent-r3-provenance-red-20260916`; `C:\temp\cad-agent-security-red-20260916`; `C:\temp\cad-agent-topology-red-20260915-01`; `C:\temp\cad-agent-visual-run-root-red-20260916` | Branch-attached alternate checkouts | `UNKNOWN` |
| `C:\Users\dkv\.codex\worktrees\5658\cad-agent-merge`; `C:\Users\dkv\.codex\worktrees\a277\cad-agent-merge`; `C:\Users\dkv\Downloads\cad-agent-duplicate-red`; `C:\Users\dkv\Downloads\cad-agent-geometry-red`; `C:\Users\dkv\Downloads\cad-agent-seq344-sync`; `C:\Users\dkv\Downloads\cad-agent-source-component-red`; `C:\Users\dkv\Downloads\cad-agent-source-support-red`; `C:\Users\dkv\Downloads\cad-agent-worktrees\dimension-source-placement-replay`; `C:\Users\dkv\Downloads\cad-agent-worktrees\issue-297-dedicated-runner-checkout`; `C:\Users\dkv\Downloads\cad-agent-worktrees\issue-297-powershell-native-stderr`; `C:\Users\dkv\Downloads\cad-agent-worktrees\page1-acceptance-matrix-20260914`; `C:\Users\dkv\Downloads\cad-agent-worktrees\page1-text-sizing-fix`; `C:\Users\dkv\Downloads\cad-agent-worktrees\semantic-multiplicity-contract`; `C:\Users\dkv\Downloads\cad-agent-worktrees\source-bound-occurrence-contract-red` | Alternate branch or detached worktrees | `UNKNOWN` |

No suitable single existing owner document was found before creation; existing IPC/architecture/runbook documents are narrower and do not own this complete topology.

## AutoCAD installation/session

### Stable facts

| Field | Value | Status / evidence |
|---|---|---|
| `AUTOCAD_VERSION` | AutoCAD Mechanical 2027 / AutoCAD 2027 | `APPROVED`; installed-product registry and executable metadata |
| `AUTOCAD_EXE_PATH` | `C:\Program Files\Autodesk\AutoCAD 2027\acad.exe` | `CANONICAL + ACTIVE` |
| `PRODUCT_YEAR` | 2027 | `APPROVED` |
| `PROFILE_IF_READABLE` | `HKCU\Software\Autodesk\AutoCAD\R26.0\ACAD-A101:409\Profiles\<<Unnamed Profile>>`; also `<<ACADMPP>>`; saved workspace observed as `Drafting & Annotation` | `ACTIVE`; registry read-only |
| `PLUGIN_TARGET_RUNTIME` | `autocad_plugin\CadAgent.AutoCAD2027\CadAgent.AutoCAD2027.csproj` targets `net10.0-windows` | `CANONICAL + ACTIVE` |

### Current snapshot

| Field | Value |
|---|---|
| `PROCESS_PID` | `21320` — `EPHEMERAL_SESSION_FACT` |
| `TOP_HWND` | `525948` — `EPHEMERAL_SESSION_FACT` |
| `ACTIVE_DRAWING_TITLE` | `Autodesk AutoCAD 2027 - [BVTL.dwg]` |
| `ACTIVE_DRAWING_PATH_IF_PROVEN` | `C:\Users\dkv\Downloads\BVTL.dwg` — proven by process command line; hash read failed because file is locked |
| `DBMOD_IF_PROVEN` | `UNKNOWN / NOT_VERIFIED` in the post-inventory #409/5738282459 snapshot; the earlier `DBMOD=0` proof predates commit `662dda7` and is not reused |
| `FILEIPC_PING_DRAWING_GET_VARIABLES_CURRENTNESS` | `NOT_RUN` in post-inventory #409/5738282459; the latest post-662 root-census checkpoint intentionally performed no ping or `drawing_get_variables` request. Earlier PASS evidence predates commit `662dda7` and is not reused |
| `SESSION_STATUS` | AutoCAD process running; no `CadAgent.AutoCAD2027.dll` module observed in the read-only module census |
| `STARTUP_ARGUMENT` | `D:\Cad agent temp\luna-readonly-lsp-load-20260919.scr`; the path was missing at verification, so its content/loading effect is `UNKNOWN / NOT_VERIFIED` |

## AutoCAD trust configuration

Read-only registry census; no setting was changed.

| Setting / path | Value | Exists / type | Status | Evidence |
|---|---|---|---|---|
| `SECURELOAD` | `1` | registry value | `ACTIVE` | current profile registry read |
| `TRUSTEDPATHS` | empty | registry value | `ACTIVE` but no trusted dispatcher path proven | current profile registry read |
| `TRUSTEDDOMAINS` | `*.autodesk.com;*.autocad.com` | registry value | `ACTIVE` | current profile registry read |
| `ACAD` support paths | `C:\Users\dkv\AppData\Roaming\Autodesk\AutoCAD 2027\R26.0\enu\support;C:\Program Files\Autodesk\AutoCAD 2027\support;C:\Program Files\Autodesk\AutoCAD 2027\support\en-US;C:\Program Files\Autodesk\AutoCAD 2027\fonts;C:\Program Files\Autodesk\AutoCAD 2027\help;C:\Program Files\Autodesk\AutoCAD 2027\Express` | existing directories confirmed where readable | `ACTIVE` | profile registry read |
| `XrefLoadPath` / `SaveFilePath` | `C:\Users\dkv\AppData\Local\Temp\` | existing directory | `ACTIVE` | profile registry read |
| `APPLOAD/STARTUP_RELEVANT_PATHS` | Startup script argument above; referenced `.scr` missing | file `MISSING` | `STALE / UNKNOWN` | WMI command line plus filesystem read |
| `TRUSTED_DISPATCHER_PATH` | `C:\cad-agent\trusted-dispatcher\mcp_dispatch.lsp` | deployed file; SHA256 equals repo LSP hash | `APPROVED + ACTIVE` | #409/5738282459 exact hash and source/deployed equality; raw-LISP sentinel/root readback |

## .NET / NETLOAD DLLs

These are on-disk identities only. AutoCAD module evidence did not show a `CadAgent.AutoCAD2027.dll` module, so no row below is `CURRENTLY_LOADED`.

| Role | Path | SHA256 | Size | Build origin / source commit | Loaded in AutoCAD | Trust / status |
|---|---|---|---:|---|---|---|
| `REPO_BUILD` | `C:\Users\dkv\Downloads\cad-agent-merge\autocad_plugin\CadAgent.AutoCAD2027\bin\x64\Release\net10.0-windows\CadAgent.AutoCAD2027.dll` | `FE8F8D41066BA0D6EF1C47D9A6811BECCED634FEDD858E9299191B774FA730F` | 433664 | current worktree build; source commit not embedded/proven | `UNKNOWN / NOT_OBSERVED` | `UNKNOWN` |
| `STALE_COPY` | `C:\Users\dkv\Downloads\cad-agent-merge\autocad_plugin\CadAgent.AutoCAD2027\bin\Release\net10.0-windows\CadAgent.AutoCAD2027.dll` | `7A1164FBCE97C7A5FAEBDF1CE454160FD823A8952AE2AE8C9E12025871E72008` | 518656 | repository standard Release output; source commit not proven | `UNKNOWN / NOT_OBSERVED` | `STALE` |
| `DISPOSABLE_BUILD` | `D:\Cad agent temp\cadagent-build\bin\CadAgent.AutoCAD2027.dll` | `E52ED879F3B8E88F88D05B8A1A2C588CEFB680C34654B5F9054823A12D1AE074` | 433664 | disposable build; source commit `UNKNOWN / NOT_PROVEN` | `UNKNOWN / NOT_OBSERVED` | `DISPOSABLE` |
| `DISPOSABLE_BUILD` | `D:\Cad agent temp\cadagent-build-ed1db3c\CadAgent.AutoCAD2027.dll` | `60C5541DC5AC5EEF65C45495B0FB6F2906863BB8E856979133134993993E8B53` | 434176 | directory label is not provenance; source commit `UNKNOWN / NOT_PROVEN` | `UNKNOWN / NOT_OBSERVED` | `DISPOSABLE` |

`CURRENTLY_LOADED_DLL_PATH=UNKNOWN / NOT_VERIFIED`; `CURRENTLY_LOADED_DLL_SHA256=UNKNOWN / NOT_VERIFIED`. Do not infer loading from filename, timestamp, or proximity to a build directory. No proven DLL move/load transition was found in the inspected local Git history.

## AutoLISP / dispatcher

| Role | Path | SHA256 | Source commit | Trust | Currently loaded | Status |
|---|---|---|---|---|---|---|
| `REPO_CANONICAL` | `C:\Users\dkv\Downloads\cad-agent-merge\mcp_integration_lib\mcp_dispatch.lsp` | `D80190A1621963E420B8E90566B1F858EEB3775C8FEE86B70352AA6FBE2CB222` | current worktree content; exact source commit not separately proven | source bytes | `YES` through fresh raw-LISP execution proof #409/5738282459 | `CANONICAL + ACTIVE` |
| `TRUSTED_RUNTIME_COPY` | `C:\cad-agent\trusted-dispatcher\mcp_dispatch.lsp` | `D80190A1621963E420B8E90566B1F858EEB3775C8FEE86B70352AA6FBE2CB222` | source/deployed equality proven by #409/5738282459 | explicit trust/deployed copy | `YES` through sentinel/content readback; session identity is ephemeral | `APPROVED + ACTIVE` |
| `DISPOSABLE / TEST` | `D:\Cad agent temp\pytest-of-dkv\...\mcp_dispatch.lsp` and `D:\Cad agent temp\pytest-temp\...\mcp_dispatch.lsp` | mostly zero-byte stubs; one observed 28-byte stub `C2C1477D02BA0AFF369307B768033C5D72E2B71008FE45D268B24D666E5FBAFC` | test-generated | not trusted | `NO / UNKNOWN` | `DISPOSABLE` |

`REPO_LSP_PATH/HASH` and `TRUSTED_LSP_PATH/HASH` are the two equal-hash rows above. `CURRENTLY_LOADED_LSP_IDENTITY` is proven for the fresh session by #409/5738282459: the exact trusted LSP expression executed and returned sentinel plus `*cad-agent-file-ipc-root*` content. This proves LSP execution/currentness for that ephemeral session, not a permanent runtime guarantee; later root/timeout evidence remains unresolved. Hash differences between repo and test stubs are intentional evidence of distinct disposable files, not a repair target.

## FileIPC / DotNet IPC

| Binding | Default | Active override at snapshot | Request/result pattern | Binding evidence |
|---|---|---|---|---|
| `FileIPCLiveMCPClient` / `CAD_AGENT_FILE_IPC_DIR` | `C:\temp` | `UNKNOWN / NOT_VERIFIED`; environment variable unset and no current request observed | `autocad_mcp_cmd_*.json` / `autocad_mcp_result_*.json` | `cad_agent\cli.py`, current environment, `C:\temp` census |
| `DotNetIPCClient` / `CAD_AGENT_DOTNET_IPC_DIR` | `C:\temp` | `UNKNOWN / NOT_VERIFIED`; environment variable unset | `cadagent_dotnet_request_*.json` / `cadagent_dotnet_result_*.json` | `mcp_integration_lib\dotnet_ipc.py`, `CommandContext.cs`, current environment |
| AutoLISP `*cad-agent-file-ipc-root*` | set by FileIPC command context/bootstrap | `UNKNOWN / NOT_VERIFIED` | consumes FileIPC request/result names | `mcp_integration_lib\mcp_dispatch.lsp` and Python client |
| `CAD_AGENT_DOTNET_IPC_DIR` plugin binding | explicit env override or code default | `UNKNOWN / NOT_VERIFIED` | .NET request/result names | `CommandContext.cs` |
| Isolated test roots | `C:\temp\disposable-workspaces` pattern plus test-specific roots | `DISPOSABLE / UNKNOWN` per test | test-specific | code/tests and filesystem census |

The defaults are equal (`C:\temp`) but the bindings are not interchangeable. `C:\temp` existed and had no FileIPC request/result files at verification; it had 9 historical-looking .NET request files and 2 result files, including `cadagent_dotnet_request_rear-loc-0000.json` and `cadagent_dotnet_request_normal-cad-health-20260918-a7e1513.json`. These were not deleted. `ACTIVE_FILEIPC_ROOT=UNKNOWN / NOT_VERIFIED`; `ACTIVE_DOTNET_IPC_ROOT=UNKNOWN / NOT_VERIFIED`.

| Root | Owner / purpose | How bound | Default or explicit | Status | Cleanup policy |
|---|---|---|---|---|---|
| `C:\temp` | legacy/default FileIPC and DotNet IPC root | code defaults when env unset | default | `HISTORICAL / DEFAULT; active currentness UNKNOWN` | do not clear automatically; inspect request/result ownership first |
| `D:\Cad agent temp` | disposable build, pytest, live/evidence roots | explicit test/session tooling | explicit | `DISPOSABLE` | no automatic deletion in this task |
| `C:\Users\dkv\AppData\Local\Temp\cad-agent-r6-204-*` | test/disposable runtime roots | test tooling | explicit | `DISPOSABLE` | no automatic deletion in this task |

## MCP / bridge topology

| Component | Purpose | Executable/script | Working/config path | Process / endpoint | Status |
|---|---|---|---|---|---|
| Codex desktop/local executor | local task orchestration and computer-use execution | `C:\Users\dkv\AppData\Local\OpenAI\Codex\bin\...` | Codex-managed; exact project bridge config not proven | Codex/Codex host/computer-use processes observed; no separate project MCP server proven | `ACTIVE` |
| Project-local MCP/bridge server | FileIPC/AutoCAD project bridge | `UNKNOWN / NOT_VERIFIED` | `UNKNOWN / NOT_VERIFIED` | no separate project MCP/bridge process identified in snapshot | `UNKNOWN` |
| `CAD_AGENT_BRIDGE_TOKEN`, `CAD_AGENT_LOCAL_MCP_TOKEN` | possible local bridge authentication bindings | values intentionally not read | `SECRET_REDACTED / NOT_RECORDED` | environment names only | `UNKNOWN` |

No access tokens, OAuth tokens, authorization headers, cookies, passwords, or private keys are recorded. No bridge endpoint was inferred from filenames or token variable names.

## Trusted drawings and source artifacts

Roles below are based on current process evidence, repository/issue evidence, and explicit uncertainty; they are not filename-only inferences.

| Logical name | Role | Path | SHA256 | Format | Admission / authority | Mutation policy | Status |
|---|---|---|---|---|---|---|---|
| `BVTL source/base` | `BASE_PRODUCT_INPUT` | `C:\Users\dkv\Downloads\BVTL.dwg` | `UNKNOWN / NOT_VERIFIED` (locked by AutoCAD) | DWG | active drawing path proven by AutoCAD process; private source outside Git | `SOURCE_MUTATION_ALLOWED=NO` | `APPROVED + ACTIVE` |
| `BVTL rollback copy` | `HISTORICAL_EVIDENCE` / rollback companion | `C:\Users\dkv\Downloads\BVTL.bak` | `B1C69C435BCAE6774414928AD8143412583016723DE6C6B8F30C9942CD19C01C` | BAK/DWG backup | local timestamp/hash only; not generation authority | preserve; no mutation | `HISTORICAL` |
| `BVTL modified observation` | `TARGET_OBSERVATION` | `C:\Users\dkv\Downloads\BVTL_raster_A3_sheets.pdf` | `13D822CF828CCCC6CD21B19EC3C410F0EA89AEF440AECA4C96248E86C08B5B38` | PDF | canonical GitHub #409 execution-input rule admits modified-vehicle PDF/image; post-inventory #409/5738808062 re-read proves this exact path/hash. It is not admitted from filename alone. | read-only observation | `APPROVED + ACTIVE` |
| `BVTL page-1 fidelity candidate` | `UNKNOWN` / possible `EVALUATOR_ONLY_GROUND_TRUTH` | `C:\Users\dkv\Downloads\BVTL_raster_A3_page1_fidelity_candidate.dxf` | `BF9984363A6B7B3FECF8FD5F80ED7218765109A64244DB49866B1B84DA5EBC39` | DXF | local artifact; role not proven by current GitHub evidence | `MUST_NOT_BE_USED_FOR_GENERATION=YES` until explicitly admitted | `UNKNOWN` |
| `BVTL Layout1` | `DISPOSABLE_CANDIDATE` / role not otherwise proven | `C:\Users\dkv\Downloads\BVTL_Layout1.dwg` | `25BE26C53F718D3E14FDD33193B2A69DE8B18CC5B3CEF10873D84D87D5D484F3` | DWG | local candidate; not source authority | no mutation without human gate | `DISPOSABLE` |

For any completed target DXF that is later proven to be evaluator ground truth, the invariant is `EVALUATOR_ONLY_GROUND_TRUTH` and `MUST_NOT_BE_USED_FOR_GENERATION=YES`; compare only after candidate freeze. All source/base drawings remain `SOURCE_MUTATION_ALLOWED=NO` unless GitHub explicitly changes that rule.

## Build/temp/evidence directories

| Path | Purpose | Owner | Persistence | Safe to delete automatically | Status |
|---|---|---|---|---|---|
| `C:\Users\dkv\Downloads\cad-agent-merge` | repository/worktree | Git | durable | `NO` | `CANONICAL + ACTIVE` |
| `C:\Users\dkv\Downloads\cad-agent-merge\autocad_plugin\CadAgent.AutoCAD2027\bin\x64\Release\net10.0-windows` | repo build output | .NET build | reproducible but local | `UNKNOWN` | `REPO_BUILD` |
| `D:\Cad agent temp\cadagent-build`; `D:\Cad agent temp\cadagent-build-ed1db3c` | disposable plugin builds | local build/test | disposable | `UNKNOWN` | `DISPOSABLE` |
| `C:\temp` | default/legacy IPC and retained evidence root | FileIPC/.NET clients and tests | retained local | `NO` without ownership check | `HISTORICAL / DEFAULT; active currentness UNKNOWN` |
| `D:\Cad agent temp\pytest-of-dkv`; `D:\Cad agent temp\pytest-temp` | pytest/test IPC/LSP artifacts | tests | disposable/retained for evidence | `UNKNOWN` | `DISPOSABLE` |
| `C:\temp\artifacts` | retained forensic/evidence artifacts | local evidence workflows | retained | `NO` | `FORENSIC_EVIDENCE` |
| `C:\Users\dkv\AppData\Local\Temp\cad-agent-r6-204-*` | isolated test roots | tests | disposable | `UNKNOWN` | `DISPOSABLE` |

## Path movement/copy history

No actual file move/copy was proven by the fresh local Git/history inspection. Do not derive provenance from matching names, directory labels, timestamps, or equal sizes.

| Artifact | From | To | Action | Old SHA256 | New SHA256 | Why | When/checkpoint | Current canonical location | Status |
|---|---|---|---|---|---|---|---|---|---|
| `mcp_dispatch.lsp` | `UNKNOWN / NOT_PROVEN` | repo copy above | `UNKNOWN` | `UNKNOWN` | `D80190...CB222` | no move evidence | local Git/history search 2026-09-19 | repo path above | `CANONICAL + ACTIVE` |
| `CadAgent.AutoCAD2027.dll` | repo/build roots | disposable build roots | `BUILD`, not a proven copy/move | `UNKNOWN` | hashes above | build output paths | timestamps 2026-09-17/18 | no loaded canonical runtime path proven | `UNKNOWN` |
| FileIPC root | `C:\temp` default | isolated test roots | `UNKNOWN` | n/a | n/a | explicit test binding exists in code/tests | current code/history | active root not proven | `UNKNOWN` |
| BVTL drawings/PDF/DXF | `UNKNOWN` | Downloads paths above | `UNKNOWN` | hashes above where readable | local evidence only | no provenance proof from Git | current filesystem | base/target rows above | `UNKNOWN` where not admitted |

## Environment bindings

| Name | Value or redaction | Scope | Consumer | Default if unset | Current status |
|---|---|---|---|---|---|
| `CAD_AGENT_FILE_IPC_DIR` | unset | process environment | Python FileIPC client | `C:\temp` | `UNKNOWN / NOT_VERIFIED` |
| `CAD_AGENT_DOTNET_IPC_DIR` | unset | process environment | .NET IPC client/plugin | `C:\temp` | `UNKNOWN / NOT_VERIFIED` |
| `CAD_AGENT_AUTOCAD_HWND` | unset | process environment | live AutoCAD guards | none; live preflight required | `UNKNOWN` |
| `CAD_AGENT_AUTOCAD_LISP_PATH` | unset | process environment | LSP loader/live guards | none; live preflight required | `UNKNOWN` |
| `CAD_AGENT_FILE_IPC` | unset | process environment | live FileIPC guards | none; live preflight required | `UNKNOWN` |
| `CAD_AGENT_TESSERACT_CMD` | unset | process environment | OCR/bootstrap | `C:\Program Files\Tesseract-OCR\tesseract.exe` | `APPROVED` default path verified; exact binary reports 5.4.0.20240606 |
| `CAD_AGENT_BRIDGE_TOKEN` | `SECRET_REDACTED / NOT_RECORDED` | process environment | local bridge, if configured | `UNKNOWN` | `UNKNOWN` |
| `CAD_AGENT_LOCAL_MCP_TOKEN` | `SECRET_REDACTED / NOT_RECORDED` | process environment | local MCP, if configured | `UNKNOWN` | `UNKNOWN` |

## Current runtime chain

Known current chain, with unproven edges marked:

```text
repo C:\Users\dkv\Downloads\cad-agent-merge
  -> repo x64 Release DLL FE8F...A730F (on disk; not proven loaded)
  -> AutoCAD 2027 PID 21320 (CadAgent DLL not observed; loaded identity UNKNOWN)

repo mcp_integration_lib\mcp_dispatch.lsp
  -> trusted runtime copy C:\cad-agent\trusted-dispatcher\mcp_dispatch.lsp (same SHA256)
  -> fresh raw-LISP execution/currentness proof in AutoCAD PID 21320/HWND 525948

Python FileIPC client
  -> default C:\temp unless CAD_AGENT_FILE_IPC_DIR is explicitly bound
  -> autocad_mcp_cmd_*.json
  -> AutoCAD dispatcher/plugin
  -> autocad_mcp_result_*.json

Python/.NET IPC client
  -> default C:\temp unless CAD_AGENT_DOTNET_IPC_DIR is explicitly bound
  -> cadagent_dotnet_request_*.json
  -> plugin CommandContext
  -> cadagent_dotnet_result_*.json

BASE_PRODUCT_INPUT BVTL.dwg
  + TARGET_OBSERVATION BVTL_raster_A3_sheets.pdf
  -> Phase-4 correspondence experiment; completed target DXF is evaluator-only when explicitly admitted
```

## Known stale/obsolete locations

| Location / identity | Finding | Classification |
|---|---|---|
| `D:\Cad agent temp\luna-readonly-lsp-load-20260919.scr` | referenced by current AutoCAD command line but missing on disk | `STALE / UNKNOWN` |
| `C:\Users\dkv\Downloads\cad-agent-merge\autocad_plugin\CadAgent.AutoCAD2027\bin\Release\net10.0-windows\CadAgent.AutoCAD2027.dll` | older/different hash from current x64 Release output; not observed loaded | `STALE` |
| `D:\Cad agent temp\pytest-of-dkv\...\mcp_dispatch.lsp`, `D:\Cad agent temp\pytest-temp\...\mcp_dispatch.lsp` | zero/28-byte test stubs; not canonical LSP | `DISPOSABLE` |
| `C:\temp\cadagent_dotnet_request_*.json` and result files dated 2026-09-11 through 2026-09-18 | retained historical request/result artifacts; ownership/currentness not established | `HISTORICAL / UNKNOWN`; do not clear here |
| Detached and dated alternate worktrees listed above | not current primary worktree | `HISTORICAL` |

## Mandatory preflight for future Luna sessions

Before rediscovering anything, first read this inventory.

Then verify only currentness-sensitive fields:

- Git `origin/main`, current HEAD/branch/status.
- AutoCAD PID/HWND/title.
- Active drawing path, hash, and currentness.
- Currently loaded DLL path/hash using actual process/module evidence.
- Currently loaded LSP identity if observable.
- Active FileIPC and DotNet IPC roots.
- Relevant environment binding.
- Target/base hashes and admission/currentness.

If unchanged: **reuse the recorded inventory**. Do **not** rescan the machine.

Only rediscover a fact when `STATUS=UNKNOWN`, `CURRENTNESS_CHECK=FAILED`, or `PROVEN_DRIFT=YES`.

## Maintenance rule

This file is **not runtime authority**. GitHub/runtime evidence still proves current truth.

Whenever a future Luna epoch proves one of these materially changed, update this same inventory file: repo/worktree path; DLL path/hash; loaded DLL; LSP path/hash; trusted runtime copy; IPC root/default; AutoCAD version/profile; source/base/target path/hash; artifact move/copy; or MCP bridge path.

Record:

`LAST_VERIFIED_AT`
`VERIFIED_BY_CHECKPOINT`
`REPLACED_VALUE`
`NEW_VALUE`
`REASON`

Do not create a second inventory file.

## Verification history

| Date | Checkpoint / evidence | Result |
|---|---|---|
| 2026-09-19 | Fresh GitHub read of `origin/main` and current #409; post-inventory checkpoint #409/5738282459 | trusted/runtime LSP refresh: `C:\cad-agent\trusted-dispatcher\mcp_dispatch.lsp`, source/deployed SHA equality, exact raw-LISP execution and root-content readback PASS |
| 2026-09-19 | Runtime transition | `inventory snapshot -> trusted LSP refresh -> explicit trust -> fresh runtime load/currentness PASS` |
| 2026-09-19 | #409/5738282459 session snapshot | PID `21320`, HWND `525948`, active `BVTL.dwg`; PID/HWND are `EPHEMERAL_SESSION_FACT`; no ping/`drawing_get_variables` was run in this post-inventory checkpoint |
| 2026-09-19 | #409 post-662 root/timeout follow-up | active FileIPC/DotNet root currentness remains `UNKNOWN / NOT_VERIFIED`; later missing-root, timeout, and DotNet module-absence evidence was not promoted to a usable runtime |
| 2026-09-19 | Fresh GitHub read of `origin/main`, #291, #305, #429 latest corrections, and #409 latest checkpoints | current product/runtime boundary re-established; GitHub treated as canonical |
| 2026-09-19 | `git status`, branch/HEAD, remote, and worktree census | clean before edit; current branch/head recorded; no unrelated file changes |
| 2026-09-19 | AutoCAD process, WMI command line, module census, registry profile/trust read | PID/HWND/title/path and trust values recorded; loaded CadAgent DLL remains unproven; LSP currentness is separately proven by #409/5738282459 |
| 2026-09-19 | SHA256 of readable DLL, LSP, BAK, PDF, DXF, and candidate DWG artifacts | hashes recorded above; active BVTL DWG remained locked/unreadable |
| 2026-09-19 | relevant environment read | IPC overrides unset; bridge token values intentionally not read |
| 2026-09-19 | `git diff --check` and one-file write-set validation | required before commit; full product/live verification intentionally not run |

Full `scripts\verify.ps1` and live CAD gates were not run because this task is bounded documentation-only discovery and must not retry or mutate the live CAD session. Missing/unknown runtime facts are explicitly marked rather than inferred.
