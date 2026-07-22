# Solver Capacity Guard Plan

**Status:** Executing

**Base SHA:** `e627b813a04ad1b7f939f9515721bf118d554f75`

1. Add a regression for a document just above the solver capacity.
2. Return the existing explicit `too_many_unknowns` status before solver
   construction when the document exceeds capacity.
3. Run solver, DXF, and full verification tests.
4. Resume the approved private PDF and record the completed real-data result.
