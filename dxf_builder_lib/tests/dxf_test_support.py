from __future__ import annotations

from pathlib import Path
from typing import Literal


def add_untracked_entity_for_test(
    candidate_path: Path,
    entity_type: Literal["LINE", "LWPOLYLINE"],
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
    else:
        entity = modelspace.add_lwpolyline(
            [(220.0, 220.0), (230.0, 220.0), (230.0, 230.0)],
            dxfattribs={"layer": "UNCLASSIFIED"},
        )
    handle = str(entity.dxf.handle)
    document.saveas(path)
    return handle
