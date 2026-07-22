# AutoCAD Mechanical 2027 Target Implementation Plan

**Status:** Completed

**Base SHA:** `cc956f2c12b487ae48b4d3c28abf95593c2e3f0c`

**Completion Head SHA:** `4346e6e0bf7ea55a3fe138a9402550009c536f54`

**Verification command:** `scripts/verify.ps1`

**Verification result:** `PASS` on the Completion Head SHA: 295 offline tests,
zero failures/errors/skips; `autocad_mechanical` unavailable-state probe
reported 4 explicit skips.

**Required live gate result:** `autocad_mechanical` passed 4 tests on AutoCAD
Mechanical 2027. `real_data` remains unaffected and `NOT RUN` without an
approved private input.

## Steps

1. Add/adjust contracts so metadata and pytest register the Mechanical target.
2. Rename the live marker in tests and the shared verifier; update current
   canonical guidance without altering historical evidence.
3. Run the focused contracts, the AutoCAD Mechanical smoke gate, and the full
   verifier.
4. Record fresh evidence and close this plan with the implementation Head SHA.
