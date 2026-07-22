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
KHÔNG dùng `sys.dragged()` để "ghim" điểm — solvespace dùng dragged() như
1 constraint CỨNG (dùng cho tương tác kéo-thả trong GUI), ghim TẤT CẢ điểm
sẽ làm hệ INCONSISTENT ngay khi có 1 constraint chưa thoả mãn hoàn toàn
(đã test thật, xem lịch sử phiên làm việc). Thay vào đó: khởi tạo mọi điểm
tại đúng toạ độ mm đã đo (initial guess), KHÔNG ghim gì cả, để Newton-Raphson
của solver tự hội tụ về nghiệm GẦN initial guess nhất thoả mãn constraint —
đã test thật cho kết quả di chuyển tối thiểu (~dưới 1mm cho line lệch nhẹ).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

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

    relevant_ids = {pid for c in constraints for pid in c.primitive_ids if pid in line_by_id}

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
        skipped_: List[str] = []

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
                sys_.parallel(la, lb, wp_)
            elif c.type == "perpendicular":
                sys_.perpendicular(la, lb, wp_)
            elif c.type == "equal_length":
                sys_.equal(la, lb, wp_)
            elif c.type == "coincident_endpoint":
                prim_a, prim_b = line_by_id[a], line_by_id[b]
                which_a, which_b = _closest_endpoint_pair(
                    prim_a.geometry.start, prim_a.geometry.end,
                    prim_b.geometry.start, prim_b.geometry.end,
                )
                pt_a = point_handles_[a][0] if which_a == "start" else point_handles_[a][1]
                pt_b = point_handles_[b][0] if which_b == "start" else point_handles_[b][1]
                sys_.coincident(pt_a, pt_b, wp_)
            elif c.type == "collinear":
                # Chưa có constraint 'collinear' trực tiếp trong solvespace —
                # dùng point-line coincident (đã có sẵn 'parallel' riêng ở 1
                # Constraint khác cùng cặp, xem detect_constraints(): collinear
                # luôn đi kèm parallel) + ép 1 điểm của line b nằm trên line a.
                pt_b_start = point_handles_[b][0]
                sys_.coincident(pt_b_start, la, wp_)

            applied_ += 1

        flag = sys_.solve()
        return status_map.get(flag, f"unknown({flag})"), sys_, point_handles_, applied_, skipped_

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
    skipped: List[str] = []

    for attempt in attempts:
        status, sys, point_handles, applied, skipped = _build_and_solve(attempt)
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

    return SolveResult(
        status=status,
        dof=sys.dof(),
        solved_primitives=solved,
        skipped_constraints=skipped,
        applied_constraint_count=applied,
    )
