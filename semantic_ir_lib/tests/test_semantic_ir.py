"""test_semantic_ir.py — test thuần offline, không cần OpenCV/ảnh thật."""

from __future__ import annotations

from primitive_ir_lib.models import (
    CircleGeometry, LineGeometry, Point2D, Primitive, Trace,
)

from semantic_ir_lib.constraint_detection import detect_constraints
from semantic_ir_lib.pattern_recognition import build_parts_from_primitives
from semantic_ir_lib.validator import validate_document


def _line(id_, x0, y0, x1, y1, ptype="line") -> Primitive:
    return Primitive(
        id=id_, type=ptype, source="geometry_opencv", confidence=0.9,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=LineGeometry(start=Point2D(x0, y0), end=Point2D(x1, y1)),
    )


def _circle(id_, cx, cy, r) -> Primitive:
    return Primitive(
        id=id_, type="circle", source="geometry_opencv", confidence=0.9,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=CircleGeometry(center=Point2D(cx, cy), radius=r),
    )


# ------------------------------------------------------- pattern_recognition --
def test_horizontal_line_classified_thanh_ngang():
    prim = _line("l1", 0, 0, 100, 0)
    parts = build_parts_from_primitives([prim])
    assert len(parts) == 1
    assert parts[0].part_type == "thanh_ngang"
    assert parts[0].confidence >= 0.9
    assert parts[0].geometry_summary.length_mm == 100.0
    print("OK   test_horizontal_line_classified_thanh_ngang")


def test_vertical_line_classified_thanh_doc():
    prim = _line("l1", 0, 0, 0, 250)
    parts = build_parts_from_primitives([prim])
    assert parts[0].part_type == "thanh_doc"
    print("OK   test_vertical_line_classified_thanh_doc")


def test_45deg_line_classified_thanh_xien():
    prim = _line("l1", 0, 0, 100, 100)
    parts = build_parts_from_primitives([prim], angle_tolerance_deg=10.0)
    assert parts[0].part_type == "thanh_xien"
    assert parts[0].confidence == 1.0, "45 deg là điểm xa nhất 2 biên -> confidence tối đa"
    print("OK   test_45deg_line_classified_thanh_xien")


def test_zero_length_line_produces_no_part():
    prim = _line("l1", 5, 5, 5, 5)
    parts = build_parts_from_primitives([prim])
    assert parts == []
    print("OK   test_zero_length_line_produces_no_part")


def test_small_circle_classified_lo_bat_vit():
    prim = _circle("c1", 0, 0, 5.0)
    parts = build_parts_from_primitives([prim], bolt_hole_max_radius_mm=15.0)
    assert parts[0].part_type == "lo_bat_vit"
    print("OK   test_small_circle_classified_lo_bat_vit")


def test_large_circle_classified_duong_vien_tron():
    prim = _circle("c1", 0, 0, 50.0)
    parts = build_parts_from_primitives([prim], bolt_hole_max_radius_mm=15.0)
    assert parts[0].part_type == "duong_vien_tron"
    print("OK   test_large_circle_classified_duong_vien_tron")


def test_text_and_arc_primitives_ignored():
    from primitive_ir_lib.models import TextData
    text_prim = Primitive(
        id="t1", type="text", source="text_tesseract", confidence=0.9,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        text_data=TextData(content="1700", position=Point2D(0, 0), rotation_deg=0, height=10),
    )
    parts = build_parts_from_primitives([text_prim])
    assert parts == []
    print("OK   test_text_and_arc_primitives_ignored")


# ------------------------------------------------------- constraint_detection --
def test_parallel_lines_detected():
    l1 = _line("l1", 0, 0, 100, 0)
    l2 = _line("l2", 0, 50, 100, 50)
    cs = detect_constraints([l1, l2])
    types = {c.type for c in cs}
    assert "parallel" in types
    assert "equal_length" in types  # cùng độ dài 100
    assert "perpendicular" not in types
    assert "coincident_endpoint" not in types
    assert "collinear" not in types  # song song nhưng cách nhau 50mm
    print("OK   test_parallel_lines_detected")


def test_perpendicular_lines_detected():
    l1 = _line("l1", 0, 0, 100, 0)
    l2 = _line("l2", 50, -50, 50, 50)
    cs = detect_constraints([l1, l2])
    types = {c.type for c in cs}
    assert "perpendicular" in types
    assert "parallel" not in types
    print("OK   test_perpendicular_lines_detected")


def test_collinear_lines_detected():
    l1 = _line("l1", 0, 0, 100, 0)
    l2 = _line("l2", 150, 0, 250, 0)  # cùng đường thẳng y=0, không chạm nhau
    cs = detect_constraints([l1, l2])
    types = {c.type for c in cs}
    assert "collinear" in types
    assert "parallel" in types
    assert "coincident_endpoint" not in types
    print("OK   test_collinear_lines_detected")


def test_coincident_endpoint_detected():
    l1 = _line("l1", 0, 0, 100, 0)
    l2 = _line("l2", 100, 0, 100, 100)  # chạm đúng tại (100,0)
    cs = detect_constraints([l1, l2])
    types = {c.type for c in cs}
    assert "coincident_endpoint" in types
    assert "perpendicular" in types
    print("OK   test_coincident_endpoint_detected")


def test_unrelated_lines_produce_no_constraint():
    l1 = _line("l1", 0, 0, 100, 0)
    l2 = _line("l2", 500, 500, 530, 537)  # góc lệch, xa, độ dài khác hẳn
    cs = detect_constraints([l1, l2])
    assert cs == []
    print("OK   test_unrelated_lines_produce_no_constraint")


def test_detect_constraints_rejects_non_line_primitive():
    l1 = _line("l1", 0, 0, 100, 0)
    circ = _circle("c1", 0, 0, 5.0)
    try:
        detect_constraints([l1, circ])
        raise AssertionError("Phải raise ValueError khi có primitive không phải line")
    except ValueError:
        pass
    print("OK   test_detect_constraints_rejects_non_line_primitive")


# ------------------------------------------------------------------ validator --
def test_validator_passes_on_well_formed_document():
    l1 = _line("l1", 0, 0, 100, 0)
    l2 = _line("l2", 0, 50, 100, 50)
    parts = build_parts_from_primitives([l1, l2])
    constraints = detect_constraints([l1, l2])
    from semantic_ir_lib.models import PrimitiveIRRef, SemanticIRDocument
    doc = SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(file_name="x.json", primitive_count=2),
        parts=parts, constraints=constraints,
    )
    errors = validate_document(doc.to_dict(), known_primitive_ids={"l1", "l2"})
    assert errors == [], f"Không kỳ vọng lỗi, nhận: {errors}"
    print("OK   test_validator_passes_on_well_formed_document")


def test_validator_catches_dangling_primitive_id():
    l1 = _line("l1", 0, 0, 100, 0)
    parts = build_parts_from_primitives([l1])
    from semantic_ir_lib.models import PrimitiveIRRef, SemanticIRDocument
    doc = SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(file_name="x.json", primitive_count=1),
        parts=parts, constraints=[],
    )
    # known_primitive_ids KHÔNG chứa "l1" -> phải bắt được tham chiếu treo
    errors = validate_document(doc.to_dict(), known_primitive_ids={"other-id"})
    assert any("treo" in e for e in errors)
    print("OK   test_validator_catches_dangling_primitive_id")


_TESTS = [
    test_horizontal_line_classified_thanh_ngang,
    test_vertical_line_classified_thanh_doc,
    test_45deg_line_classified_thanh_xien,
    test_zero_length_line_produces_no_part,
    test_small_circle_classified_lo_bat_vit,
    test_large_circle_classified_duong_vien_tron,
    test_text_and_arc_primitives_ignored,
    test_parallel_lines_detected,
    test_perpendicular_lines_detected,
    test_collinear_lines_detected,
    test_coincident_endpoint_detected,
    test_unrelated_lines_produce_no_constraint,
    test_detect_constraints_rejects_non_line_primitive,
    test_validator_passes_on_well_formed_document,
    test_validator_catches_dangling_primitive_id,
]


def run_all():
    passed = 0
    for t in _TESTS:
        t()
        passed += 1
    print(f"\n{passed}/{len(_TESTS)} test PASS")


if __name__ == "__main__":
    run_all()
