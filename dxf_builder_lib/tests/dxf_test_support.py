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


    records = _dimension_native_records_for_test(native, built, dimension_handle)
    return built, records, dimension.get_measurement()


def _dimension_native_records_for_test(native, built, dimension_handle):
    """Read actual saved candidate geometry for external-native test replay."""
    dimension = native.entitydb[dimension_handle]
    records = []
    for handle in built.handle_by_primitive_id.values():
        entity = native.entitydb[handle]
        if entity.dxftype() == "LINE":
            geometry = {"start": tuple(entity.dxf.start), "end": tuple(entity.dxf.end), "layout": "Model"}
        elif entity.dxftype() == "ARC":
            geometry = {
                "center": tuple(entity.dxf.center), "radius": entity.dxf.radius,
                "start_angle_deg": entity.dxf.start_angle, "end_angle_deg": entity.dxf.end_angle,
                "extrusion": tuple(entity.dxf.extrusion), "layout": "Model",
            }
        else:
            geometry = {
                "insert": tuple(entity.dxf.insert), "text": entity.dxf.text,
                "height": entity.dxf.height, "rotation_deg": entity.dxf.rotation,
            }
        records.append((handle, entity.dxftype(), entity.dxf.layer, geometry))
    records.append((dimension_handle, "DIMENSION", dimension.dxf.layer,
                    {"measurement": dimension.get_measurement(), "dimtype": dimension.dxf.dimtype,
                     "defpoint2": tuple(dimension.dxf.defpoint2),
                     "defpoint3": tuple(dimension.dxf.defpoint3), "layout": "Model"}))

    return records


def build_dimension_feature_binding_fixture(tmp_path, origins=None):
    """Build an 80 mm source-bound DIM, optionally move only its WCS origins."""
    import ezdxf

    built, _, _ = build_native_dimension_consumer_fixture(tmp_path, 80, 80, "")
    dimension_handle = next(iter(built.dimension_handle_by_cross_validation_id.values()))
    native = ezdxf.readfile(built.output_path)
    dimension = native.entitydb[dimension_handle]
    if origins is not None:
        dimension.dxf.defpoint2, dimension.dxf.defpoint3 = origins
        native.saveas(built.output_path)
    native = ezdxf.readfile(built.output_path)
    records = _dimension_native_records_for_test(native, built, dimension_handle)
    return built, records, native.entitydb[dimension_handle].get_measurement()
def build_fillet_join_fixture(tmp_path, radius, coupled, offset=0.0, *, dimensions=False):
    """Literal quarter arc plus two edges; no production helper computes wants."""
    from dxf_builder_lib.builder import NativeLinearDimensionSpec, build_dxf
    from primitive_ir_lib.models import (
        ArcGeometry, Calibration, LineGeometry, Point2D, Primitive,
        PrimitiveIRDocument, SourceDocument, Trace,
    )
    line_y = 2.1 if coupled else 2.0
    line_x = -0.1 if coupled else 0.0
    document = PrimitiveIRDocument(
        source_document=SourceDocument("synthetic.png", 0, 100, 100),
        calibration=Calibration("mm", 1.0, (0, 0), "manual_override"),
        primitives=[
            Primitive(id="fillet", type="arc", source="geometry_external_ai",
                      confidence=1.0, trace=Trace((0, 0, 100, 100)),
                      geometry=ArcGeometry(Point2D(offset + 1, 1), radius, 90, 180)),
            Primitive(id="top", type="line", source="geometry_opencv",
                      confidence=1.0, trace=Trace((0, 0, 100, 100)),
                      geometry=LineGeometry(Point2D(offset + 4, line_y), Point2D(offset + 1, line_y))),
            Primitive(id="side", type="line", source="geometry_opencv",
                      confidence=1.0, trace=Trace((0, 0, 100, 100)),
                      geometry=LineGeometry(Point2D(offset + line_x, 1), Point2D(offset + line_x, -2))),
        ],
    )
    joins = {
        "top-fillet": {"first": {"primitive_id": "fillet", "endpoint": "start"},
                       "second": {"primitive_id": "top", "endpoint": "end"}},
        "fillet-side": {"first": {"primitive_id": "fillet", "endpoint": "end"},
                        "second": {"primitive_id": "side", "endpoint": "start"}},
    }
    specs = [NativeLinearDimensionSpec("top-dim", "top", 3, "synthetic-top-length")] if dimensions else None
    return build_dxf(document, str(tmp_path / "candidate.dxf"), contour_join_by_id=joins,
                     build_dimensions=dimensions, dimension_specs=specs)


def build_fillet_dimension_fixture(tmp_path, radius, coupled, wrong_dimension):
    """One candidate carries both source contour and DIM feature obligations."""
    import ezdxf

    built = build_fillet_join_fixture(tmp_path, radius, coupled, dimensions=True)
    native = ezdxf.readfile(built.output_path)
    dimension_handle = built.dimension_handle_by_cross_validation_id["top-dim"]
    if wrong_dimension:
        dimension = native.entitydb[dimension_handle]
        dimension.dxf.defpoint2 += (0, 25, 0)
        dimension.dxf.defpoint3 += (0, 25, 0)
        native.saveas(built.output_path)
        native = ezdxf.readfile(built.output_path)
    return built, _dimension_native_records_for_test(native, built, dimension_handle)
