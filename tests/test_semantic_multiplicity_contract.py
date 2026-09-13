from __future__ import annotations

import copy
import importlib
import unittest


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


if __name__ == "__main__":
    unittest.main()
