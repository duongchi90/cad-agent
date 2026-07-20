"""CLI Phase 1 for a real CAD drawing image.

Example:
    .venv\\Scripts\\python -m primitive_ir_lib.run_image ^
      --image drawing.png --output output/primitive_ir.json ^
      --scale-mm-per-px 0.0917 --ocr-roi 620,325,860,385

A scale is deliberately required.  Automatic calibration from noisy OCR can
silently produce incorrect CAD coordinates; use a verified known dimension
until a drawing has passed calibration validation.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import pytesseract

from .assemble import build_document
from .calibration import Calibration
from .calibration_registry import get_verified_scale
from .cross_validation import cross_validate
from .geometry_extraction import extract_raw_geometry
from .io_utils import save_document
from .line_merging import merge_collinear_lines
from .text_extraction import extract_text_tesseract

Bbox = Tuple[int, int, int, int]


def _parse_roi(value: str) -> Bbox:
    try:
        values = tuple(int(item.strip()) for item in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("ROI phải có dạng x0,y0,x1,y1") from exc
    if len(values) != 4 or values[0] >= values[2] or values[1] >= values[3]:
        raise argparse.ArgumentTypeError("ROI phải có dạng x0,y0,x1,y1 với x0<x1 và y0<y1")
    return values  # type: ignore[return-value]


def _configure_tesseract(command: Optional[str]) -> None:
    if command:
        if not os.path.isfile(command):
            raise FileNotFoundError(f"Không thấy tesseract.exe: {command}")
        pytesseract.pytesseract.tesseract_cmd = command
        return

    known_windows_path = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
    if os.path.isfile(known_windows_path):
        pytesseract.pytesseract.tesseract_cmd = known_windows_path


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(
    image_path: str,
    output_path: str,
    scale_mm_per_px: float,
    preset: str = "real_scan_tuned_v1",
    ocr_rois: Optional[List[Bbox]] = None,
    tesseract_cmd: Optional[str] = None,
    merge_lines: bool = False,
) -> str:
    """Extract a validated Primitive IR JSON from one PNG/JPG drawing image."""
    if scale_mm_per_px <= 0:
        raise ValueError("scale_mm_per_px phải lớn hơn 0")
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Không thấy ảnh đầu vào: {image_path}")

    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Không đọc được ảnh bằng OpenCV: {image_path}")

    raw_geometry = extract_raw_geometry(image, preset=preset)
    raw_texts = []
    if ocr_rois:
        _configure_tesseract(tesseract_cmd)
        raw_texts = extract_text_tesseract(image, roi_boxes=ocr_rois)

    raw_lines = raw_geometry.lines
    if merge_lines:
        raw_lines = merge_collinear_lines(raw_lines, blocking_texts=raw_texts, image_bgr=image)

    calibration = Calibration(
        unit="mm",
        pixel_to_unit_scale=scale_mm_per_px,
        origin_px=(0.0, float(image.shape[0])),
        method="manual_override",
        reference_note=(
            "Scale supplied via --scale-mm-per-px; verify against a known "
            "dimension before using output for production DXF."
        ),
    )
    document = build_document(
        file_name=os.path.basename(image_path),
        page_index=0,
        image_width_px=image.shape[1],
        image_height_px=image.shape[0],
        calibration=calibration,
        raw_lines=raw_lines,
        raw_circles=raw_geometry.circles,
        raw_texts=raw_texts,
        sha256=_sha256(image_path),
    )
    document.cross_validations = cross_validate(raw_texts, raw_lines, calibration)

    output_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(output_dir, exist_ok=True)
    save_document(document, output_path)
    return output_path


def _configure_console_output() -> None:
    """Keep Vietnamese CLI output readable in legacy Windows terminals."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def main() -> int:
    _configure_console_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Ảnh bản vẽ PNG/JPG")
    parser.add_argument("--output", required=True, help="Đường dẫn Primitive IR JSON")
    parser.add_argument("--scale-mm-per-px", type=float,
                        help="Tỷ lệ mm/px đã xác minh từ kích thước chuẩn")
    parser.add_argument("--calibration-registry", help="Hash-bound calibration registry JSON")
    parser.add_argument("--calibration-id", help="Verified calibration record ID")
    parser.add_argument("--preset", default="real_scan_tuned_v1",
                        choices=("default", "real_scan_tuned_v1"))
    parser.add_argument("--ocr-roi", action="append", type=_parse_roi, default=[],
                        help="ROI OCR: x0,y0,x1,y1; có thể truyền nhiều lần")
    parser.add_argument("--tesseract-cmd", help="Đường dẫn tesseract.exe nếu không ở PATH")
    parser.add_argument("--merge-lines", action="store_true",
                        help="Bật merge + witness split trước khi assemble IR")
    args = parser.parse_args()

    try:
        if args.calibration_registry:
            if not args.calibration_id or args.scale_mm_per_px is not None:
                parser.error("Registry mode requires --calibration-id and no --scale-mm-per-px")
            scale_mm_per_px = get_verified_scale(Path(args.calibration_registry), args.calibration_id, Path(args.image))
        elif args.scale_mm_per_px is not None:
            scale_mm_per_px = args.scale_mm_per_px
        else:
            parser.error("Supply --scale-mm-per-px or a verified calibration registry")
        result = run(
            image_path=args.image,
            output_path=args.output,
            scale_mm_per_px=scale_mm_per_px,
            preset=args.preset,
            ocr_rois=args.ocr_roi,
            tesseract_cmd=args.tesseract_cmd,
            merge_lines=args.merge_lines,
        )
    except (FileNotFoundError, ValueError, pytesseract.TesseractNotFoundError) as exc:
        parser.error(str(exc))
    print(f"Primitive IR saved: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
