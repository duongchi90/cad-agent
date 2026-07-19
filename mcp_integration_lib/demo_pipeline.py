"""Run a self-contained Phase 4 demo using the deterministic FakeMCPClient."""
from __future__ import annotations

import sys

from dxf_builder_lib.builder import BuildResult
from .mcp_client import FakeMCPClient
from .repair2 import repair_dxf_live
from .reviewer2 import review_dxf_live


def run_demo() -> dict:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build = BuildResult(output_path="phase4_demo.dxf", entity_count=1)
    build.handle_by_primitive_id = {"line-demo": "10"}
    build.layer_by_primitive_id = {"line-demo": "KET_CAU"}
    build.written_geometry_by_primitive_id = {"line-demo": {"type": "line", "start": (0.0, 0.0), "end": (100.0, 0.0)}}
    client = FakeMCPClient(fail_entity_get=True)
    client.preload_entity("10", "LINE", "KET_CAU", dict(build.written_geometry_by_primitive_id["line-demo"]))
    initial = review_dxf_live(build, client)
    client._entities["10"].layer = "LAYER_SAI"
    damaged = review_dxf_live(build, client, open_drawing=False)
    repair = repair_dxf_live(build, damaged.mismatches, client)
    final = review_dxf_live(build, client, open_drawing=False)
    print(f"[phase4] initial={initial.passed}; damaged={damaged.passed}; repaired={final.passed}")
    return {"initial_passed": initial.passed, "repaired_count": repair.repaired_count, "reviewer2_passed": final.passed}


if __name__ == "__main__":
    run_demo()
