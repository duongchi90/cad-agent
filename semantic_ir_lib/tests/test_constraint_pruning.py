"""
test_constraint_pruning.py — test cho `constraint_pruning.prune_constraints()`.

8 test đầu THUẦN LOGIC trên chính danh sách `Constraint` (không cần primitive
IR thật, không cần solvespace) — luôn chạy được. Test cuối (thứ 9) là test
TÍCH HỢP prune -> solve THẬT, tái hiện đúng tình huống đã gặp khi chạy
`demo_pipeline.py` trên dữ liệu Phase 1 thật (mô tả trong docstring
`constraint_pruning.py`, bước 4): 4 line nhóm ngang x 2 line nhóm dọc sinh
8 constraint 'perpendicular' dư thừa, đưa thẳng vào solver thật sẽ ra
INCONSISTENT, nhưng sau prune (chỉ còn 1 perpendicular đại diện + spanning
tree parallel mỗi nhóm) thì solver phải ra 'okay'. Test này tự SKIP nếu máy
chưa cài `python-solvespace`, cùng cách `test_constraint_solving.py` đã làm.
"""

from __future__ import annotations

from semantic_ir_lib.constraint_pruning import prune_constraints
from semantic_ir_lib.models import Constraint

try:
    import python_solvespace  # noqa: F401
    _HAS_SOLVESPACE = True
except ImportError:
    _HAS_SOLVESPACE = False


def _c(type_, a, b, confidence=0.9) -> Constraint:
    return Constraint(type=type_, primitive_ids=[a, b], confidence=confidence, tolerance={})


# ------------------------------------------------------------ bước 1: confidence --
def test_low_confidence_constraint_dropped():
    weak = _c("parallel", "l1", "l2", confidence=0.4)
    strong = _c("parallel", "l3", "l4", confidence=0.8)
    result = prune_constraints([weak, strong], min_confidence=0.6)

    assert weak.id in result.dropped_low_confidence
    assert strong.id not in result.dropped_low_confidence
    kept_ids = {c.id for c in result.kept}
    assert strong.id in kept_ids
    assert weak.id not in kept_ids
    print("OK   test_low_confidence_constraint_dropped")


# --------------------------------------------------------- bước 2: trùng lặp --
def test_duplicate_same_type_same_pair_keeps_highest_confidence():
    low = _c("equal_length", "l1", "l2", confidence=0.7)
    high = _c("equal_length", "l1", "l2", confidence=0.95)
    result = prune_constraints([low, high], min_confidence=0.6)

    kept_ids = {c.id for c in result.kept}
    assert high.id in kept_ids
    assert low.id not in kept_ids
    assert low.id in result.dropped_duplicate
    print("OK   test_duplicate_same_type_same_pair_keeps_highest_confidence")


def test_duplicate_detection_is_order_independent():
    # (l1,l2) và (l2,l1) cùng type phải bị coi là 1 cặp, không phân biệt thứ tự
    c1 = _c("parallel", "l1", "l2", confidence=0.7)
    c2 = _c("parallel", "l2", "l1", confidence=0.9)
    result = prune_constraints([c1, c2], min_confidence=0.6)

    kept_ids = {c.id for c in result.kept}
    assert len(kept_ids) == 1
    assert c2.id in kept_ids  # confidence cao hơn được giữ
    assert c1.id in result.dropped_duplicate
    print("OK   test_duplicate_detection_is_order_independent")


# ----------------------------------------------- bước 3: dư thừa bắc cầu --
def test_parallel_transitive_redundant_pruned_spanning_tree():
    # A//B, B//C, A//C: 3 constraint cho 1 nhóm 3 line -> chỉ cần 2 (spanning tree)
    ab = _c("parallel", "A", "B", confidence=0.9)
    bc = _c("parallel", "B", "C", confidence=0.8)
    ac = _c("parallel", "A", "C", confidence=0.7)  # cạnh yếu nhất -> dư thừa, bị bỏ
    result = prune_constraints([ab, bc, ac], min_confidence=0.6)

    kept_ids = {c.id for c in result.kept}
    assert ab.id in kept_ids
    assert bc.id in kept_ids
    assert ac.id not in kept_ids
    assert ac.id in result.dropped_transitive_redundant
    print("OK   test_parallel_transitive_redundant_pruned_spanning_tree")


def test_equal_length_and_parallel_are_independent_transitive_groups():
    # A//B (parallel) và A~B, B~C, A~C (equal_length) -- 2 quan hệ ĐỘC LẬP,
    # dư thừa bắc cầu equal_length không được ảnh hưởng bởi nhóm parallel
    parallel_ab = _c("parallel", "A", "B", confidence=0.9)
    eq_ab = _c("equal_length", "A", "B", confidence=0.9)
    eq_bc = _c("equal_length", "B", "C", confidence=0.8)
    eq_ac = _c("equal_length", "A", "C", confidence=0.7)  # dư thừa trong nhóm equal_length
    result = prune_constraints([parallel_ab, eq_ab, eq_bc, eq_ac], min_confidence=0.6)

    kept_ids = {c.id for c in result.kept}
    assert parallel_ab.id in kept_ids  # không bị đụng bởi union-find của equal_length
    assert eq_ab.id in kept_ids
    assert eq_bc.id in kept_ids
    assert eq_ac.id not in kept_ids
    assert eq_ac.id in result.dropped_transitive_redundant
    print("OK   test_equal_length_and_parallel_are_independent_transitive_groups")


def test_collinear_transitive_redundant_pruned():
    ab = _c("collinear", "A", "B", confidence=0.9)
    bc = _c("collinear", "B", "C", confidence=0.85)
    ac = _c("collinear", "A", "C", confidence=0.6)
    result = prune_constraints([ab, bc, ac], min_confidence=0.5)

    kept_ids = {c.id for c in result.kept}
    assert ab.id in kept_ids and bc.id in kept_ids
    assert ac.id not in kept_ids
    assert ac.id in result.dropped_transitive_redundant
    print("OK   test_collinear_transitive_redundant_pruned")


def test_coincident_endpoint_not_transitively_pruned():
    # coincident_endpoint KHÔNG bắc cầu -- dù A-B, B-C, A-C đều xuất hiện
    # (hình thành "chu trình" trong đồ thị), CẢ 3 phải được giữ lại vì đây
    # không phải quan hệ bắc cầu thật (2 điểm trùng ở 2 đầu khác nhau của
    # cùng 1 line không suy ra điểm thứ 3).
    ab = _c("coincident_endpoint", "A", "B", confidence=0.9)
    bc = _c("coincident_endpoint", "B", "C", confidence=0.85)
    ac = _c("coincident_endpoint", "A", "C", confidence=0.8)
    result = prune_constraints([ab, bc, ac], min_confidence=0.5)

    kept_ids = {c.id for c in result.kept}
    assert {ab.id, bc.id, ac.id} == kept_ids
    assert result.dropped_transitive_redundant == []
    print("OK   test_coincident_endpoint_not_transitively_pruned")


# ------------------------------------------- bước 4: dư thừa theo nhóm (perpendicular) --
def test_perpendicular_redundant_across_group_pair_pruned():
    # nhóm ngang: h1,h2,h3,h4 (nối bằng parallel thành 1 nhóm)
    # nhóm dọc: v1,v2 (nối bằng parallel thành 1 nhóm)
    # mọi cặp (hi, vj) đều có constraint 'perpendicular' -> 4*2=8 constraint,
    # nhưng chỉ có 1 CẶP NHÓM (nhóm-ngang, nhóm-dọc) nên chỉ cần giữ 1
    parallels = [
        _c("parallel", "h1", "h2", confidence=0.95),
        _c("parallel", "h2", "h3", confidence=0.9),
        _c("parallel", "h3", "h4", confidence=0.85),
        _c("parallel", "v1", "v2", confidence=0.9),
    ]
    perpendiculars = [
        _c("perpendicular", "h1", "v1", confidence=0.9),
        _c("perpendicular", "h1", "v2", confidence=0.88),
        _c("perpendicular", "h2", "v1", confidence=0.87),
        _c("perpendicular", "h2", "v2", confidence=0.86),
        _c("perpendicular", "h3", "v1", confidence=0.85),
        _c("perpendicular", "h3", "v2", confidence=0.84),
        _c("perpendicular", "h4", "v1", confidence=0.83),
        _c("perpendicular", "h4", "v2", confidence=0.63),  # đo lệch nhất trong nhóm
    ]
    result = prune_constraints(parallels + perpendiculars, min_confidence=0.6)

    kept_perp = [c for c in result.kept if c.type == "perpendicular"]
    assert len(kept_perp) == 1, f"phải chỉ còn đúng 1 perpendicular đại diện, còn {len(kept_perp)}"
    # constraint đại diện được giữ phải là cạnh confidence cao nhất trong nhóm
    assert kept_perp[0].id == perpendiculars[0].id
    assert len(result.dropped_group_redundant) == 7
    print("OK   test_perpendicular_redundant_across_group_pair_pruned")


# ---------------------------------------------------------------- tích hợp --
def test_integration_prune_then_solve_real_demo_scenario():
    """Tái hiện chính xác tình huống đã gặp khi chạy demo_pipeline.py trên
    dữ liệu Phase 1 thật: 4 line ngang + 2 line dọc, đưa THẲNG 8 constraint
    'perpendicular' (chưa prune) vào solver thật sẽ dễ ra INCONSISTENT vì
    sai số góc đo từ ảnh scan khác nhau ở mỗi cặp; sau prune (chỉ còn 1
    perpendicular đại diện + parallel spanning tree mỗi nhóm) solver phải
    ra 'okay'. Test SKIP nếu chưa cài python-solvespace."""
    if not _HAS_SOLVESPACE:
        print("SKIP test_integration_prune_then_solve_real_demo_scenario — "
              "chưa cài python-solvespace")
        return

    from primitive_ir_lib.models import (
        Calibration, LineGeometry, Point2D, Primitive, PrimitiveIRDocument,
        SourceDocument, Trace,
    )
    from semantic_ir_lib.constraint_solving import solve_constraints

    def _line(id_, x0, y0, x1, y1) -> Primitive:
        return Primitive(
            id=id_, type="line", source="geometry_opencv", confidence=0.9,
            trace=Trace(bbox_px=(0, 0, 10, 10)),
            geometry=LineGeometry(start=Point2D(x0, y0), end=Point2D(x1, y1)),
        )

    # 4 line ngang gần y=0/50/100/150, mỗi line lệch góc chút ít khác nhau
    h1 = _line("h1", 0, 0, 100, 0.2)
    h2 = _line("h2", 0, 50, 100, 49.7)
    h3 = _line("h3", 0, 100, 100, 100.6)
    h4 = _line("h4", 0, 150, 100, 149.3)
    # 2 line dọc gần x=0/100, lệch góc khác chút (đây là line "lệch nhất"
    # được nhắc trong docstring constraint_pruning.py: ~0.63°)
    v1 = _line("v1", 0, 0, 0.3, 150)
    v2 = _line("v2", 100, 0, 101.1, 150)

    doc = PrimitiveIRDocument(
        source_document=SourceDocument(file_name="x.png", page_index=0, image_width_px=200, image_height_px=200),
        calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
        primitives=[h1, h2, h3, h4, v1, v2],
    )

    parallels = [
        _c("parallel", "h1", "h2", confidence=0.95),
        _c("parallel", "h2", "h3", confidence=0.9),
        _c("parallel", "h3", "h4", confidence=0.85),
        _c("parallel", "v1", "v2", confidence=0.9),
    ]
    # mọi cặp ngang x dọc đều gần vuông góc -> 8 constraint dư thừa
    perpendiculars = [
        _c("perpendicular", h, v, confidence=0.9 - 0.03 * i)
        for i, (h, v) in enumerate(
            [("h1", "v1"), ("h1", "v2"), ("h2", "v1"), ("h2", "v2"),
             ("h3", "v1"), ("h3", "v2"), ("h4", "v1"), ("h4", "v2")]
        )
    ]
    raw_constraints = parallels + perpendiculars

    pruned = prune_constraints(raw_constraints, min_confidence=0.6)
    kept_perp = [c for c in pruned.kept if c.type == "perpendicular"]
    assert len(kept_perp) == 1, "prune phải rút 8 perpendicular xuống còn 1"

    result = solve_constraints(doc, pruned.kept)
    assert result.status == "okay", (
        f"solver phải ra 'okay' sau khi prune bỏ constraint dư thừa, "
        f"nhận '{result.status}'"
    )
    print("OK   test_integration_prune_then_solve_real_demo_scenario")


_TESTS = [
    test_low_confidence_constraint_dropped,
    test_duplicate_same_type_same_pair_keeps_highest_confidence,
    test_duplicate_detection_is_order_independent,
    test_parallel_transitive_redundant_pruned_spanning_tree,
    test_equal_length_and_parallel_are_independent_transitive_groups,
    test_collinear_transitive_redundant_pruned,
    test_coincident_endpoint_not_transitively_pruned,
    test_perpendicular_redundant_across_group_pair_pruned,
    test_integration_prune_then_solve_real_demo_scenario,
]


def run_all():
    passed = 0
    for t in _TESTS:
        t()
        passed += 1
    print(f"\n{passed}/{len(_TESTS)} test PASS")


if __name__ == "__main__":
    run_all()
