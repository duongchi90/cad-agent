"""CLI entry point for the offline Dimension Observer."""

from __future__ import annotations

import argparse
from pathlib import Path

from cad_agent.dimension_observer_run import run_dimension_observer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run_dimension_observer")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--view-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ocr-lang", default="vie+eng")
    parser.add_argument("--tesseract-cmd")
    parser.add_argument("--semantic-anchors", type=Path)
    parser.add_argument("--profile", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = run_dimension_observer(
        run_id=args.run_id,
        source_image=args.source,
        page_id=args.page_id,
        view_id=args.view_id,
        output_dir=args.output,
        ocr_lang=args.ocr_lang,
        tesseract_cmd=args.tesseract_cmd,
        semantic_anchors_path=args.semantic_anchors,
        profile_path=args.profile,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
