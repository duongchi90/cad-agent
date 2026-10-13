# GHIDRA_OPERATING_PLAYBOOK: Performance, Operating Model, and Best Practices

## 1. Measured Performance & Latency Metrics on Windows 10/11 x64

| Operation Type | Measured Latency (Mean) | Operational Characteristics & Constraints |
| :--- | :---: | :--- |
| **Cold Binary Import (`inspect`)** | **37.7s** | Spawns Java VM, extracts PE headers, creates ephemeral project database, runs full auto-analysis pipeline. |
| **Warm Query / Procedure Search** | **2.8s** | Queries pre-analyzed metadata; fast lookup over mapped procedure symbols. |
| **Decompilation (`decompile`)** | **18.5s** | Imports binary into ephemeral project and runs native Ghidra decompiler on target procedure. |
| **Xrefs Query (`xrefs`)** | **17.2s** | Traces inbound code and data references within ephemeral project session. |

---

## 2. Operating Model Recommendation: Broad vs Targeted Queries

> [!IMPORTANT]
> **OPERATING DISCIPLINE: Few Broader Calls over Many Rapid CLI Queries**
> 
> Because the current Windows REA bridge invokes Ghidra headlessly via ephemeral project databases (`analyzeHeadless.bat`), **each CLI invocation incurs an ~18-second JVM startup and database initialization tax**.
> 
> - **Anti-Pattern (Avoid):** Issuing 50 fine-grained CLI commands in a tight sequential loop ($50 \times 18\text{s} = 900\text{s} = 15\text{ minutes}$).
> - **Recommended Pattern (Adopt):**
>   1. Use `inspect` once to capture the entire binary overview, segments, entry points, and procedure inventories.
>   2. Filter candidate procedures down to the 3–5 highest fan-in/fan-out functions.
>   3. Decompile only those high-value targets.
>   4. Combine evidence with source-assisted analysis or batch MCP commands whenever available.

---

## 3. Ghidra Project Hygiene
- All benchmark artifacts are compiled and stored in `C:\Tools\benchmarks\` (outside the Git repository tree).
- Ephemeral Ghidra projects (`~/.ghidra/` or temporary app data) are automatically deleted upon request termination.
- Zero raw Ghidra `.gpr` / `.rep` databases are committed to GitHub. Only distilled, evidence-grade JSON and Markdown artifacts are persisted.
