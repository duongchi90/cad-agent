from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch

import pytest

from primitive_ir_lib.models import (
    Calibration,
    LineGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    Trace,
)
from semantic_ir_lib.assemble import build_semantic_document


def _document(unit: object) -> PrimitiveIRDocument:
    return PrimitiveIRDocument(
        source_document=SourceDocument(
            file_name="synthetic.json",
            page_index=0,
            image_width_px=100,
            image_height_px=100,
        ),
        calibration=Calibration(
            unit=unit,  # type: ignore[arg-type]
            pixel_to_unit_scale=1.0,
            origin_px=(0, 0),
            method="manual_override",
        ),
        primitives=[
            Primitive(
                id="line-20mm",
                type="line",
                source="geometry_opencv",
                confidence=1.0,
                trace=Trace(bbox_px=(0, 0, 20, 0)),
                geometry=LineGeometry(
                    start=Point2D(0.0, 0.0), end=Point2D(20.0, 0.0)
                ),
            )
        ],
    )


@pytest.mark.parametrize("unit", ["cm", "m", "MM", "inch", None, 3])
def test_non_mm_calibration_is_refused_before_semantic_helpers(unit: object) -> None:
    primitive_doc = _document(unit)
    before = deepcopy(primitive_doc.to_dict())

    with (
        patch("semantic_ir_lib.assemble.build_parts_from_primitives") as parts,
        patch("semantic_ir_lib.assemble.detect_constraints") as constraints,
        patch("semantic_ir_lib.assemble.detect_circle_constraints") as circle_constraints,
        patch("semantic_ir_lib.assemble.build_compound_parts") as compounds,
        patch("semantic_ir_lib.assemble.prune_constraints") as pruning,
    ):
        with pytest.raises(ValueError, match="Semantic IR.*mm"):
            build_semantic_document(primitive_doc, "synthetic.json")

    parts.assert_not_called()
    constraints.assert_not_called()
    circle_constraints.assert_not_called()
    compounds.assert_not_called()
    pruning.assert_not_called()
    assert primitive_doc.to_dict() == before


def test_mm_calibration_preserves_existing_semantic_length() -> None:
    primitive_doc = _document("mm")

    semantic_doc = build_semantic_document(
        primitive_doc, "synthetic.json", enable_compound_parts=False
    )

    assert len(semantic_doc.parts) == 1
    assert semantic_doc.parts[0].geometry_summary.length_mm == 20.0
