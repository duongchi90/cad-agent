"""
test_constraint_solving.py — test THẬT với python-solvespace (không mock,
khác với vision_client vốn phải mock vì cần API key mạng ngoài — solvespace
là thư viện tính toán cục bộ, cài được offline sau khi build 1 lần, nên
test được thật 100%).
"""

from __future__ import annotations

import math

import pytest

from primitive_ir_lib.models import (
    Calibration, LineGeometry, Point2D, Primitive, PrimitiveIRDocument,
    SourceDocument, Trace,
)

from semantic_ir_lib.constraint_solving import solve_constraints
from semantic_ir_lib.models import Constraint

try:
    import python_solvespace  # noqa: F401
    _HAS_SOLVESPACE = True
except ImportError:
    _HAS_SOLVESPACE = False

pytestmark = pytest.mark.skipif(
    not _HAS_SOLVESPACE,
    reason="python-solvespace is an optional dependency",
)


def _line(id_, x0, y0, x1, y1) -> Primitive:
    return Primitive(
        id=id_, type="line", source="geometry_opencv", confidence=0.9,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=LineGeometry(start=Point2D(x0, y0), end=Point2D(x1, y1)),
    )


def _doc(*lines: Primitive) -> PrimitiveIRDocument:
    return PrimitiveIRDocument(
        source_document=SourceDocument(file_name="x.png", page_index=0, image_width_px=100, image_height_px=100),
        calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
        primitives=list(lines),
    )


def _c(type_, a, b) -> Constraint:
    return Constraint(type=type_, primitive_ids=[a, b], confidence=1.0, tolerance={})


def _angle_deg(start: Point2D, end: Point2D) -> float:
    return math.degrees(math.atan2(end.y - start.y, end.x - start.x)) % 180.0


def test_parallel_constraint_makes_lines_exactly_parallel():
    l1 = _line("l1", 0, 0, 100, 0)
    l2 = _line("l2", 0, 50, 100, 55)  # lệch 1 chút so với ngang
    doc = _doc(l1, l2)
    result = solve_constraints(doc, [_c("parallel", "l1", "l2")])

    assert result.status == "okay", result.status
    sp1, sp2 = result.solved_primitives["l1"], result.solved_primitives["l2"]
    angle_diff = abs(_angle_deg(sp1.start, sp1.end) - _angle_deg(sp2.start, sp2.end))
    assert angle_diff < 0.01, f"Sau solve phải song song gần tuyệt đối, lệch {angle_diff}"
    print("OK   test_parallel_constraint_makes_lines_exactly_parallel")


def test_perpendicular_constraint_enforced():
    l1 = _line("l1", 0, 0, 100, 0)
    l2 = _line("l2", 50, -50, 52, 50)  # gần vuông góc, lệch chút
    doc = _doc(l1, l2)
    result = solve_constraints(doc, [_c("perpendicular", "l1", "l2")])

    assert result.status == "okay"
    sp1, sp2 = result.solved_primitives["l1"], result.solved_primitives["l2"]
    a1, a2 = _angle_deg(sp1.start, sp1.end), _angle_deg(sp2.start, sp2.end)
    diff = abs(abs(a1 - a2) - 90.0)
    assert diff < 0.01, f"Sau solve phải vuông góc gần tuyệt đối, lệch {diff}"
    print("OK   test_perpendicular_constraint_enforced")


def test_equal_length_constraint_enforced():
    l1 = _line("l1", 0, 0, 100, 0)
    l2 = _line("l2", 0, 50, 97, 50)  # ngắn hơn 1 chút
    doc = _doc(l1, l2)
    result = solve_constraints(doc, [_c("equal_length", "l1", "l2")])

    assert result.status == "okay"
    sp1, sp2 = result.solved_primitives["l1"], result.solved_primitives["l2"]
    len1 = math.hypot(sp1.end.x - sp1.start.x, sp1.end.y - sp1.start.y)
    len2 = math.hypot(sp2.end.x - sp2.start.x, sp2.end.y - sp2.start.y)
    assert abs(len1 - len2) < 0.01, f"Sau solve phải bằng độ dài gần tuyệt đối, lệch {abs(len1-len2)}"
    print("OK   test_equal_length_constraint_enforced")


def test_coincident_endpoint_constraint_enforced():
    l1 = _line("l1", 0, 0, 100, 0)
    l2 = _line("l2", 101, 1, 101, 100)  # đầu (101,1) lẽ ra phải trùng (100,0)
    doc = _doc(l1, l2)
    result = solve_constraints(doc, [_c("coincident_endpoint", "l1", "l2")])

    assert result.status == "okay"
    sp1, sp2 = result.solved_primitives["l1"], result.solved_primitives["l2"]
    dist = math.hypot(sp1.end.x - sp2.start.x, sp1.end.y - sp2.start.y)
    assert dist < 0.01, f"Sau solve 2 điểm phải trùng nhau, còn cách {dist}"
    print("OK   test_coincident_endpoint_constraint_enforced")


def test_collinear_constraint_enforced():
    l1 = _line("l1", 0, 0, 100, 0)
    l2 = _line("l2", 150, 3, 250, 3)  # song song, lệch khỏi đường thẳng y=0 một chút
    doc = _doc(l1, l2)
    result = solve_constraints(doc, [_c("parallel", "l1", "l2"), _c("collinear", "l1", "l2")])

    assert result.status == "okay"
    sp1, sp2 = result.solved_primitives["l1"], result.solved_primitives["l2"]
    # khoảng cách từ điểm đầu l2 tới đường thẳng qua l1 phải ~0
    ax, ay = sp1.end.x - sp1.start.x, sp1.end.y - sp1.start.y
    cross = ax * (sp2.start.y - sp1.start.y) - ay * (sp2.start.x - sp1.start.x)
    dist = abs(cross) / math.hypot(ax, ay)
    assert dist < 0.01, f"Sau solve phải thẳng hàng gần tuyệt đối, lệch {dist}"
    print("OK   test_collinear_constraint_enforced")


def test_unsupported_and_missing_primitive_constraints_are_skipped():
    l1 = _line("l1", 0, 0, 100, 0)
    l2 = _line("l2", 0, 50, 100, 50)
    doc = _doc(l1, l2)
    bogus = Constraint(type="parallel", primitive_ids=["l1", "does-not-exist"], confidence=1.0, tolerance={})
    result = solve_constraints(doc, [_c("parallel", "l1", "l2"), bogus])

    assert result.applied_constraint_count == 1
    assert bogus.id in result.skipped_constraints
    print("OK   test_unsupported_and_missing_primitive_constraints_are_skipped")


def test_empty_constraints_solves_trivially_with_zero_relevant_primitives():
    l1 = _line("l1", 0, 0, 100, 0)
    doc = _doc(l1)
    result = solve_constraints(doc, [])
    assert result.solved_primitives == {}
    assert result.applied_constraint_count == 0
    print("OK   test_empty_constraints_solves_trivially_with_zero_relevant_primitives")


def test_solver_capacity_guard_skips_construction_for_more_than_1000_unknowns(monkeypatch):
    """A dense scan must fall back before constructing an expensive solver."""
    import python_solvespace

    def unexpected_solver_construction():
        raise AssertionError("capacity guard must run before SolverSystem construction")

    monkeypatch.setattr(python_solvespace, "SolverSystem", unexpected_solver_construction)
    lines = [_line(f"l{i}", 0, i * 10, 100, i * 10) for i in range(251)]
    constraints = [_c("parallel", f"l{i}", f"l{i + 1}") for i in range(250)]

    result = solve_constraints(_doc(*lines), constraints)

    assert result.status == "too_many_unknowns"
    assert result.dof == 0
    assert result.solved_primitives == {}
    assert result.applied_constraint_count == 0


_TESTS = [
    test_parallel_constraint_makes_lines_exactly_parallel,
    test_perpendicular_constraint_enforced,
    test_equal_length_constraint_enforced,
    test_coincident_endpoint_constraint_enforced,
    test_collinear_constraint_enforced,
    test_unsupported_and_missing_primitive_constraints_are_skipped,
    test_empty_constraints_solves_trivially_with_zero_relevant_primitives,
    test_solver_capacity_guard_skips_construction_for_more_than_1000_unknowns,
]


def run_all():
    if not _HAS_SOLVESPACE:
        print("SKIP toàn bộ test_constraint_solving.py — chưa cài python-solvespace "
              "(pip install python-solvespace --break-system-packages)")
        return
    passed = 0
    for t in _TESTS:
        t()
        passed += 1
    print(f"\n{passed}/{len(_TESTS)} test PASS")


if __name__ == "__main__":
    run_all()
