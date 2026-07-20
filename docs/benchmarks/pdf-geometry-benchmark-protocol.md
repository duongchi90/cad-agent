# PDF geometry benchmark protocol

## Purpose

This benchmark measures the raw line detector before semantic recognition. It keeps source PDFs unchanged and stores all derived material under `demo_output/pdf_benchmark/`.

## Generate a baseline

```powershell
python -m primitive_ir_lib.benchmark_pdf `
  --pdf "document-id=C:\path\drawing.pdf" `
  --output-dir demo_output\pdf_benchmark `
  --dpi 144 --preset real_scan_tuned_v1
```

For every page the runner creates: rendered PNG, raw Hough geometry, and one annotation template. The relative path below `annotations/` always matches the one below `raw_geometry/`.

## Annotation convention

Set `status` to `annotated` only after review. Add a line as:

```json
{"p1_px": [x1, y1], "p2_px": [x2, y2]}
```

Coordinates are in the rendered PNG pixel space. Include each intended visible line once, using its visible endpoints. Endpoint direction does not matter. Do not put OCR text, construction noise, page borders, or uncertain strokes in `expected_lines`; record uncertainties in `notes` and leave the template `needs_annotation` until resolved.

## Evaluate

```powershell
python -m primitive_ir_lib.benchmark_evaluator `
  --annotations-dir demo_output\pdf_benchmark\annotations `
  --predictions-dir demo_output\pdf_benchmark\raw_geometry `
  --tolerance-px 6 `
  --output demo_output\pdf_benchmark\evaluation_report.json
```

The report uses one-to-one endpoint matching (orientation independent). `micro` is aggregated across reviewed pages. Unreviewed templates are listed separately and yield `precision: null` / `recall: null` when no reviewed page exists; these are intentionally not scores.

## Regression rule

Keep the same PDFs, DPI, preset, annotation files, and tolerance when comparing versions. A detector or merge change is acceptable only after inspecting false positives/misses and comparing the new report against the saved baseline.
## Visual review overlay

Create a review image with detector lines in red and verified lines in green:

```powershell
python -m primitive_ir_lib.benchmark_overlay `
  --image "rendered\document-id\page_01.png" `
  --prediction "raw_geometry\document-id\page_01.json" `
  --annotation "annotations\document-id\page_01.json" `
  --output "overlays\document-id\page_01.png"
```
## Local review index

Create a browser-openable index for all pages and overlays:

```powershell
python -m primitive_ir_lib.benchmark_report `
  --benchmark-dir "demo_output\pdf_benchmark"
```
## Interactive annotation

```powershell
python -m primitive_ir_lib.benchmark_annotate `
  --image "rendered\document-id\page_01.png" `
  --annotation "annotations\document-id\page_01.json"
```

Click two endpoints to add a green ground-truth line. Press `U` to undo, `S` to save the draft, `A` to save and mark the page `annotated`, or `Q` to leave without saving.
Pass the detector geometry for red reference candidates and suppress short Hough segments when needed:

```powershell
python -m primitive_ir_lib.benchmark_annotate `
  --image "rendered\bv-sa-lan\page_01.png" `
  --annotation "annotations\bv-sa-lan\page_01.json" `
  --prediction "raw_geometry\bv-sa-lan\page_01.json" `
  --min-length-px 100
```
Clicks snap to the nearest displayed Hough endpoint within 8 px by default. Use `--snap-px 0` to retain exact manual click coordinates.
## Verified calibration registry

Use a hash-bound record when generating production Primitive IR so a scale cannot accidentally be reused for a different image:

```powershell
python -m primitive_ir_lib.run_image `
  --image "drawing.png" --output "primitive_ir.json" `
  --calibration-registry "docs\benchmarks\calibration_registry.json" `
  --calibration-id "drawing-id"
```

The supplied registry contains the verified `truck-2026-07-18` record. Other benchmark images remain geometry-only until a reviewed physical reference establishes their scale.
A page cannot be marked `annotated` without at least one verified line; the annotation tool and evaluator reject that state to prevent empty-label metrics.
Review/calibration queues are tracked in docs/benchmarks/review_queue.json and docs/benchmarks/calibration_queue.json.
