"""Build a local HTML index for PDF geometry benchmark review."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def build_report(benchmark_dir: Path, output_path: Path, overlay_dir_name: str = "overlays_filtered_100px") -> dict:
    baseline_path = benchmark_dir / "geometry_baseline.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    rows = []
    for document in baseline["documents"]:
        for page in document["pages"]:
            annotation_path = benchmark_dir / page["annotation_json"]
            annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
            page_name = Path(page["annotation_json"]).name.replace(".json", ".png")
            document_id = document["id"]
            rows.append({
                "document": document_id,
                "page": page["page"],
                "status": annotation.get("status", "unknown"),
                "raw_lines": page["raw_line_count"],
                "expected_lines": len(annotation.get("expected_lines", [])),
                "overlay": f"{overlay_dir_name}/{document_id}/{page_name}",
                "annotation": page["annotation_json"],
            })
    body = "\n".join(
        "<tr>"
        f"<td>{html.escape(row['document'])}</td><td>{row['page']}</td>"
        f"<td>{html.escape(row['status'])}</td><td>{row['raw_lines']}</td><td>{row['expected_lines']}</td>"
        f"<td><a href='{html.escape(row['overlay'])}'>overlay</a></td>"
        f"<td><a href='{html.escape(row['annotation'])}'>annotation</a></td>"
        "</tr>" for row in rows
    )
    document = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>CAD Agent PDF benchmark</title>
<style>body{{font-family:system-ui;margin:2rem}}table{{border-collapse:collapse}}th,td{{border:1px solid #bbb;padding:.45rem;text-align:left}}th{{background:#eee}}</style>
</head><body><h1>CAD Agent PDF geometry benchmark</h1>
<p>Red lines are predictions; green lines are reviewed ground truth. Open an annotation JSON, review it against the overlay, then set status to <code>annotated</code>.</p>
<table><thead><tr><th>Document</th><th>Page</th><th>Status</th><th>Raw lines</th><th>Expected</th><th>Overlay</th><th>Annotation</th></tr></thead><tbody>{body}</tbody></table>
</body></html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
    return {"pages": len(rows), "output": str(output_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overlay-dir-name", default="overlays_filtered_100px")
    args = parser.parse_args()
    output = args.output or args.benchmark_dir / "review_index.html"
    result = build_report(args.benchmark_dir, output, args.overlay_dir_name)
    print(f"Review report saved: {result['output']} ({result['pages']} pages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())