"""
test_builder.py — test cho `dxf_builder_lib.builder.build_dxf()`.

`test_missing_ezdxf_raises_clear_import_error` LUÔN chạy được (không cần
ezdxf — test đúng lúc CHƯA cài). Các test còn lại cần `ezdxf` thật (build
file DXF thật rồi đọc lại bằng chính ezdxf để xác nhận), tự SKIP nếu chưa
cài, cùng cách `test_constraint_solving.py`/`test_constraint_pruning.py`
đã làm với `python-solvespace`.
"""

from __future__ import annotations

import os
import tempfile

from primitive_ir_lib.models import (
    Calibration, CircleGeometry, LineGeometry, Point2D, Primitive,
    PrimitiveIRDocument, SourceDocument, TextData, Trace,
)

from dxf_builder_lib.builder import build_dxf
from semantic_ir_lib.constraint_solving import SolvedPrimitive
from semantic_ir_lib.models import PrimitiveIRRef, SemanticIRDocument, SemanticPart

try:
    import ezdxf  # noqa: F401
    _HAS_EZDXF = True
except ImportError:
    _HAS_EZDXF = False


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


def _text(id_, content, x, y) -> Primitive:
    return Primitive(
        id=id_, type="text", source="text_tesseract", confidence=0.9,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        text_data=TextData(content=content, position=Point2D(x, y), rotation_deg=0.0, height=3.5),
    )


def _doc(*prims: Primitive) -> PrimitiveIRDocument:
    return PrimitiveIRDocument(
        source_document=SourceDocument(file_name="x.png", page_index=0, image_width_px=100, image_height_px=100),
        calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
        primitives=list(prims),
    )


def test_missing_ezdxf_raises_clear_import_error():
    if _HAS_EZDXF:
        print("SKIP test_missing_ezdxf_raises_clear_import_error — ezdxf ĐANG cài "
              "(test này chỉ có ý nghĩa khi ezdxf CHƯA cài)")
        return
    l1 = _line("l1", 0, 0, 100, 0)
    doc = _doc(l1)
    try:
        build_dxf(doc, "/tmp/should_not_be_created.dxf")
        assert False, "phải raise ImportError khi chưa cài ezdxf"
    except ImportError as exc:
        assert "ezdxf" in str(exc)
        assert "pip install" in str(exc)
    print("OK   test_missing_ezdxf_raises_clear_import_error")


def test_build_line_circle_text_assigns_handles_and_writes_file():
    if not _HAS_EZDXF:
        print("SKIP test_build_line_circle_text_assigns_handles_and_writes_file — chưa cài ezdxf")
        return
    l1 = _line("l1", 0, 0, 100, 0)
    c1 = _circle("c1", 50, 50, 10)
    t1 = _text("t1", "M10", 5, 5)
    doc = _doc(l1, c1, t1)

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        result = build_dxf(doc, out_path)

        assert os.path.exists(out_path)
        assert result.entity_count == 3
        assert set(result.handle_by_primitive_id) == {"l1", "c1", "t1"}
        # handle phải được ghi ngược lại lên chính Primitive gốc
        assert l1.handle == result.handle_by_primitive_id["l1"]
        assert c1.handle == result.handle_by_primitive_id["c1"]
        assert t1.handle == result.handle_by_primitive_id["t1"]
        assert l1.handle is not None and l1.handle != ""
        # mỗi handle phải khác nhau
        assert len(set(result.handle_by_primitive_id.values())) == 3

        reopened = ezdxf.readfile(out_path)
        assert reopened.header["$INSUNITS"] == 4
    print("OK   test_build_line_circle_text_assigns_handles_and_writes_file")


def test_layer_assigned_by_part_type_from_semantic_doc():
    if not _HAS_EZDXF:
        print("SKIP test_layer_assigned_by_part_type_from_semantic_doc — chưa cài ezdxf")
        return
    h1 = _line("h1", 0, 0, 100, 0)      # sẽ gán part_type=thanh_ngang
    v1 = _line("v1", 0, 0, 0, 100)      # không có part -> UNCLASSIFIED
    doc = _doc(h1, v1)

    semantic_doc = SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(file_name="x.json", primitive_count=2),
        parts=[SemanticPart(part_type="thanh_ngang", primitive_ids=["h1"], confidence=1.0)],
        constraints=[],
    )

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        result = build_dxf(doc, out_path, semantic_doc=semantic_doc)

        assert result.layer_by_primitive_id["h1"] == "THANH_NGANG"
        assert result.layer_by_primitive_id["v1"] == "UNCLASSIFIED"

        # đọc lại file thật để xác nhận layer thật sự được ghi vào DXF
        reopened = ezdxf.readfile(out_path)
        db = reopened.entitydb
        entity_h1 = db.get(result.handle_by_primitive_id["h1"])
        assert entity_h1.dxf.layer == "THANH_NGANG"
    print("OK   test_layer_assigned_by_part_type_from_semantic_doc")


def test_solved_primitives_override_raw_coordinates():
    if not _HAS_EZDXF:
        print("SKIP test_solved_primitives_override_raw_coordinates — chưa cài ezdxf")
        return
    l1 = _line("l1", 0, 0, 100, 5)  # toạ độ đo thô, lệch chút
    doc = _doc(l1)
    solved = {
        "l1": SolvedPrimitive(
            primitive_id="l1", start=Point2D(0, 0), end=Point2D(100, 0), displacement_mm=5.0,
        )
    }

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        result = build_dxf(doc, out_path, solved_primitives=solved)

        assert result.written_geometry_by_primitive_id["l1"]["end"] == (100, 0)

        reopened = ezdxf.readfile(out_path)
        entity = reopened.entitydb.get(result.handle_by_primitive_id["l1"])
        assert entity.dxf.end.x == 100 and entity.dxf.end.y == 0
    print("OK   test_solved_primitives_override_raw_coordinates")


def test_primitive_missing_geometry_is_skipped_not_crashed():
    if not _HAS_EZDXF:
        print("SKIP test_primitive_missing_geometry_is_skipped_not_crashed — chưa cài ezdxf")
        return
    # arc type nhưng geometry None sẽ vi phạm __post_init__ của Primitive,
    # nên mô phỏng "thiếu dữ liệu" bằng text primitive có text_data hợp lệ
    # nhưng cắt geometry rỗng cho line khác bằng cách set None sau khi tạo
    l1 = _line("l1", 0, 0, 100, 0)
    l_broken = _line("l_broken", 0, 0, 1, 1)
    l_broken.geometry = None  # mô phỏng dữ liệu hỏng ở tầng trên
    doc = _doc(l1, l_broken)

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.dxf")
        result = build_dxf(doc, out_path)

        assert result.entity_count == 1
        assert result.skipped_primitive_ids == ["l_broken"]
        assert "l_broken" not in result.handle_by_primitive_id
    print("OK   test_primitive_missing_geometry_is_skipped_not_crashed")


_TESTS = [
    test_missing_ezdxf_raises_clear_import_error,
    test_build_line_circle_text_assigns_handles_and_writes_file,
    test_layer_assigned_by_part_type_from_semantic_doc,
    test_solved_primitives_override_raw_coordinates,
    test_primitive_missing_geometry_is_skipped_not_crashed,
]


def run_all():
    passed = 0
    for t in _TESTS:
        t()
        passed += 1
    print(f"\n{passed}/{len(_TESTS)} test PASS")


if __name__ == "__main__":
    run_all()
