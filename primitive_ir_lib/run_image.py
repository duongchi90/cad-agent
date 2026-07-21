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
import json
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import pytesseract

from .assemble import build_document
from .calibration import Calibration, auto_estimate_calibration
from .calibration_registry import add_record, get_verified_scale
from .cross_validation import cross_validate
from .geometry_extraction import extract_raw_geometry
from .io_utils import save_document
from .line_merging import merge_collinear_lines
from .text_extraction import detect_text_candidate_rois, extract_text_tesseract
from .view_calibration import detect_view_candidates

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
    scale_mm_per_px: Optional[float] = None,
    preset: str = "real_scan_tuned_v1",
    ocr_rois: Optional[List[Bbox]] = None,
    tesseract_cmd: Optional[str] = None,
    merge_lines: bool = False,
    auto_ocr_roi: bool = False,
    auto_calibrate: bool = False,
    calibration_registry_path: Optional[Path] = None,
    calibration_id: Optional[str] = None,
    view_candidates_output_path: Optional[str] = None,
    view_candidates_dpi: Optional[int] = None,
) -> str:
    """Extract a validated Primitive IR JSON from one PNG/JPG drawing image.

    scale_mm_per_px vẫn là cách được khuyến nghị (đã verify thủ công). Nếu
    không có, cần bật auto_calibrate=True để thử suy ra tỷ lệ tự động từ 1
    cặp (text kích thước, line đo được) tìm thấy qua OCR — xem cảnh báo an
    toàn trong auto_estimate_calibration(): kết quả này CHƯA được verify,
    không nên dùng thẳng cho DXF sản xuất mà không kiểm tra lại.
    """
    if scale_mm_per_px is not None and scale_mm_per_px <= 0:
        raise ValueError("scale_mm_per_px phải lớn hơn 0")
    if scale_mm_per_px is None and not auto_calibrate:
        raise ValueError("Cần scale_mm_per_px hoặc bật auto_calibrate=True")
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Không thấy ảnh đầu vào: {image_path}")

    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Không đọc được ảnh bằng OpenCV: {image_path}")

    raw_geometry = extract_raw_geometry(image, preset=preset)

    effective_rois = list(ocr_rois) if ocr_rois else []
    if auto_ocr_roi or (auto_calibrate and not effective_rois):
        detected = detect_text_candidate_rois(image)
        effective_rois = list({*effective_rois, *detected}) if effective_rois else detected
        print(f"[run-image] auto-ocr-roi: {len(detected)} vùng ứng viên được phát hiện tự động.")

    raw_texts = []
    if effective_rois:
        _configure_tesseract(tesseract_cmd)
        raw_texts = extract_text_tesseract(image, roi_boxes=effective_rois)

    raw_lines = raw_geometry.lines
    if merge_lines:
        raw_lines = merge_collinear_lines(raw_lines, blocking_texts=raw_texts, image_bgr=image)

    if view_candidates_output_path is not None:
        if view_candidates_dpi is None:
            raise ValueError("view_candidates_dpi is required with view_candidates_output_path")
        candidates = detect_view_candidates(raw_texts, raw_lines, image.shape[1], image.shape[0], dpi=view_candidates_dpi)
        candidates_path = Path(view_candidates_output_path)
        candidates_path.parent.mkdir(parents=True, exist_ok=True)
        candidates_path.write_text(json.dumps(candidates, indent=2) + "\n", encoding="utf-8")

    if scale_mm_per_px is not None:
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
    else:
        calibration = auto_estimate_calibration(raw_texts, raw_lines, image.shape[0], unit="mm")
        if calibration is None:
            raise ValueError(
                "auto_calibrate không tìm được cặp (dimension_value, line gần "
                "nhất) hợp lệ trong các ROI đã quét — cần cung cấp "
                "--scale-mm-per-px thủ công hoặc thêm --ocr-roi bao trùm 1 "
                "kích thước đã biết."
            )
        print(
            "[run-image] CẢNH BÁO: scale được suy tự động "
            f"({calibration.pixel_to_unit_scale} mm/px, method="
            f"{calibration.method}) — CHƯA được verify, chỉ dùng để test/"
            "khảo sát, không dùng thẳng cho DXF sản xuất."
        )
        if calibration_registry_path is not None and calibration_id is not None:
            add_record(
                calibration_registry_path,
                calibration_id,
                Path(image_path),
                calibration.pixel_to_unit_scale,
                evidence=calibration.reference_note or "auto_estimate_calibration",
                status="needs_verification",
            )
            print(
                f"[run-image] Đã ghi bản ghi calibration '{calibration_id}' "
                f"vào {calibration_registry_path} với status=needs_verification "
                "— cần người xác minh và đổi status='verified' trước khi dùng "
                "qua --calibration-registry."
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
    parser.add_argument("--auto-ocr-roi", action="store_true",
                        help="Tự động phát hiện vùng ứng viên chứa text (connected-"
                             "components) thay vì phải tự khoanh --ocr-roi bằng tay. "
                             "Có thể kết hợp với --ocr-roi (cộng dồn).")
    parser.add_argument("--auto-calibrate", action="store_true",
                        help="Suy tỷ lệ mm/px tự động từ 1 cặp (kích thước OCR đọc "
                             "được, line gần nhất) thay vì --scale-mm-per-px. KẾT QUẢ "
                             "CHƯA ĐƯỢC VERIFY — chỉ dùng để khảo sát/test, không dùng "
                             "thẳng cho DXF sản xuất. Kết hợp với --calibration-registry "
                             "+ --calibration-id để ghi lại kết quả (status=needs_verification) "
                             "cho việc xác minh sau.")
    parser.add_argument("--tesseract-cmd", help="Đường dẫn tesseract.exe nếu không ở PATH")
    parser.add_argument("--merge-lines", action="store_true",
                        help="Bật merge + witness split trước khi assemble IR")
    args = parser.parse_args()

    try:
        scale_mm_per_px: Optional[float] = None
        if args.auto_calibrate:
            if args.calibration_registry and not args.calibration_id:
                parser.error("--calibration-registry với --auto-calibrate cần thêm --calibration-id")
            if args.scale_mm_per_px is not None:
                parser.error("--auto-calibrate không dùng cùng --scale-mm-per-px")
        elif args.calibration_registry:
            if not args.calibration_id or args.scale_mm_per_px is not None:
                parser.error("Registry mode requires --calibration-id and no --scale-mm-per-px")
            scale_mm_per_px = get_verified_scale(Path(args.calibration_registry), args.calibration_id, Path(args.image))
        elif args.scale_mm_per_px is not None:
            scale_mm_per_px = args.scale_mm_per_px
        else:
            parser.error("Supply --scale-mm-per-px, --auto-calibrate, or a verified calibration registry")
        result = run(
            image_path=args.image,
            output_path=args.output,
            scale_mm_per_px=scale_mm_per_px,
            auto_ocr_roi=args.auto_ocr_roi,
            auto_calibrate=args.auto_calibrate,
            calibration_registry_path=Path(args.calibration_registry) if (args.auto_calibrate and args.calibration_registry) else None,
            calibration_id=args.calibration_id if args.auto_calibrate else None,
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
