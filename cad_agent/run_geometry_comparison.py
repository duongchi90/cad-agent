"""CLI for the offline deterministic geometry comparator."""

from __future__ import annotations

import argparse
from pathlib import Path

from .geometry_comparison_run import GeometryComparisonRunError, run_geometry_comparison


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m cad_agent.run_geometry_comparison")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--region-id", required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--cad-render", type=Path, required=True)
    parser.add_argument("--reference-package-sha256", required=True)
    parser.add_argument("--mutation-sha256", required=True)
    parser.add_argument("--anchors", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--previous-comparison", type=Path)
    parser.add_argument("--source-is-photograph", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = run_geometry_comparison(
            run_id=args.run_id,
            region_id=args.region_id,
            reference_image=args.reference,
            cad_image=args.cad_render,
            reference_package_sha256=args.reference_package_sha256,
            mutation_sha256=args.mutation_sha256,
            anchors_path=args.anchors,
            output_dir=args.output,
            previous_comparison_path=args.previous_comparison,
            source_is_photograph=args.source_is_photograph,
        )
    except GeometryComparisonRunError as exc:
        parser.error(str(exc))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_parser", "main"]
