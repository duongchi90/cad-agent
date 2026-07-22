# Fidelity Layout Recovery Plan

**Status:** Executing

**Base SHA:** `8891bd83afc08d39e7a913438e5c7407cc430e25`

1. Add tests and a paper-coordinate transform for clean layout DXF export.
2. Add a resumable fidelity-PDF command that renders pages, writes clean DXFs,
   and keeps source underlays staging-only.
3. Add OCR/table/layout audit sidecars and page completeness reports.
4. Add a source-versus-layout vector edge overlay report and review state.
5. Preserve reviewed per-view calibration candidates as the sole input to a
   future model-view export; report unapproved candidates rather than applying
   them.
6. Run the approved private nine-page PDF, visually inspect the result, run
   the required checks, and record only fresh evidence.
7. Add a SHA-bound, private page-region proposal sidecar for a reviewed page;
   it is a required human-approval input to any future per-view work and never
   authorizes model export by itself.
