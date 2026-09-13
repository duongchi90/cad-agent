from __future__ import annotations

import copy
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz
import numpy as np

from primitive_ir_lib.geometry_extraction import RawGeometry, RawLine


class SemanticMultiplicityContractTests(unittest.TestCase):
    def test_region_proposal_preserves_geometry_occurrences_and_hashes_them(self) -> None:
        fidelity = importlib.import_module("cad_agent.fidelity")
        regions = {
            "regions": [
                {
                    "id": "main",
                    "bbox_px": [10, 10, 260, 120],
                    "purpose": "layout-reconstruction",
                    "geometry_occurrences": [
                        {"id": "row-a", "p1_px": [20.0, 30.0], "p2_px": [220.0, 30.0]},
                        {"id": "row-b", "p1_px": [20.0, 70.0], "p2_px": [220.0, 70.0]},
                    ],
                },
            ],
            "excluded_regions": [
                {"id": "outside", "bbox_px": [280, 10, 319, 120], "purpose": "exclude"},
            ],
        }

        included, excluded = fidelity._normalized_regions(regions, 320, 150)
        self.assertEqual(included[0]["geometry_occurrences"], regions["regions"][0]["geometry_occurrences"])
        before = fidelity._region_proposal_definition_sha256({
            "regions": included,
            "excluded_regions": excluded,
        })

        changed = copy.deepcopy(regions)
        changed["regions"][0]["geometry_occurrences"][0]["p2_px"][0] = 219.0
        changed_included, changed_excluded = fidelity._normalized_regions(changed, 320, 150)
        after = fidelity._region_proposal_definition_sha256({
            "regions": changed_included,
            "excluded_regions": changed_excluded,
        })
        self.assertNotEqual(before, after)

    def test_filter_preserves_distinct_semantic_occurrences_within_endpoint_tolerance(self) -> None:
        fidelity = importlib.import_module("cad_agent.fidelity")
        raw = RawGeometry(lines=[
            RawLine("row-a", (20.0, 40.0), (180.0, 40.0), 0.8, (20.0, 40.0, 180.0, 40.0)),
            RawLine("row-b", (20.0, 46.0), (180.0, 46.0), 0.9, (20.0, 46.0, 180.0, 46.0)),
        ])

        filtered = fidelity._filter_fidelity_geometry(
            raw,
            occurrence_ids={"row-a": "occ-a", "row-b": "occ-b"},
        )
        self.assertEqual({line.id for line in filtered.lines}, {"row-a", "row-b"})

    def test_filter_deduplicates_raw_fragments_within_one_semantic_occurrence(self) -> None:
        fidelity = importlib.import_module("cad_agent.fidelity")
        raw = RawGeometry(lines=[
            RawLine("fragment-a", (20.0, 40.0), (180.0, 40.0), 0.8, (20.0, 40.0, 180.0, 40.0)),
            RawLine("fragment-b", (22.0, 40.0), (180.0, 40.0), 0.9, (22.0, 40.0, 180.0, 40.0)),
        ])

        filtered = fidelity._filter_fidelity_geometry(
            raw,
            occurrence_ids={"fragment-a": "occ-a", "fragment-b": "occ-a"},
        )
        self.assertEqual([line.id for line in filtered.lines], ["fragment-b"])

    def test_filter_keeps_ambiguous_occurrence_candidates_fail_closed(self) -> None:
        fidelity = importlib.import_module("cad_agent.fidelity")
        raw = RawGeometry(lines=[
            RawLine("ambiguous-a", (20.0, 40.0), (180.0, 40.0), 0.8, (20.0, 40.0, 180.0, 40.0)),
            RawLine("ambiguous-b", (20.0, 46.0), (180.0, 46.0), 0.9, (20.0, 46.0, 180.0, 46.0)),
        ])

        filtered = fidelity._filter_fidelity_geometry(
            raw,
            occurrence_ids={"ambiguous-a": None, "ambiguous-b": None},
        )
        self.assertEqual({line.id for line in filtered.lines}, {"ambiguous-a", "ambiguous-b"})

    def test_raw_line_maps_to_one_approved_occurrence_by_source_segment(self) -> None:
        fidelity = importlib.import_module("cad_agent.fidelity")
        line = RawLine("fragment", (30.0, 40.5), (120.0, 40.5), 0.9, (30.0, 40.5, 120.0, 40.5))
        occurrences = [{"id": "occ-a", "p1_px": [20.0, 40.0], "p2_px": [180.0, 40.0]}]

        self.assertEqual(fidelity._map_raw_line_to_occurrence_id(line, occurrences), "occ-a")

    def test_raw_line_with_multiple_occurrence_matches_is_unresolved(self) -> None:
        fidelity = importlib.import_module("cad_agent.fidelity")
        line = RawLine("fragment", (30.0, 40.0), (120.0, 40.0), 0.9, (30.0, 40.0, 120.0, 40.0))
        occurrences = [
            {"id": "occ-a", "p1_px": [20.0, 40.0], "p2_px": [180.0, 40.0]},
            {"id": "occ-b", "p1_px": [20.0, 40.0], "p2_px": [180.0, 40.0]},
        ]

        self.assertIsNone(fidelity._map_raw_line_to_occurrence_id(line, occurrences))

    def test_raw_line_without_occurrence_match_is_unresolved(self) -> None:
        fidelity = importlib.import_module("cad_agent.fidelity")
        line = RawLine("unmapped", (30.0, 60.0), (120.0, 60.0), 0.9, (30.0, 60.0, 120.0, 60.0))
        occurrences = [{"id": "occ-a", "p1_px": [20.0, 40.0], "p2_px": [180.0, 40.0]}]

        self.assertIsNone(fidelity._map_raw_line_to_occurrence_id(line, occurrences))

    def test_raw_geometry_wiring_preserves_unresolved_mapping_for_counts(self) -> None:
        fidelity = importlib.import_module("cad_agent.fidelity")
        raw = RawGeometry(lines=[
            RawLine("mapped", (30.0, 40.0), (120.0, 40.0), 0.9, (30.0, 40.0, 120.0, 40.0)),
            RawLine("ambiguous", (30.0, 60.0), (120.0, 60.0), 0.9, (30.0, 60.0, 120.0, 60.0)),
            RawLine("unmapped", (30.0, 90.0), (120.0, 90.0), 0.9, (30.0, 90.0, 120.0, 90.0)),
        ])
        occurrences = [
            {"id": "occ-a", "p1_px": [20.0, 40.0], "p2_px": [180.0, 40.0]},
            {"id": "occ-b", "p1_px": [20.0, 60.0], "p2_px": [180.0, 60.0]},
            {"id": "occ-c", "p1_px": [20.0, 60.5], "p2_px": [180.0, 60.5]},
        ]

        occurrence_ids = fidelity._map_raw_geometry_to_occurrence_ids(raw, occurrences)
        self.assertEqual(occurrence_ids, {"mapped": "occ-a", "ambiguous": None, "unmapped": None})
        self.assertEqual(sum(value is not None for value in occurrence_ids.values()), 1)
        self.assertEqual(sum(value is None for value in occurrence_ids.values()), 2)

    def test_selection_wiring_forwards_occurrence_ids_to_existing_filter(self) -> None:
        fidelity = importlib.import_module("cad_agent.fidelity")
        crop = np.full((100, 180, 3), 255, dtype=np.uint8)
        raw = RawGeometry(lines=[
            RawLine("line", (10.0, 40.0), (170.0, 40.0), 0.9, (10.0, 40.0, 170.0, 40.0)),
        ])
        seen: dict[str, object] = {}

        def fake_filter(candidate: RawGeometry, *, occurrence_ids: dict[str, str | None] | None = None) -> RawGeometry:
            seen["occurrence_ids"] = occurrence_ids
            return candidate

        with patch.object(fidelity, "_filter_fidelity_geometry", side_effect=fake_filter):
            fidelity._select_fidelity_geometry(
                raw, crop, 1.0, occurrence_ids={"line": "occ-a"},
            )
        self.assertEqual(seen["occurrence_ids"], {"line": "occ-a"})

    def test_reconstruction_wiring_passes_occurrence_ids_and_records_unresolved_count(self) -> None:
        fidelity = importlib.import_module("cad_agent.fidelity")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "drawing.pdf"
            document = fitz.open()
            page = document.new_page(width=400, height=300)
            page.draw_line((20, 40), (380, 40))
            document.save(source)
            document.close()

            output = root / "private-staging"
            manifest = fidelity.new_fidelity_manifest(
                source, output, 144, "approved-test", workspace_root=Path.cwd(),
            )
            manifest_path = output / "fidelity-run-manifest.json"
            fidelity.run_fidelity_pdf(source, output, manifest_path, manifest)
            page_record = manifest["pages"][0]
            audit = json.loads((output / page_record["artifacts"]["layout_audit"]["artifact"]).read_text(encoding="utf-8"))
            width = audit["source_page"]["render_width_px"]
            height = audit["source_page"]["render_height_px"]
            x0, y0, x1, y1 = 10, 10, width - 50, height - 10
            regions = {
                "regions": [{
                    "id": "main",
                    "bbox_px": [x0, y0, x1, y1],
                    "purpose": "layout-reconstruction",
                    "geometry_occurrences": [
                        {"id": "occ-a", "p1_px": [x0 + 10.0, y0 + 30.0], "p2_px": [x1 - 10.0, y0 + 30.0]},
                        {"id": "occ-b", "p1_px": [x0 + 10.0, y0 + 50.0], "p2_px": [x1 - 10.0, y0 + 50.0]},
                        {"id": "occ-c", "p1_px": [x0 + 10.0, y0 + 50.5], "p2_px": [x1 - 10.0, y0 + 50.5]},
                    ],
                }],
                "excluded_regions": [{
                    "id": "outside",
                    "bbox_px": [x1 + 3, y0, x1 + 33, y0 + 30],
                    "purpose": "exclude",
                }],
            }
            fidelity.write_region_proposal(
                source, output, manifest_path, manifest, 1, regions, workspace_root=Path.cwd(),
            )
            approval_path = output / "region_approvals" / "page_01.json"
            fidelity.write_region_approval(
                source, output, manifest, 1, 1, ["main"], "approved-test", workspace_root=Path.cwd(),
            )
            crop_width, crop_height = x1 - x0, y1 - y0
            raw = RawGeometry(lines=[
                RawLine("mapped", (10.0, 30.0), (crop_width - 10.0, 30.0), 0.9, (10.0, 30.0, crop_width - 10.0, 30.0)),
                RawLine("ambiguous", (10.0, 50.0), (crop_width - 10.0, 50.0), 0.9, (10.0, 50.0, crop_width - 10.0, 50.0)),
                RawLine("unmapped", (10.0, 80.0), (crop_width - 10.0, 80.0), 0.9, (10.0, 80.0, crop_width - 10.0, 80.0)),
            ])
            seen: dict[str, object] = {}

            def fake_select(
                candidate: RawGeometry,
                crop: np.ndarray,
                scale: float,
                *,
                occurrence_ids: dict[str, str | None] | None = None,
            ) -> tuple[RawGeometry, dict[str, object]]:
                del crop, scale
                seen["occurrence_ids"] = occurrence_ids
                return candidate, {"selected_profile": "baseline"}

            with patch.object(fidelity, "extract_raw_geometry", return_value=raw), patch.object(
                fidelity, "_select_fidelity_geometry", side_effect=fake_select,
            ):
                results = fidelity.run_fidelity_reconstruct(
                    source, output, manifest, approval_path, workspace_root=Path.cwd(),
                )

            self.assertEqual(seen["occurrence_ids"], {"mapped": "occ-a", "ambiguous": None, "unmapped": None})
            report = json.loads((results[0] / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["quality"]["occurrence_mapping"], {"mapped": 1, "unresolved": 2})


if __name__ == "__main__":
    unittest.main()
