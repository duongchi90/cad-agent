# Solver Capacity Guard Plan

**Status:** Complete

**Base SHA:** `e627b813a04ad1b7f939f9515721bf118d554f75`

1. Add a regression for a document just above the solver capacity.
2. Return the existing explicit `too_many_unknowns` status before solver
   construction when the document exceeds capacity.
3. Run solver, DXF, and full verification tests.
4. Resume the approved private PDF and record the completed real-data result.
   Completed: page 5 reached DXF generation through the explicit fallback and
   passed a read-only AutoCAD Mechanical geometry review.
