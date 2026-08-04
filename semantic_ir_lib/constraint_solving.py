"""
constraint_solving.py — tích hợp `python-solvespace` THẬT (không phải mock),
đóng phần "Constraint Solving" trong sơ đồ pipeline (mục 2 tài liệu kiến
trúc). Nhận `constraints[]` (nên là bản đã `prune_constraints()` — solver
thật sẽ báo INCONSISTENT nếu đưa thẳng danh sách chưa lọc chứa nhiều cạnh
dư thừa mâu thuẫn nhau về số, đã test thật trong quá trình viết module này).

MỤC ĐÍCH: "làm sạch" hình học — line trong bản vẽ scan luôn có sai số đo
nhỏ (song song nhưng lệch vài độ, độ dài chênh vài mm...). Solver tìm toạ độ
GẦN NHẤT với toạ độ đo được mà thoả mãn CHÍNH XÁC các constraint đã phát
hiện, dùng làm input sạch cho DXF Builder (ezdxf) ở bước sau — tránh vẽ lại
đúng y nguyên sai số của ảnh scan vào bản vẽ CAD.

CHIẾN LƯỢC KHỞI TẠO (quan trọng, đã test thật — xem ghi chú bên dưới):
khởi tạo mọi điểm tại đúng toạ độ mm đã đo (initial guess), không ghim hàng
loạt, để Newton-Raphson tự hội tụ về nghiệm gần nhất thoả mãn constraint.
Chỉ khi caller cung cấp một `DatumAnchor` tường minh mới dùng `dragged()` cho
đúng một điểm gốc và `horizontal()` cho trục X; cách này loại chuyển động cứng
mà không khoá toàn bộ hình học.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Sequence, Tuple

from primitive_ir_lib.models import Point2D, Primitive, PrimitiveIRDocument

from .models import Constraint

_SUPPORTED_TYPES = {"parallel", "perpendicular", "equal_length", "coincident_endpoint", "collinear"}
_COORDINATE_UNKNOWNS_PER_LINE = 4
_MAX_SOLVER_UNKNOWNS = 1_000


@dataclass
class SolvedPrimitive:
    primitive_id: str
    start: Point2D
    end: Point2D
    displacement_mm: float  # khoảng cách tổng (start+end) so với toạ độ đo gốc


@dataclass
class SolveResult:
    status: str  # "okay" | "inconsistent" | "didnt_converge" | "too_many_unknowns"
    dof: int
    solved_primitives: Dict[str, SolvedPrimitive] = field(default_factory=dict)
    skipped_constraints: List[str] = field(default_factory=list)  # id constraint không áp dụng được
    applied_constraint_count: int = 0
    model_dof: int | None = None
    applied_driving_length_count: int = 0
    driving_length_residual_mm: Dict[str, float] = field(default_factory=dict)
    conflict_constraint_ids: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class DrivingLengthConstraint:
    id: str
    primitive_id: str
    value_mm: float


@dataclass(frozen=True)
class DatumAnchor:
    id: str
    origin_primitive_id: str
    origin_endpoint: Literal["start", "end"]
    x_axis_primitive_id: str


def _closest_endpoint_pair(
    li_start: Point2D, li_end: Point2D, lj_start: Point2D, lj_end: Point2D,
) -> Tuple[str, str]:
    """Suy lại CẶP điểm đầu/cuối nào của 2 line là cặp gần nhau nhất — dùng
    cho constraint 'coincident_endpoint'. `detect_constraints()` (Phase 2)
    chỉ lưu khoảng cách nhỏ nhất đo được (measured), KHÔNG lưu cặp điểm cụ
    thể (start-start hay start-end...) vì Primitive IR/Semantic IR không
    cần biết chi tiết đó — solver thì cần, nên tính lại ở đây thay vì đổi
    schema chỉ để phục vụ 1 module tiêu thụ."""
    import math

    def d(a: Point2D, b: Point2D) -> float:
        return math.hypot(a.x - b.x, a.y - b.y)

    candidates = [
        ("start", "start", d(li_start, lj_start)),
        ("start", "end", d(li_start, lj_end)),
        ("end", "start", d(li_end, lj_start)),
        ("end", "end", d(li_end, lj_end)),
    ]
    best = min(candidates, key=lambda c: c[2])
    return best[0], best[1]


def solve_constraints(
    primitive_doc: PrimitiveIRDocument,
    constraints: List[Constraint],
    *,
    driving_lengths: Sequence[DrivingLengthConstraint] = (),
    datum_anchor: DatumAnchor | None = None,
) -> SolveResult:
    """Entry point. `constraints` nên là output đã qua
    `constraint_pruning.prune_constraints()` — hàm này KHÔNG tự prune (tách
    trách nhiệm rõ ràng: prune là quyết định 'constraint nào dư thừa',
    solve là 'giải hệ với constraint đã cho', không trộn 2 việc).

    Raise ImportError nếu chưa cài `python-solvespace` (optional dependency,
    xem requirements.txt — cùng chiến lược lazy-import như vision_client.py).
    """
    try:
        from python_solvespace import ResultFlag, SolverSystem
    except ImportError as exc:
        raise ImportError(
            "Cần cài package 'python-solvespace' để dùng Constraint Solving thật: "
            "pip install python-solvespace --break-system-packages"
        ) from exc

    line_by_id: Dict[str, Primitive] = {
        p.id: p for p in primitive_doc.primitives if p.type == "line" and p.geometry is not None
    }

    driving_ids: set[str] = set()
    for driving in driving_lengths:
        if not driving.id or driving.id in driving_ids:
            raise ValueError("driving length ids must be non-empty and unique")
        driving_ids.add(driving.id)
        if (
            isinstance(driving.value_mm, bool)
            or not isinstance(driving.value_mm, (int, float))
            or not math.isfinite(driving.value_mm)
            or driving.value_mm <= 0
        ):
            raise ValueError(f"driving length {driving.id} value_mm must be finite positive")
        if driving.primitive_id not in line_by_id:
            raise ValueError(
                f"driving length {driving.id} references missing line {driving.primitive_id}"
            )

    if datum_anchor is not None:
        if not datum_anchor.id:
            raise ValueError("datum anchor id must be non-empty")
        if datum_anchor.origin_endpoint not in {"start", "end"}:
            raise ValueError("datum anchor origin_endpoint must be start or end")
        if datum_anchor.origin_primitive_id not in line_by_id:
            raise ValueError("datum anchor origin primitive must reference an existing line")
        if datum_anchor.x_axis_primitive_id not in line_by_id:
            raise ValueError("datum anchor x-axis primitive must reference an existing line")

    relevant_ids = {pid for c in constraints for pid in c.primitive_ids if pid in line_by_id}
    relevant_ids.update(driving.primitive_id for driving in driving_lengths)
    if datum_anchor is not None:
        relevant_ids.update(
            {datum_anchor.origin_primitive_id, datum_anchor.x_axis_primitive_id}
        )

    # SolveSpace receives two point coordinates for every relevant line. Its
    # nonlinear solve is retried in three constraint orders below, so starting
    # a system above this capacity makes a safe fallback consume minutes of
    # CPU on dense scans. The DXF caller preserves calibrated input geometry
    # for this existing explicit status.
    if len(relevant_ids) * _COORDINATE_UNKNOWNS_PER_LINE > _MAX_SOLVER_UNKNOWNS:
        return SolveResult(status="too_many_unknowns", dof=0)

    status_map = {
        ResultFlag.OKAY: "okay",
        ResultFlag.INCONSISTENT: "inconsistent",
        ResultFlag.DIDNT_CONVERGE: "didnt_converge",
        ResultFlag.TOO_MANY_UNKNOWNS: "too_many_unknowns",
    }

    def _build_and_solve(ordered_constraints: List[Constraint]):
        """Dựng 1 SolverSystem MỚI HOÀN TOÀN và áp constraint theo đúng thứ
        tự `ordered_constraints`, rồi solve. Phải dựng lại từ đầu mỗi lần
        thử (không tái dùng `sys` cũ) vì solvespace không hỗ trợ "undo" áp
        constraint theo thứ tự khác trên cùng 1 hệ đã solve dở."""
        sys_ = SolverSystem()
        wp_ = sys_.create_2d_base()
        point_handles_: Dict[str, Tuple[object, object]] = {}
        line_handles_: Dict[str, object] = {}

        for pid in relevant_ids:
            prim = line_by_id[pid]
            s, e = prim.geometry.start, prim.geometry.end
            p_start = sys_.add_point_2d(s.x, s.y, wp_)
            p_end = sys_.add_point_2d(e.x, e.y, wp_)
            point_handles_[pid] = (p_start, p_end)
            line_handles_[pid] = sys_.add_line_2d(p_start, p_end, wp_)

        applied_ = 0
        applied_driving_ = 0
        skipped_: List[str] = []
        constraint_id_by_handle_: Dict[int, str] = {}

        def _record_constraint(source_id: str, operation) -> None:
            before = sys_.cons_len()
            operation()
            for handle in range(before + 1, sys_.cons_len() + 1):
                constraint_id_by_handle_[handle] = source_id

        for c in ordered_constraints:
            if c.type not in _SUPPORTED_TYPES:
                skipped_.append(c.id)
                continue
            a, b = c.primitive_ids
            if a not in line_handles_ or b not in line_handles_:
                skipped_.append(c.id)  # constraint tham chiếu primitive không phải line hợp lệ
                continue

            la, lb = line_handles_[a], line_handles_[b]

            if c.type == "parallel":
                _record_constraint(c.id, lambda: sys_.parallel(la, lb, wp_))
            elif c.type == "perpendicular":
                _record_constraint(c.id, lambda: sys_.perpendicular(la, lb, wp_))
            elif c.type == "equal_length":
                _record_constraint(c.id, lambda: sys_.equal(la, lb, wp_))
            elif c.type == "coincident_endpoint":
                prim_a, prim_b = line_by_id[a], line_by_id[b]
                which_a, which_b = _closest_endpoint_pair(
                    prim_a.geometry.start, prim_a.geometry.end,
                    prim_b.geometry.start, prim_b.geometry.end,
                )
                pt_a = point_handles_[a][0] if which_a == "start" else point_handles_[a][1]
                pt_b = point_handles_[b][0] if which_b == "start" else point_handles_[b][1]
                _record_constraint(c.id, lambda: sys_.coincident(pt_a, pt_b, wp_))
            elif c.type == "collinear":
                # Chưa có constraint 'collinear' trực tiếp trong solvespace —
                # dùng point-line coincident (đã có sẵn 'parallel' riêng ở 1
                # Constraint khác cùng cặp, xem detect_constraints(): collinear
                # luôn đi kèm parallel) + ép 1 điểm của line b nằm trên line a.
                pt_b_start = point_handles_[b][0]
                _record_constraint(c.id, lambda: sys_.coincident(pt_b_start, la, wp_))

            applied_ += 1

        for driving in driving_lengths:
            p_start, p_end = point_handles_[driving.primitive_id]
            _record_constraint(
                driving.id,
                lambda p_start=p_start, p_end=p_end, driving=driving: sys_.distance(
                    p_start,
                    p_end,
                    driving.value_mm,
                    wp_,
                ),
            )
            applied_driving_ += 1

        if datum_anchor is not None:
            origin_points = point_handles_[datum_anchor.origin_primitive_id]
            origin_point = origin_points[0] if datum_anchor.origin_endpoint == "start" else origin_points[1]
            _record_constraint(
                f"{datum_anchor.id}.origin",
                lambda: sys_.dragged(origin_point, wp_),
            )
            _record_constraint(
                f"{datum_anchor.id}.x_axis",
                lambda: sys_.horizontal(line_handles_[datum_anchor.x_axis_primitive_id], wp_),
            )

        flag = sys_.solve()
        return (
            status_map.get(flag, f"unknown({flag})"),
            sys_,
            point_handles_,
            applied_,
            applied_driving_,
            skipped_,
            constraint_id_by_handle_,
        )

    # THỬ NHIỀU THỨ TỰ áp constraint — đã test thật và xác nhận Newton-Raphson
    # của solvespace NHẠY VỚI THỨ TỰ constraint được thêm vào cho initial
    # guess đo từ ảnh scan (không phải do hệ mâu thuẫn thật): với cùng 1 bộ
    # constraint hợp lệ về mặt toán, thêm 'perpendicular'/'coincident_endpoint'
    # (chỉ ràng buộc 1 bậc tự do, "cục bộ") TRƯỚC 'parallel'/'equal_length'/
    # 'collinear' (ràng buộc lan toả qua nhiều line theo nhóm) hội tụ ổn định
    # hơn hẳn thứ tự ngược lại — đã tái hiện bằng dữ liệu Phase 1 thật
    # (`semantic_ir_lib/demo_pipeline.py`): cùng 7 constraint, thứ tự gốc ra
    # DIDNT_CONVERGE, thứ tự ưu tiên dưới đây ra OKAY. Thử thêm thứ tự đảo
    # ngược hoàn toàn làm phương án dự phòng cuối cùng cho các bộ dữ liệu
    # khác có thể nhạy theo chiều ngược lại.
    _local_first = {"perpendicular": 0, "coincident_endpoint": 0,
                     "parallel": 1, "equal_length": 1, "collinear": 1}
    attempts = [
        sorted(constraints, key=lambda c: _local_first.get(c.type, 1)),  # ưu tiên ràng buộc cục bộ
        list(constraints),  # thứ tự gốc do caller cung cấp
        list(reversed(constraints)),  # đảo ngược, dự phòng cuối
    ]

    status = "didnt_converge"
    sys = None
    point_handles: Dict[str, Tuple[object, object]] = {}
    applied = 0
    applied_driving = 0
    skipped: List[str] = []
    constraint_id_by_handle: Dict[int, str] = {}

    for attempt in attempts:
        (
            status,
            sys,
            point_handles,
            applied,
            applied_driving,
            skipped,
            constraint_id_by_handle,
        ) = _build_and_solve(attempt)
        if status == "okay":
            break

    solved: Dict[str, SolvedPrimitive] = {}
    for pid, (p_start, p_end) in point_handles.items():
        sx, sy = sys.params(p_start.params)
        ex, ey = sys.params(p_end.params)
        orig = line_by_id[pid].geometry
        displacement = (
            ((sx - orig.start.x) ** 2 + (sy - orig.start.y) ** 2) ** 0.5
            + ((ex - orig.end.x) ** 2 + (ey - orig.end.y) ** 2) ** 0.5
        )
        solved[pid] = SolvedPrimitive(
            primitive_id=pid,
            start=Point2D(round(sx, 4), round(sy, 4)),
            end=Point2D(round(ex, 4), round(ey, 4)),
            displacement_mm=round(displacement, 4),
        )

    residuals = {
        driving.id: round(
            abs(
                math.hypot(
                    solved[driving.primitive_id].end.x
                    - solved[driving.primitive_id].start.x,
                    solved[driving.primitive_id].end.y
                    - solved[driving.primitive_id].start.y,
                )
                - driving.value_mm
            ),
            9,
        )
        for driving in driving_lengths
    }
    conflict_constraint_ids = sorted(
        {
            constraint_id_by_handle[handle]
            for handle in sys.failures()
            if handle in constraint_id_by_handle
        }
    )

    return SolveResult(
        status=status,
        dof=sys.dof(),
        solved_primitives=solved,
        skipped_constraints=skipped,
        applied_constraint_count=applied,
        model_dof=max(0, sys.dof() - 6) if datum_anchor is not None else None,
        applied_driving_length_count=applied_driving,
        driving_length_residual_mm=residuals,
        conflict_constraint_ids=conflict_constraint_ids,
    )
