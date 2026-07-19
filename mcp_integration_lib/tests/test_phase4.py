import unittest

from dxf_builder_lib.builder import BuildResult
from mcp_integration_lib.mcp_client import FakeMCPClient
from mcp_integration_lib.repair2 import repair_dxf_live
from mcp_integration_lib.reviewer2 import review_dxf_live


def _pair(kind="line", entity_get=False):
    build = BuildResult(output_path="fake.dxf", entity_count=1)
    geometry = ({"type": "line", "start": (0.0, 0.0), "end": (1.0, 1.0)}
                if kind == "line" else {"type": "arc", "center": (0.0, 0.0), "radius": 2.0, "start_angle_deg": 0.0, "end_angle_deg": 90.0})
    build.handle_by_primitive_id = {"p": "10"}
    build.layer_by_primitive_id = {"p": "L"}
    build.written_geometry_by_primitive_id = {"p": geometry}
    client = FakeMCPClient(fail_entity_get=not entity_get)
    client.preload_entity("10", kind.upper(), "L", dict(geometry))
    return build, client


class Phase4Tests(unittest.TestCase):
    def test_structural_review_passes_when_entity_get_times_out(self):
        build, client = _pair()
        result = review_dxf_live(build, client)
        self.assertTrue(result.passed)
        self.assertTrue(result.geometry_degraded)

    def test_geometry_mismatch_fails(self):
        build, client = _pair(entity_get=True)
        client.tamper("10", end=(2.0, 2.0))
        self.assertFalse(review_dxf_live(build, client).passed)

    def test_repair_restores_review_and_updates_handle(self):
        build, client = _pair()
        client._entities["10"].layer = "BAD"
        repair = repair_dxf_live(build, review_dxf_live(build, client).mismatches, client)
        self.assertEqual(repair.repaired_count, 1)
        self.assertNotEqual(build.handle_by_primitive_id["p"], "10")
        self.assertTrue(review_dxf_live(build, client, open_drawing=False).passed)

    def test_arc_repair(self):
        build, client = _pair("arc")
        client._entities["10"].layer = "BAD"
        self.assertEqual(repair_dxf_live(build, review_dxf_live(build, client).mismatches, client).repaired_count, 1)
