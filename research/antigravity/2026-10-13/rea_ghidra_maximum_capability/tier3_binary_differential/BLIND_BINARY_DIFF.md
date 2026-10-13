# BLIND_BINARY_DIFF: Tier 3 Differential Analysis

## 1. Structural Comparison (Build A vs Build B)

| Artifact Metric | Build A (`tolerance_guard_v1.exe`) | Build B (`tolerance_guard_v2.exe`) | Delta Classification |
| :--- | :--- | :--- | :---: |
| **SHA256** | `773616ee...` | `6cc4a730...` | **DIFFERENT** |
| **PE Image Size** | 3,072 bytes | 3,072 bytes | Identical PE alignment |
| **Import / Export Table** | 0 imports (nodefaultlib) | 0 imports (nodefaultlib) | Unchanged |
| **Section Count** | 3 (`.text`, `.rdata`, `.data`) | 3 (`.text`, `.rdata`, `.data`) | Unchanged |
| **.text Section Size** | 0x200 bytes | 0x200 bytes | Unchanged |
| **Procedure Count** | 5 procedures | 5 procedures | Unchanged |

---

## 2. Differential Hypothesis & Causal Change Reconstruction

### Candidate Changed Functions
1. **Target Function 1 (Normalization Helper):**
   - **RANK:** `HIGH_PROBABILITY_CHANGED`
   - **Old Behavior (Build A):** Function loads two vector coordinates, computes sum of squares $x^2 + y^2$, and executes scalar double division without branching.
   - **New Behavior (Build B):** Function introduces a new floating-point comparison against constant threshold $10^{-12}$ (`0x3d719799812dea11`). If less, it immediately returns immediate constant `-10` (`0xFFFFFFF6`).
2. **Target Function 2 (Caller / Validator Pipeline):**
   - **RANK:** `HIGH_PROBABILITY_CHANGED`
   - **Old Behavior (Build A):** Calls normalization helper ignoring return value.
   - **New Behavior (Build B):** Checks return value from normalization helper and propagates non-zero error codes up the call stack.

---

## 3. Predicted User-Visible Effect & Failing Test Oracle
- **Failing Test Prediction:**
  Passing degenerate vector inputs $(0.0, 0.0)$ to the tolerance validation routine.
  - On `BUILD_A`: Emits floating-point singularity / NaN without clean error handling.
  - On `BUILD_B`: Cleanly halts and returns exit code `-10`.
