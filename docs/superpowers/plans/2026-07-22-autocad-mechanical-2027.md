# AutoCAD Mechanical 2027 Target Implementation Plan

**Status:** Executing

**Base SHA:** `cc956f2c12b487ae48b4d3c28abf95593c2e3f0c`

**Verification command:** `scripts/verify.ps1`

**Required live gate:** `autocad_mechanical` must pass on the connected
AutoCAD Mechanical 2027 session. `real_data` remains unaffected and is
explicitly `NOT RUN` when no approved private input is supplied.

## Steps

1. Add/adjust contracts so metadata and pytest register the Mechanical target.
2. Rename the live marker in tests and the shared verifier; update current
   canonical guidance without altering historical evidence.
3. Run the focused contracts, the AutoCAD Mechanical smoke gate, and the full
   verifier.
4. Record fresh evidence and close this plan with the implementation Head SHA.
