"""Create one Primitive IR JSON per page of a PDF drawing.

Example:
    python -m primitive_ir_lib.run_pdf --pdf drawing.pdf --output-dir output/pdf_ir \
      --scale-mm-per-px 0.0917 --dpi 144 --merge-lines
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import fitz

from .run_image import run


def _configure_console_output() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def run_pdf(
    pdf_path: Path,
    output_dir: Path,
    scale_mm_per_px: float,
    dpi: int = 144,
    preset: str = "real_scan_tuned_v1",
    merge_lines: bool = False,
) -> dict:
    """Render each PDF page locally and emit a validated Primitive IR JSON."""
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)
    if dpi <= 0:
        raise ValueError("dpi must be positive")
    if scale_mm_per_px <= 0:
        raise ValueError("scale_mm_per_px must be positive")

    render_dir = output_dir / "rendered"
    ir_dir = output_dir / "primitive_ir"
    render_dir.mkdir(parents=True, exist_ok=True)
    ir_dir.mkdir(parents=True, exist_ok=True)
    scale = dpi / 72.0
    manifest = {"source_pdf": pdf_path.name, "render_dpi": dpi, "scale_mm_per_px": scale_mm_per_px, "pages": []}
    document = fitz.open(str(pdf_path))
    try:
        for index, page in enumerate(document, start=1):
            image_path = render_dir / f"page_{index:02d}.png"
            page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).save(str(image_path))
            output_path = ir_dir / f"page_{index:02d}.json"
            run(
                image_path=str(image_path), output_path=str(output_path),
                scale_mm_per_px=scale_mm_per_px, preset=preset,
                merge_lines=merge_lines,
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            manifest["pages"].append({
                "page": index,
                "rendered_png": str(image_path.relative_to(output_dir)),
                "primitive_ir": str(output_path.relative_to(output_dir)),
                "primitive_count": len(payload["primitives"]),
                "cross_validation_count": len(payload["cross_validations"]),
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
    parser.add_argument("--scale-mm-per-px", required=True, type=float)
    parser.add_argument("--dpi", type=int, default=144)
    parser.add_argument("--preset", choices=("default", "real_scan_tuned_v1"), default="real_scan_tuned_v1")
    parser.add_argument("--merge-lines", action="store_true")
    args = parser.parse_args()
    manifest = run_pdf(args.pdf, args.output_dir, args.scale_mm_per_px, args.dpi, args.preset, args.merge_lines)
    print(f"PDF Primitive IR saved: {args.output_dir / 'manifest.json'} ({len(manifest['pages'])} pages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())