"""test_pattern_compound.py — test cho pattern_compound.py (compound parts).
Test thuần offline, không cần OpenCV/ảnh/solvespace/ezdxf."""

from __future__ import annotations

from primitive_ir_lib.models import (
    CircleGeometry, LineGeometry, Point2D, Primitive, Trace,
)

from semantic_ir_lib.constraint_detection import detect_constraints
from semantic_ir_lib.pattern_compound import build_compound_parts


def _line(id_, x0, y0, x1, y1) -> Primitive:
    return Primitive(
        id=id_, type="line", source="geometry_opencv", confidence=0.9,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=LineGeometry(start=Point2D(x0, y0), end=Point2D(x1, y1)),
    )


def _circle(id_, cx, cy, r) -> Primitive:
    return Primitive(
        id=id_, type="circle", source="geometry_opencv", confidence=0.9,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=CircleGeometry(center=Point2D(cx, cy), radius=r),
    )


def _detect_and_compound(prims, **kwargs):
    lines = [p for p in prims if p.type == "line"]
    cs = detect_constraints(lines)
    return build_compound_parts(prims, cs, **kwargs)


# ============================================================ khung_chu_nhat ==
def test_khung_chu_nhat_perfect():
    r1 = _line("r1", 0, 0, 200, 0)
    r2 = _line("r2", 200, 0, 200, 100)
    r3 = _line("r3", 200, 100, 0, 100)
    r4 = _line("r4", 0, 100, 0, 0)
    parts = _detect_and_compound([r1, r2, r3, r4])
    types = [p.part_type for p in parts]
    assert "khung_chu_nhat" in types, f"phải có khung_chu_nhat, nhận {types}"
    khung = [p for p in parts if p.part_type == "khung_chu_nhat"][0]
    assert set(khung.primitive_ids) == {"r1", "r2", "r3", "r4"}
    assert khung.confidence >= 0.8
    print("OK   test_khung_chu_nhat_perfect")


def test_khung_chu_nhat_dedup_no_gia_do():
    """Khung chữ nhật KHÔNG sinh thêm gia_do trùng primitive."""
    r1 = _line("r1", 0, 0, 200, 0)
    r2 = _line("r2", 200, 0, 200, 100)
    r3 = _line("r3", 200, 100, 0, 100)
    r4 = _line("r4", 0, 100, 0, 0)
    parts = _detect_and_compound([r1, r2, r3, r4])
    pids_used = set()
    for p in parts:
        for pid in p.primitive_ids:
            assert pid not in pids_used, f"primitive {pid} bị gán vào >1 compound"
            pids_used.add(pid)
    print("OK   test_khung_chu_nhat_dedup_no_gia_do")


def test_khung_chu_nhat_negative_incomplete():
    """3 line không thành khung (thiếu 1 cạnh) -> KHÔNG tạo khung."""
    r1 = _line("r1", 0, 0, 200, 0)
    r2 = _line("r2", 200, 0, 200, 100)
    r3 = _line("r3", 0, 100, 0, 0)
    parts = _detect_and_compound([r1, r2, r3])
    types = [p.part_type for p in parts]
    assert "khung_chu_nhat" not in types, f"3 line KHÔNG nên tạo khung, nhận {types}"
    print("OK   test_khung_chu_nhat_negative_incomplete")


# ================================================================= gia_do ====
def test_gia_do_perpendicular_coincident():
    l1 = _line("l1", 0, 0, 100, 0)
    l2 = _line("l2", 100, 0, 100, 100)
    parts = _detect_and_compound([l1, l2])
    types = [p.part_type for p in parts]
    assert "gia_do" in types, f"2 line vuông góc + coincident phải là gia_do, nhận {types}"
    gd = [p for p in parts if p.part_type == "gia_do"][0]
    assert set(gd.primitive_ids) == {"l1", "l2"}
    print("OK   test_gia_do_perpendicular_coincident")


def test_gia_do_negative_parallel():
    """2 line song song KHÔNG tạo gia_do (thiếu perpendicular)."""
    l1 = _line("l1", 0, 0, 100, 0)
    l2 = _line("l2", 0, 50, 100, 50)
    parts = _detect_and_compound([l1, l2])
    types = [p.part_type for p in parts]
    assert "gia_do" not in types, f"song song KHÔNG phải gia_do, nhận {types}"
    print("OK   test_gia_do_negative_parallel")


# ================================================================== ban_le ===
def test_ban_le_parallel_two_circles():
    h1 = _line("h1", 0, 0, 100, 0)
    h2 = _line("h2", 0, 5, 100, 5)
    c1 = _circle("c1", 0, 0, 4)
    c2 = _circle("c2", 100, 5, 4)
    parts = _detect_and_compound([h1, h2, c1, c2])
    types = [p.part_type for p in parts]
    assert "ban_le" in types, f"2 parallel + 2 circles phải là ban_le, nhận {types}"
    bl = [p for p in parts if p.part_type == "ban_le"][0]
    assert set(bl.primitive_ids) == {"h1", "h2", "c1", "c2"}
    print("OK   test_ban_le_parallel_two_circles")


def test_ban_le_selects_circles_across_both_lines():
    """Bản lề 4 lỗ vẫn phải chọn circle phủ cả hai thanh song song."""
    h1 = _line("h1", 0, 0, 100, 0)
    h2 = _line("h2", 0, 5, 100, 5)
    c1 = _circle("c1", 0, 0, 4)
    c2 = _circle("c2", 100, 0, 4)
    c3 = _circle("c3", 0, 5, 4)
    c4 = _circle("c4", 100, 5, 4)
    parts = _detect_and_compound([h1, h2, c1, c2, c3, c4])
    hinge = [p for p in parts if p.part_type == "ban_le"]
    assert len(hinge) == 1, f"4 lỗ quanh hai thanh phải là ban_le, nhận {parts}"
    assert {"h1", "h2"}.issubset(hinge[0].primitive_ids)
    print("OK   test_ban_le_selects_circles_across_both_lines")


def test_ban_le_negative_only_one_circle():
    h1 = _line("h1", 0, 0, 100, 0)
    h2 = _line("h2", 0, 5, 100, 5)
    c1 = _circle("c1", 0, 0, 4)
    parts = _detect_and_compound([h1, h2, c1])
    types = [p.part_type for p in parts]
    assert "ban_le" not in types, f"chỉ 1 circle KHÔNG đủ ban_le, nhận {types}"
    print("OK   test_ban_le_negative_only_one_circle")


def test_ban_le_negative_circles_too_far():
    h1 = _line("h1", 0, 0, 100, 0)
    h2 = _line("h2", 0, 5, 100, 5)
    c1 = _circle("c1", 500, 500, 4)
    c2 = _circle("c2", 600, 500, 4)
    parts = _detect_and_compound([h1, h2, c1, c2])
    types = [p.part_type for p in parts]
    assert "ban_le" not in types, f"circle xa KHÔNG phải ban_le, nhận {types}"
    print("OK   test_ban_le_negative_circles_too_far")


# ================================================================ diem_noi ===
def test_diem_noi_three_lines_at_origin():
    n1 = _line("n1", 0, 0, 100, 0)
    n2 = _line("n2", 0, 0, 0, 100)
    n3 = _line("n3", 0, 0, -70, -70)
    parts = _detect_and_compound([n1, n2, n3])
    types = [p.part_type for p in parts]
    assert "diem_noi" in types, f"3 line gặp nhau tại origin phải là diem_noi, nhận {types}"
    dn = [p for p in parts if p.part_type == "diem_noi"][0]
    assert set(dn.primitive_ids) == {"n1", "n2", "n3"}
    print("OK   test_diem_noi_three_lines_at_origin")


def test_diem_noi_negative_two_lines_only():
    """Chỉ 2 line gặp nhau -> KHÔNG tạo diem_noi (để gia_do xử lý)."""
    l1 = _line("l1", 0, 0, 100, 0)
    l2 = _line("l2", 0, 0, 0, 100)
    parts = _detect_and_compound([l1, l2])
    types = [p.part_type for p in parts]
    assert "diem_noi" not in types, f"2 line KHÔNG đủ diem_noi (cần >=3), nhận {types}"
    print("OK   test_diem_noi_negative_two_lines_only")


# ============================================================ empty/negative ==
def test_unrelated_lines_no_compound():
    u1 = _line("u1", 0, 0, 100, 0)
    u2 = _line("u2", 500, 500, 600, 600)
    parts = _detect_and_compound([u1, u2])
    assert parts == [], f"2 line xa, không liên quan -> rỗng, nhận {[p.part_type for p in parts]}"
    print("OK   test_unrelated_lines_no_compound")


def test_single_line_no_compound():
    l1 = _line("l1", 0, 0, 100, 0)
    parts = _detect_and_compound([l1])
    assert parts == [], "1 line không thể tạo compound"
    print("OK   test_single_line_no_compound")


# =========================================================== integration ====
def test_integration_via_assemble():
    """Test toàn bộ assemble pipeline: single-parts + constraints + compound."""
    from semantic_ir_lib.assemble import build_semantic_document
    from primitive_ir_lib.models import PrimitiveIRDocument, SourceDocument, Calibration

    # 1. Khung chữ nhật: 4 line kín
    r1 = _line("r1", 0, 0, 200, 0)
    r2 = _line("r2", 200, 0, 200, 100)
    r3 = _line("r3", 200, 100, 0, 100)
    r4 = _line("r4", 0, 100, 0, 0)

    # 2. Gia đỡ L: 2 line vuông góc (riêng, không dính khung)
    g1 = _line("g1", 300, 200, 400, 200)
    g2 = _line("g2", 400, 200, 400, 300)

    # 3. Bản lề: 2 line parallel + 2 circle nhỏ gần endpoint
    h1 = _line("h1", 0, 150, 100, 150)
    h2 = _line("h2", 0, 155, 100, 155)
    c1 = _circle("c1", 0, 150, 3)
    c2 = _circle("c2", 100, 155, 3)

    # 4. Điểm nối: 3 line gặp nhau tại (0, -50)
    d1 = _line("d1", -50, -50, 0, -50)
    d2 = _line("d2", 0, -50, 0, 50)
    d3 = _line("d3", 0, -50, 50, -50)

    all_prims = [r1, r2, r3, r4, g1, g2, h1, h2, c1, c2, d1, d2, d3]
    prim_doc = PrimitiveIRDocument(
        source_document=SourceDocument(file_name="test.png", page_index=0,
            image_width_px=1000, image_height_px=800),
        calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0,
            origin_px=(0, 0), method="manual_override"),
        primitives=all_prims,
    )
    doc = build_semantic_document(prim_doc, "test.png")
    types = [p.part_type for p in doc.parts]

    assert "khung_chu_nhat" in types, f"integration: phải có khung, nhận {types}"
    assert any(
        p.part_type == "gia_do" and set(p.primitive_ids) == {"g1", "g2"}
        for p in doc.parts
    ), "integration: cặp g1/g2 độc lập phải được nhận diện là gia_do"
    assert "gia_do" in types, f"integration: phải có gia_do, nhận {types}"
    assert "ban_le" in types, f"integration: phải có ban_le, nhận {types}"
    assert "diem_noi" in types, f"integration: phải có diem_noi, nhận {types}"
    # single-parts vẫn phải có (bên cạnh compound)
    assert "thanh_ngang" in types, f"integration: vẫn phải có single-parts, nhận {types}"
    print(f"OK   test_integration_via_assemble ({len(doc.parts)} parts, {len(doc.constraints)} constraints)")


_TESTS = [
    test_khung_chu_nhat_perfect,
    test_khung_chu_nhat_dedup_no_gia_do,
    test_khung_chu_nhat_negative_incomplete,
    test_gia_do_perpendicular_coincident,
    test_gia_do_negative_parallel,
    test_ban_le_parallel_two_circles,
    test_ban_le_selects_circles_across_both_lines,
    test_ban_le_negative_only_one_circle,
    test_ban_le_negative_circles_too_far,
    test_diem_noi_three_lines_at_origin,
    test_diem_noi_negative_two_lines_only,
    test_unrelated_lines_no_compound,
    test_single_line_no_compound,
    test_integration_via_assemble,
]


def run_all():
    passed = 0
    for t in _TESTS:
        t()
        passed += 1
    print(f"\n{passed}/{len(_TESTS)} test PASS")


if __name__ == "__main__":
    run_all()
