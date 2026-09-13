from __future__ import annotations

import copy
import importlib
import unittest

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


if __name__ == "__main__":
    unittest.main()
