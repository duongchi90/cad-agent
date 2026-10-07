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


def build_native_dimension_consumer_fixture(
    tmp_path: Path, length: float, approved: float | None, display: str,
):
    """Build legal synthetic CAD and replay records for native-consumer tests."""
    import ezdxf
    from dxf_builder_lib.builder import NativeLinearDimensionSpec, build_dxf
    from primitive_ir_lib.models import (
        Calibration,
        CrossValidation,
        LineGeometry,
        Point2D,
        Primitive,
        PrimitiveIRDocument,
        SourceDocument,
        TextData,
        Trace,
    )
    from primitive_ir_lib.validator import validate_document

    document = PrimitiveIRDocument(
        source_document=SourceDocument(
            file_name="synthetic.png", page_index=0,
            image_width_px=100, image_height_px=100,
        ),
        calibration=Calibration(
            unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0),
            method="manual_override",
        ),
        primitives=[Primitive(
            id="line", type="line", source="geometry_opencv", confidence=1.0,
            trace=Trace(bbox_px=(0, 0, 100, 100)),
            geometry=LineGeometry(start=Point2D(0, 0), end=Point2D(length, 0)),
        )],
    )
    specs = None
    if approved is None:
        # The existing legacy path creates a DIM without exact source authority.
        document.primitives.append(Primitive(
            id="reference", type="text", source="text_tesseract", confidence=1.0,
            trace=Trace(bbox_px=(0, 0, 100, 100)),
            text_data=TextData(
                content="80", position=Point2D(0, 10), rotation_deg=0, height=3.5,
            ),
        ))
        document.cross_validations = [CrossValidation(
            text_primitive_id="reference", geometry_primitive_id="line",
            status="confirmed", text_value=80.0,
            geometry_measured_length=80.0, delta_percent=0.0,
        )]
    else:
        specs = [NativeLinearDimensionSpec(
            id="exact", geometry_primitive_id="line",
            approved_value_mm=approved, source_ref="synthetic-source-dimension",
        )]
    assert validate_document(document.to_dict()) == []
    candidate = tmp_path / "candidate.dxf"
    built = build_dxf(
        document, str(candidate), build_dimensions=True, dimension_specs=specs,
    )
    native = ezdxf.readfile(candidate)
    dimension_handle = next(iter(built.dimension_handle_by_cross_validation_id.values()))
    dimension = native.entitydb[dimension_handle]
    if display:
        dimension.dxf.text = display
        native.saveas(candidate)
    assert dimension.get_measurement() == length


    records = []
    for handle in built.handle_by_primitive_id.values():
        entity = native.entitydb[handle]
        if entity.dxftype() == "LINE":
            geometry = {"start": tuple(entity.dxf.start), "end": tuple(entity.dxf.end)}
        else:
            geometry = {
                "insert": tuple(entity.dxf.insert), "text": entity.dxf.text,
                "height": entity.dxf.height, "rotation_deg": entity.dxf.rotation,
            }
        records.append((handle, entity.dxftype(), entity.dxf.layer, geometry))
    records.append((dimension_handle, "DIMENSION", dimension.dxf.layer,
                    {"measurement": dimension.get_measurement()}))

    return built, records, dimension.get_measurement()
