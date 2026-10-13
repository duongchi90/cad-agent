# BLIND_FINDINGS: Independent Binary Inspection Findings (Pre-Source Reveal)

- **Document ID:** `REA_TRUE_BLIND_FINDINGS_V1`
- **Executor Role:** `ANTIGRAVITY_REA_BENCHMARK_AUDITOR_AND_TRUE_BLIND_VALIDATOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`
- **Target Binary A:** `C:\Tools\ghidra_12.1.4_PUBLIC\docs\GhidraClass\ExerciseFiles\VersionTracking\WallaceSrc.exe`
- **Binary A SHA256:** `168a175ccf74e80899d2519bbe6e1ae8b0fa2489af70e8cc0720afab1ad8b0ab`
- **Target Binary B:** `C:\Tools\ghidra_12.1.4_PUBLIC\docs\GhidraClass\ExerciseFiles\VersionTracking\WallaceVersion2.exe`
- **Binary B SHA256:** `94510664e6578bec7391d6023af414e2d2d8c4ff58ed3f618dd549ff648015cf`
- **Timestamp:** 2026-10-14T00:55:00+07:00
- **Source Inspection Status:** STRICTLY_UNREAD (Zero source files inspected prior to this document freeze)

---

## 1. Binary Architecture & Layout Findings

### Finding 1.1: Binary Target & Compilation Environment
- **CLAIM:** Both binaries are 32-bit x86 Windows PE executables compiled with Microsoft Visual C++ (MSVC) with debug/RTC runtime checks enabled.
- **EVIDENCE:**
  - PE header architecture: `x86`.
  - CRT strings observed: `f:\dd\vctools\crt_bld\self_x86\crt\src\crtexe.c`, `MSVCR100D.dll`, `__RTC_CheckEsp`.
  - Memory buffers initialized with `0xCCCCCCCC` (MSVC debug stack frame poison pattern).
- **CONFIDENCE:** `OBSERVED_BINARY` / `OBSERVED_PSEUDOCODE`.
- **FALSIFICATION:** Target is non-x86 or compiled with GCC/Clang.

---

## 2. Program Structure & Procedures Inventory

### Finding 2.1: Application Procedures Map (WallaceSrc.exe)
- **CLAIM:** The primary user-space program logic consists of 6 core functions operating around base `0x411400..0x411B00`:
  1. `FUN_00411a30` (`main`): Program entry orchestration.
  2. `FUN_00411700` (`init_characters` / `populate_list`): Populates linked list with 6 character names.
  3. `FUN_00411860` (`character_create_and_prepend`): Allocates character node (0x2C bytes) and prepends to head.
  4. `FUN_004117c0` (`character_list_process`): Traverses character list, assigns sequential IDs and randomized boolean flag.
  5. `FUN_004118f0` (`device_create_and_deploy`): Allocates device node (0x10 bytes), searches list for `"Wallace"`, and deploys.
  6. `FUN_00411440` (`Device::Device` constructor): Initializes device name, status flag, and target pointer.
  7. `FUN_00411570` (`Device::deploy` method): `__thiscall` member function setting deployment flag and target pointer.
  8. `FUN_004115d0` (`Device::print_status`): Formatted output function printing device deployment state.
- **EVIDENCE:** Decompiled pseudocode in `logs/app_decompiled.json`, caller xrefs traces from `0x411a30`.
- **CONFIDENCE:** `OBSERVED_PSEUDOCODE` / `OBSERVED_XREF`.
- **FALSIFICATION:** Program performs unrelated operations or has differing call topology.

---

## 3. Data Structure Recovery

### Finding 3.1: Character Node Data Structure
- **CLAIM:** Allocated size `0x2C` (44 bytes) via `operator new(0x2C)`. Layout:
  - `+0x00`: `int id` (Assigned 0, 1, 2, ... in list order)
  - `+0x04`: `char name[32]` (Fixed-size buffer, written via `strncpy_s(..., 0x20)`)
  - `+0x24`: `char / bool flag` (Assigned `rand() * 2 < 1` in V1; modulo in V2)
  - `+0x28`: `struct CharacterNode* next` (Singly linked list pointer)
- **EVIDENCE:** Decompilation of `FUN_00411860`, `FUN_004117c0`, `FUN_004118f0`.
- **CONFIDENCE:** `OBSERVED_PSEUDOCODE`.
- **FALSIFICATION:** Struct size is not 44 bytes, or fields are stored at different offsets.

### Finding 3.2: Device Data Structure
- **CLAIM:** Allocated size `0x10` (16 bytes) via `operator new(0x10)`. Layout:
  - `+0x00`: `const char* name` (Pointer to string literal `"Infrared Garden Gnome"`)
  - `+0x04`: `int field_4` (Initialized to 0)
  - `+0x08`: `char is_deployed` (0 = not deployed, 1 = deployed)
  - `+0x0C`: `struct CharacterNode* target` (Pointer to target Character, or NULL)
- **EVIDENCE:** Decompilation of constructor `FUN_00411440`, deploy method `FUN_00411570`, and status reporter `FUN_004115d0`.
- **CONFIDENCE:** `OBSERVED_PSEUDOCODE`.
- **FALSIFICATION:** Struct size is not 16 bytes, or fields do not represent device status and target.

---

## 4. Algorithmic Mechanism & Constants Recovery

### Finding 4.1: Character List Population & Prepend Order
- **CLAIM:** Global variable `DAT_00418138` holds the head of the character list. Six names are prepended in this sequence:
  1. `"Lord Victor Quartermaine"`
  2. `"Lady Tottington"`
  3. `"Were Rabbit"`
  4. `"Rabbit"`
  5. `"Gromit"`
  6. `"Wallace"`
  Because each node is prepended to the head, the resulting traversal order is reversed:
  `Wallace` (id 0) $\rightarrow$ `Gromit` (id 1) $\rightarrow$ `Rabbit` (id 2) $\rightarrow$ `Were Rabbit` (id 3) $\rightarrow$ `Lady Tottington` (id 4) $\rightarrow$ `Lord Victor Quartermaine` (id 5).
- **EVIDENCE:** `FUN_00411700` and `FUN_004117c0` decompilation.
- **CONFIDENCE:** `OBSERVED_PSEUDOCODE`.
- **FALSIFICATION:** List is appended rather than prepended, or names differ.

### Finding 4.2: Output Formatting
- **CLAIM:** Program emits a single formatted report line via `printf("%s %s deployed on %s\n", ...)`:
  - If deployed (`is_deployed != 0`): `"<Device Name> is deployed on <Target Name>"`
  - If not deployed (`is_deployed == 0`): `"<Device Name> is not deployed on anyone"`
- **EVIDENCE:** `FUN_004115d0` decompilation and string references at `0x416830`, `0x41684c`, `0x416858`.
- **CONFIDENCE:** `OBSERVED_PSEUDOCODE` / `OBSERVED_XREF`.
- **FALSIFICATION:** Output format differs.

---

## 5. Differential Binary Findings (WallaceSrc.exe vs WallaceVersion2.exe)

### Finding 5.1: Removal of CRT `rand()` Import
- **CLAIM:** `WallaceSrc.exe` imports `rand` from `MSVCR100D.dll` at `0x419338`. `WallaceVersion2.exe` removes `rand` from its import address table completely.
- **EVIDENCE:** Observed import table strings across both binaries.
- **CONFIDENCE:** `OBSERVED_BINARY`.
- **FALSIFICATION:** `rand()` is present in `WallaceVersion2.exe`.

### Finding 5.2: Modification of Character Flag Initialization
- **CLAIM:** In `WallaceSrc.exe` (`FUN_004117c0`), character flag is initialized non-deterministically:
  `*(bool *)(node + 0x24) = rand() * 2 < 1;`
  In `WallaceVersion2.exe` (`FUN_004117b0`), character flag is initialized deterministically:
  `*(char *)(node + 0x24) = (local_c % 3 == 0);` (Ghidra decompilation: `'\x01' - (local_c % 3 != 0)`).
- **EVIDENCE:** Decompilation of `0x4117c0` (V1) vs `0x4117b0` (V2).
- **CONFIDENCE:** `OBSERVED_PSEUDOCODE`.
- **FALSIFICATION:** Flag formula in V2 is not modulo 3 or differs from prediction.

### Finding 5.3: Modification of Device Deployment Condition
- **CLAIM:** In `WallaceSrc.exe` (`FUN_004118f0`), deployment target is selected strictly by name:
  `if (strcmp(node->name, "Wallace") == 0) deploy(device, node);`
  In `WallaceVersion2.exe` (`FUN_004118c0`), deployment condition is expanded with an OR clause:
  `if ((strcmp(node->name, "Wallace") == 0) || (node->flag != 0)) deploy(device, node);`
- **EVIDENCE:** Decompilation of `0x4118f0` (V1) vs `0x4118c0` (V2).
- **CONFIDENCE:** `OBSERVED_PSEUDOCODE`.
- **FALSIFICATION:** Condition in V2 does not check `node->flag`.
