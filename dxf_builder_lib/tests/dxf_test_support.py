from __future__ import annotations

from pathlib import Path
from typing import Literal


def add_untracked_entity_for_test(
    candidate_path: Path,
    entity_type: Literal["LINE", "LWPOLYLINE", "INSERT"],
) -> str:
    """Add one disposable untracked entity through the DXF owner."""

    import ezdxf

    path = Path(candidate_path)
    document = ezdxf.readfile(path)
    modelspace = document.modelspace()
    if entity_type == "LINE":
        entity = modelspace.add_line(
            (200.0, 200.0),
            (210.0, 210.0),
            dxfattribs={"layer": "UNCLASSIFIED"},
        )
    elif entity_type == "LWPOLYLINE":
        entity = modelspace.add_lwpolyline(
            [(220.0, 220.0), (230.0, 220.0), (230.0, 230.0)],
            dxfattribs={"layer": "UNCLASSIFIED"},
        )
    else:
        block_name = "UNTRACKED_TEST_COMPONENT"
        block = document.blocks.new(name=block_name)
        block.add_line((0.0, 0.0), (1.0, 0.0))
        block.add_attdef(tag="PART_ID", insert=(0.0, 0.0), height=0.1)
        entity = modelspace.add_blockref(
            block_name,
            (240.0, 240.0),
            dxfattribs={
                "layer": "UNCLASSIFIED",
                "xscale": 1.0,
                "yscale": 1.0,
                "zscale": 1.0,
                "rotation": 0.0,
            },
        )
        entity.add_auto_attribs({"PART_ID": "forged-component"})
    handle = str(entity.dxf.handle)
    document.saveas(path)
    return handle
