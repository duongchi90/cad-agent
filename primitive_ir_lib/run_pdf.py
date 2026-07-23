"""Create one Primitive IR JSON per page of a PDF drawing.

Example:
    python -m primitive_ir_lib.run_pdf --pdf drawing.pdf --output-dir output/pdf_ir \
      --scale-mm-per-px 0.0917 --dpi 144 --merge-lines

    # Không biết tỷ lệ, không muốn tự khoanh ROI OCR:
    python -m primitive_ir_lib.run_pdf --pdf drawing.pdf --output-dir output/pdf_ir \
      --auto-ocr-roi --auto-calibrate --dpi 144
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import fitz

from .calibration_registry import get_verified_scale
from .run_image import run


def _configure_console_output() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def run_pdf(
    pdf_path: Path,
    output_dir: Path,
    scale_mm_per_px: Optional[float] = None,
    dpi: int = 144,
    preset: str = "real_scan_tuned_v1",
    merge_lines: bool = False,
    auto_ocr_roi: bool = False,
    auto_calibrate: bool = False,
    calibration_registry_path: Optional[Path] = None,
    calibration_id_prefix: Optional[str] = None,
) -> dict:
    """Render each PDF page locally and emit a validated Primitive IR JSON.

    scale_mm_per_px vẫn là cách khuyến nghị (đã verify). Nếu để None, cần
    auto_calibrate=True — mỗi trang PDF là 1 ảnh khác nhau nên tỷ lệ được
    suy riêng cho từng trang (không giả định các trang cùng scale), và nếu
    có calibration_registry_path thì mỗi trang ghi 1 record riêng với id
    "{calibration_id_prefix}_page{N:02d}", status=needs_verification — xem
    cảnh báo an toàn trong run_image.run()/auto_estimate_calibration().
    """
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)
    if dpi <= 0:
        raise ValueError("dpi must be positive")
    if scale_mm_per_px is not None and scale_mm_per_px <= 0:
        raise ValueError("scale_mm_per_px must be positive")
    if scale_mm_per_px is None and not auto_calibrate:
        raise ValueError("Cần scale_mm_per_px hoặc bật auto_calibrate=True")
    if auto_calibrate and calibration_registry_path is not None and not calibration_id_prefix:
        raise ValueError("calibration_registry_path cần đi kèm calibration_id_prefix")

    render_dir = output_dir / "rendered"
    ir_dir = output_dir / "primitive_ir"
    render_dir.mkdir(parents=True, exist_ok=True)
    ir_dir.mkdir(parents=True, exist_ok=True)
    scale = dpi / 72.0
    manifest = {
        "source_pdf": pdf_path.name,
        "render_dpi": dpi,
        "scale_mm_per_px": scale_mm_per_px if scale_mm_per_px is not None else "auto",
        "pages": [],
    }
    document = fitz.open(str(pdf_path))
    try:
        for index, page in enumerate(document, start=1):
            image_path = render_dir / f"page_{index:02d}.png"
            page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).save(str(image_path))
            output_path = ir_dir / f"page_{index:02d}.json"
            view_candidates_path = ir_dir / f"page_{index:02d}.view_candidates.json"
            page_calibration_id = (
                f"{calibration_id_prefix}_page{index:02d}"
                if (auto_calibrate and calibration_registry_path is not None)
                else None
            )
            run(
                image_path=str(image_path), output_path=str(output_path),
                scale_mm_per_px=scale_mm_per_px, preset=preset,
                merge_lines=merge_lines,
                auto_ocr_roi=auto_ocr_roi,
                auto_calibrate=auto_calibrate,
                calibration_registry_path=calibration_registry_path,
                calibration_id=page_calibration_id,
                view_candidates_output_path=str(view_candidates_path),
                view_candidates_dpi=dpi,
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            manifest["pages"].append({
                "page": index,
                "rendered_png": str(image_path.relative_to(output_dir)),
                "primitive_ir": str(output_path.relative_to(output_dir)),
                "primitive_count": len(payload["primitives"]),
                "cross_validation_count": len(payload["cross_validations"]),
                "calibration_method": payload["calibration"]["method"],
                "scale_mm_per_px": payload["calibration"]["pixel_to_unit_scale"],
                "scale_label_candidates": json.loads(view_candidates_path.read_text(encoding="utf-8")),
            })
    finally:
        document.close()
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    _configure_console_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--scale-mm-per-px", type=float,
                        help="Tỷ lệ mm/px đã xác minh, áp dụng cho mọi trang")
    parser.add_argument("--calibration-registry", type=Path,
                        help="Hash-bound calibration registry JSON (verified scale, mode thủ công)")
    parser.add_argument("--calibration-id",
                        help="Verified calibration record ID (registry mode thủ công, không dùng cùng --auto-calibrate)")
    parser.add_argument("--auto-ocr-roi", action="store_true",
                        help="Tự động phát hiện vùng ứng viên chứa text thay vì cần --ocr-roi thủ công")
    parser.add_argument("--auto-calibrate", action="store_true",
                        help="Suy tỷ lệ mm/px tự động cho TỪNG TRANG (mỗi trang 1 ảnh khác nhau). "
                             "KẾT QUẢ CHƯA VERIFY — chỉ dùng để khảo sát/test. Kết hợp với "
                             "--calibration-registry + --calibration-id (dùng làm prefix, mỗi "
                             "trang ghi record riêng '<id>_pageNN' status=needs_verification).")
    parser.add_argument("--dpi", type=int, default=144)
    parser.add_argument("--preset", choices=("default", "real_scan_tuned_v1"), default="real_scan_tuned_v1")
    parser.add_argument("--merge-lines", action="store_true")
    args = parser.parse_args()

    try:
        scale_mm_per_px: Optional[float] = None
        registry_for_run: Optional[Path] = None
        calibration_id_prefix: Optional[str] = None

        if args.auto_calibrate:
            if args.scale_mm_per_px is not None:
                parser.error("--auto-calibrate không dùng cùng --scale-mm-per-px")
            if args.calibration_registry and not args.calibration_id:
                parser.error("--calibration-registry với --auto-calibrate cần thêm --calibration-id (dùng làm prefix)")
            registry_for_run = args.calibration_registry
            calibration_id_prefix = args.calibration_id
        elif args.calibration_registry:
            if not args.calibration_id or args.scale_mm_per_px is not None:
                parser.error("Registry mode (verified) requires --calibration-id and no --scale-mm-per-px")
            # Chế độ thủ công: 1 registry record verified dùng chung cho cả PDF
            # (đại diện bởi chính file PDF gốc, không phải từng trang render).
            scale_mm_per_px = get_verified_scale(args.calibration_registry, args.calibration_id, args.pdf)
        elif args.scale_mm_per_px is not None:
            scale_mm_per_px = args.scale_mm_per_px
        else:
            parser.error("Supply --scale-mm-per-px, --auto-calibrate, or a verified calibration registry")

        manifest = run_pdf(
            args.pdf, args.output_dir, scale_mm_per_px, args.dpi, args.preset, args.merge_lines,
            auto_ocr_roi=args.auto_ocr_roi,
            auto_calibrate=args.auto_calibrate,
            calibration_registry_path=registry_for_run,
            calibration_id_prefix=calibration_id_prefix,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(f"PDF Primitive IR saved: {args.output_dir / 'manifest.json'} ({len(manifest['pages'])} pages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
