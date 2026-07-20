"""Create geometry benchmark artifacts for one or more drawing images."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from .benchmark_pdf import _annotation_template, _circle_dict, _line_dict
from .geometry_extraction import extract_raw_geometry


def _read_image(image_path: Path):
    """Read Unicode Windows paths without relying on OpenCV imread path decoding."""
    return cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)


def benchmark_image(identifier: str, image_path: Path, output_dir: Path, preset: str) -> dict:
    image = _read_image(image_path)
    if image is None:
        raise FileNotFoundError(image_path)
    rendered_dir = output_dir / "rendered" / identifier
    geometry_dir = output_dir / "raw_geometry" / identifier
    annotation_dir = output_dir / "annotations" / identifier
    for directory in (rendered_dir, geometry_dir, annotation_dir):
        directory.mkdir(parents=True, exist_ok=True)
    copied_image = rendered_dir / "page_01.png"
    cv2.imwrite(str(copied_image), image)
    geometry = extract_raw_geometry(image, preset=preset)
    geometry_path = geometry_dir / "page_01.json"
    geometry_path.write_text(json.dumps({
        "schema_version": "1.0", "document_id": identifier, "page": 1,
        "image": {"width_px": image.shape[1], "height_px": image.shape[0]},
        "lines": [_line_dict(line) for line in geometry.lines],
        "circles": [_circle_dict(circle) for circle in geometry.circles],
    }, indent=2), encoding="utf-8")
    annotation_path = annotation_dir / "page_01.json"
    if not annotation_path.exists():
        annotation_path.write_text(json.dumps(_annotation_template(identifier, 1, copied_image, image), indent=2), encoding="utf-8")
    return {"id": identifier, "source_file": image_path.name, "pages": [{
        "page": 1, "rendered_png": str(copied_image.relative_to(output_dir)),
        "raw_geometry_json": str(geometry_path.relative_to(output_dir)),
        "annotation_json": str(annotation_path.relative_to(output_dir)),
        "image_width_px": image.shape[1], "image_height_px": image.shape[0],
        "raw_line_count": len(geometry.lines), "raw_circle_count": len(geometry.circles),
    }]}


def _parse_image(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--image must be id=path")
    identifier, raw_path = value.split("=", 1)
    path = Path(raw_path)
    if not identifier or not path.is_file():
        raise argparse.ArgumentTypeError(f"Image not found: {raw_path}")
    return identifier, path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, action="append", type=_parse_image)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--preset", choices=("default", "real_scan_tuned_v1"), default="real_scan_tuned_v1")
    args = parser.parse_args()
    report = {"preset": args.preset, "documents": [benchmark_image(identifier, path, args.output_dir, args.preset) for identifier, path in args.image]}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "geometry_baseline.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Image benchmark report saved: {args.output_dir / 'geometry_baseline.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())