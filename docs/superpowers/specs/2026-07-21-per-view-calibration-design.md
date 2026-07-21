# Per-view calibration for mixed-scale scanned sheets

## Goal

Replace the unsafe assumption that one rendered PDF page has one CAD scale.
Scanned vehicle drawing sheets can contain views labelled `TL 1:40`, `TL 1:20`,
`TL 1:10`, `TL 1:8`, and `TL 1:5` on the same page.

## Scope

The page-level Primitive IR remains unchanged. A detected view is represented
as a separate child IR with its own crop-local pixel origin and calibration.
Each candidate has a bounding box, a parsed scale denominator, provenance from
an OCR scale label, and a `needs_verification` status. Content outside an
unambiguous view remains only in the page-level IR and receives no production
scale.

The conversion at render DPI `dpi` is:

`mm_per_px = denominator * 25.4 / dpi`

At 144 DPI, a `1:40` view therefore uses `7.055556 mm/px`.

## Detection and assignment

1. OCR text candidates are parsed for scale labels such as `TL 1:40` and
   `Tỷ lệ 1:8`; common OCR variants are normalized before parsing.
2. A label is associated only with a nearby drawing-region candidate. If no
   unambiguous region is found, the label remains an unassigned candidate.
3. The candidate crop is processed as its own IR; page-level primitives are
   not reprojected or mutated. Overlapping candidates are rejected.
4. Existing page-wide manual/registry calibration remains backward compatible.
   Per-view calibration never upgrades itself to `verified`.

## Output and safety

The page manifest records each candidate and child IR path. Review output
identifies unassigned labels, overlapping regions, and pages without a
calibrated view. DXF export must reject unverified or absent scale exactly as
it does for the existing registry path.

## Verification

- Unit-test parsing of clean and OCR-corrupted scale labels.
- Unit-test scale conversion at 144 DPI and region assignment boundaries.
- Keep existing page-wide calibration tests green.
- Re-run the five-PDF batch and report calibrated/unassigned primitive counts;
  do not claim production accuracy without reviewed references.
