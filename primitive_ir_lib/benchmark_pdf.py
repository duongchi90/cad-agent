"""Render scanned PDFs and create reproducible geometry benchmark artifacts.

Example:
    python -m primitive_ir_lib.benchmark_pdf \
      --pdf sa-lan="C:\\drawings\\bv.pdf" \
      --output-dir demo_output\\pdf_benchmark

Each rendered page receives a raw-geometry JSON and an annotation template.
Images remain local; templates contain only the metadata and labels you enter.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Tuple

import cv2
import fitz
from pypdf import PdfReader

from .geometry_extraction import extract_raw_geometry


def _configure_console_output() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _parse_pdf(value: str) -> Tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--pdf phải có dạng id=đường_dẫn.pdf")
    identifier, raw_path = value.split("=", 1)
    path = Path(raw_path)
    if not identifier or not path.is_file():
        raise argparse.ArgumentTypeError(f"PDF không tồn tại: {raw_path}")
    return identifier, path


def _line_dict(line) -> dict:
    return {"id": line.id, "p1_px": list(line.p1_px), "p2_px": list(line.p2_px), "confidence": line.confidence}


def _circle_dict(circle) -> dict:
    return {"id": circle.id, "center_px": list(circle.center_px), "radius_px": circle.radius_px, "confidence": circle.confidence}


def _annotation_template(identifier: str, page_number: int, png_path: Path, image) -> dict:
    return {
        "schema_version": "1.0",
        "status": "needs_annotation",
        "source": {"document_id": identifier, "page": page_number, "rendered_png": str(png_path.name)},
        "image": {"width_px": image.shape[1], "height_px": image.shape[0]},
        "expected_lines": [],
        "expected_texts": [],
        "expected_witness_boundaries": [],
        "notes": "Add only verified ground truth. Coordinates are rendered-image pixels.",
    }


def benchmark_pdf(identifier: str, pdf_path: Path, output_dir: Path, dpi: int, preset: str) -> dict:
    scale = dpi / 72.0
    rendered_dir = output_dir / "rendered" / identifier
    geometry_dir = output_dir / "raw_geometry" / identifier
    annotation_dir = output_dir / "annotations" / identifier
    for directory in (rendered_dir, geometry_dir, annotation_dir):
        directory.mkdir(parents=True, exist_ok=True)

    document = fitz.open(str(pdf_path))
    reader = PdfReader(str(pdf_path))
    result = {"id": identifier, "source_file": pdf_path.name, "pages": []}
    for page_index, page in enumerate(document):
        page_number = page_index + 1
        png_path = rendered_dir / f"page_{page_number:02d}.png"
        page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).save(str(png_path))
        image = cv2.imread(str(png_path))
        if image is None:
            raise RuntimeError(f"OpenCV không đọc được PNG vừa render: {png_path}")
        started = time.perf_counter()
        geometry = extract_raw_geometry(image, preset=preset)
        elapsed = round(time.perf_counter() - started, 3)
        geometry_path = geometry_dir / f"page_{page_number:02d}.json"
        geometry_path.write_text(json.dumps({
            "schema_version": "1.0", "document_id": identifier, "page": page_number,
            "image": {"width_px": image.shape[1], "height_px": image.shape[0]},
            "lines": [_line_dict(line) for line in geometry.lines],
            "circles": [_circle_dict(circle) for circle in geometry.circles],
        }, indent=2), encoding="utf-8")
        annotation_path = annotation_dir / f"page_{page_number:02d}.json"
        if not annotation_path.exists():
            annotation_path.write_text(json.dumps(
                _annotation_template(identifier, page_number, png_path, image), indent=2), encoding="utf-8")
        native_text = reader.pages[page_index].extract_text() or ""
        result["pages"].append({
            "page": page_number,
            "rendered_png": str(png_path.relative_to(output_dir)),
            "raw_geometry_json": str(geometry_path.relative_to(output_dir)),
            "annotation_json": str(annotation_path.relative_to(output_dir)),
            "image_width_px": image.shape[1], "image_height_px": image.shape[0],
            "native_text_chars": len(native_text.strip()), "raw_line_count": len(geometry.lines),
            "raw_circle_count": len(geometry.circles), "geometry_seconds": elapsed,
        })
    return result


def main() -> int:
    _configure_console_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", action="append", required=True, type=_parse_pdf, help="id=đường_dẫn.pdf; có thể truyền nhiều lần")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--dpi", type=int, default=144)
    parser.add_argument("--preset", choices=("default", "real_scan_tuned_v1"), default="real_scan_tuned_v1")
    args = parser.parse_args()
    if args.dpi <= 0:
        parser.error("--dpi phải lớn hơn 0")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {"render_dpi": args.dpi, "preset": args.preset, "documents": []}
    for identifier, pdf_path in args.pdf:
        report["documents"].append(benchmark_pdf(identifier, pdf_path, args.output_dir, args.dpi, args.preset))
    report_path = args.output_dir / "geometry_baseline.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Benchmark report saved: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
