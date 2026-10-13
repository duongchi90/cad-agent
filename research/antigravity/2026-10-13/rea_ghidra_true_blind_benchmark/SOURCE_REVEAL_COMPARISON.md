# SOURCE_REVEAL_COMPARISON: Blind Prediction vs Upstream Source Ground Truth

- **Document ID:** `REA_TRUE_BLIND_SOURCE_REVEAL_V1`
- **Executor Role:** `ANTIGRAVITY_REA_BENCHMARK_AUDITOR_AND_TRUE_BLIND_VALIDATOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`
- **Target Project:** Ghidra Version Tracking Exercise (`WallaceSrc.exe` vs `WallaceVersion2.exe`)
- **Upstream Source Path:** `C:\Tools\ghidra_12.1.4_PUBLIC\docs\GhidraClass\ExerciseFiles\VersionTracking\Source`
- **Blind Freeze Hash Verification:**
  - `BLIND_FINDINGS_SHA256`: `177eb74ca69e85c45f39fceb5694e19a0ee98e62f5cbfbab4b8901f24af1ec37`
  - `BLIND_BEHAVIORAL_SPEC_SHA256`: `fc5982e0878b1b46a98a7ef1cea7ce0ec155f64955e86eaa3e907418f91f1467`

---

## 1. Material Finding Comparison Inventory

| Item | Blind Finding (Frozen) | Source Ground Truth Revealed | Rating | Detailed Evaluation |
| :---: | :--- | :--- | :---: | :--- |
| **1** | **Target Architecture & Toolchain**<br>x86 PE32 MSVC with debug runtime checks | MSVC project `WinHelloCPP.vcxproj`, x86 debug configuration with `/RTC1` (`__RTC_CheckEsp`). | `EXACT` | Compiler, runtime checks, architecture, and memory poisoning pattern matched exactly. |
| **2** | **Procedures Topology**<br>8 procedures mapping entry, initialization, allocation, processing, and output. | Source defines: `main()`, `addPeople()`, `initializePeople()`, `addPerson()`, `deployGadget()`, `Gadget::Gadget()`, `Gadget::use()`, `Gadget::print()`. | `EXACT` | 1-to-1 correspondence across all 8 user-space procedures and their call hierarchy. |
| **3** | **Person Data Structure**<br>44 bytes (`0x2C`): `id` (+0x00), `name[32]` (+0x04), `is_special` (+0x24), `next` (+0x28). | `struct _person { int id; char name[32]; bool likesCheese; struct _person *next; };` | `EXACT` | Exact struct size (44 bytes), field ordering, offsets, buffer widths (32 bytes), and pointer link. |
| **4** | **Device / Gadget Structure**<br>16 bytes (`0x10`): `name` (+0x00), `field_4` (+0x04), `is_deployed` (+0x08), `target` (+0x0C). | `class Gadget { char *name; int type; bool deployed; Person *workingOn; };` | `EXACT` | Exact class layout (16 bytes), member offsets, types, and semantics. |
| **5** | **List Character Prepend Order**<br>Prepends 6 names starting with Quartermaine down to Wallace. | `addPeople()` calls `addPerson()` for Quartermaine, Tottington, Were Rabbit, Rabbit, Gromit, Wallace. | `EXACT` | Exact string names, exact prepend logic, and exact reverse traversal order. |
| **6** | **Output Formatting**<br>`printf("%s %s deployed on %s\n", name, status, target)` | `printf("%s %s deployed on %s\n", name, depstr, who)` where `depstr = deployed ? "is" : "is not"`, `who = deployed ? workingOn->name : "anyone"`. | `EXACT` | Format string, conditional status substitution, and target resolution match verbatim. |
| **7** | **Version Delta 1: CRT Import**<br>`WallaceSrc.exe` imports `rand()`; `WallaceVersion2.exe` removes `rand()`. | `Original/Wallace.cpp` calls `rand()`; `Mod1/Wallace.cpp` removes `rand()`. | `EXACT` | Import delta correctly predicted. |
| **8** | **Version Delta 2: Flag Initialization**<br>V1 assigns `rand() * 2 < 1`; V2 assigns `(index % 3 == 0)`. | V1: `people->likesCheese = (rand() * 2) < 1;`<br>V2: `people->likesCheese = ((index % 3) == 0);` | `EXACT` | Algorithmic logic and modulo 3 formula isolated without source access. |
| **9** | **Version Delta 3: Deployment Guard**<br>V1 checks `strcmp(...) == 0`; V2 checks `strcmp(...) == 0 \|\| node->flag`. | V1: `if (strcmp(pp->name, "Wallace")==0)`<br>V2: `if (strcmp(pp->name, "Wallace")==0 \|\| pp->likesCheese)` | `EXACT` | Branch expansion and boolean condition delta isolated cleanly. |
| **10** | **Domain Terminology (Semantic Gap)**<br>Inferred names: `Character`, `Device`, `is_special`. Source names: `Person`, `Gadget`, `likesCheese`. | Source names: `Person`, `Gadget`, `likesCheese`. | `FUNCTIONALLY_CORRECT` | Stripped binaries do not contain variable or struct names. Inferred domain semantics were functionally identical to author intent. |
