"""
pattern_compound.py — Phase 2 nâng cao: ghép nhiều primitive thành 1 linh
kiện phức hợp (compound part). Đây là việc còn lại quan trọng nhất của Phase 2
(mục 11.4 tài liệu kiến trúc), đứng phía trên pattern_recognition.py (single-
primitive parts) nhưng KHÔNG thay thế nó.

NGUYÊN TẮC THIẾT KẾ (bám sát dự án, mục 10.1/7):

1. KHÔNG đoán bừa: chỉ tạo compound khi luật hình học rõ ràng thoả mãn.
   Trường hợp thiếu 1 điều kiện → KHÔNG tạo, để lại cho Vision xử lý sau
   (Phase 4). Không bao giờ ép gán compound cho mọi nhóm primitive gần nhau.

2. TÁI DÙNG CONSTRAINT ĐÃ CÓ: module này nhận danh sách `constraints` do
   constraint_detection.py sinh ra (parallel/perpendicular/coincident_endpoint)
   làm input chính, KHÔNG tự đo lại hình học từ primitives. Lý do:
   - tránh 2 nguồn đo trùng lặp (detection đã đo góc/khoảng cách, compound
     chỉ cần xác minh điều kiện tổ hợp);
   - nếu ngưỡng detect thay đổi thì compound tự theo kịp, không cần giữ 1
     bộ ngưỡng thứ 2 trong module này (nguyên tắc "1 nguồn sự thật" đã áp
     dụng xuyên suốt: Detection tách Solving, Pruning tách Solving...).

3. CONFIDENCE COMPOUND = trung bình có trọng số của confidence các constraint
   thành phần × hệ số khớp hình học (0.5–1.0). Đây KHÔNG phải xác suất thống
   kê thật (cùng định nghĩa confidence ở pattern_recognition.py/constraint
   _detection.py) — chỉ để xếp hạng ưu tiên review, không phải quyết định
   chốt.

4. COMPOUND LÀ LỚP BỔ SUNG, không thay thế single-part: primitive tham gia
   compound vẫn giữ single-part của nó (vd 1 line vừa là 'thanh_ngang' vừa
   nằm trong 'khung_chu_nhat'). Lý do: Reviewer #2 (Phase 4) cần cả 2 góc
   nhìn — cấp primitive riêng lẻ (lỗi dịch thuật) lẫn cấp linh kiện (lỗi
   nhận thức compound).

4 part_type compound (xem semantic_ir.schema.json enum PartType):
- khung_chu_nhat: 4 line tạo khung kín (2 cặp parallel + perpendicular ở
  góc + 4 coincident_endpoint).
- gia_do (L-bracket): 2 line perpendicular + coincident_endpoint tại 1 đầu.
- ban_le (hinge): 2 line gần parallel + coincident_endpoint + 2 circle nhỏ
  (lo_bat_vit) gần endpoint của line.
- diem_noi: >=2 line có coincident_endpoint tại 1 điểm chung (điểm hàn/gia cố).
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Set, Tuple

from primitive_ir_lib.models import CircleGeometry, LineGeometry, Primitive, Point2D

from .models import Constraint, GeometrySummary, SemanticPart


# ============================================================ helper geometry ==
# Các helper này chỉ dùng cho việc mà constraint_detection KHÔNG đã làm: tra
# nhanh circle gần endpoint, và tính điểm chung của nhóm coincident. Không đo
# lại góc/khoảng cách line-line (đã có trong constraints[] input).

def _index_constraints_by_pair(constraints: List[Constraint]) -> Dict[Tuple[str, str], List[Constraint]]:
    """Index constraint theo cặp primitive_id (cả 2 thứ tự) để tra O(1).
    Trả dict {(id_a, id_b): [constraint, ...]} — cùng cặp có thể có nhiều
    constraint (vd parallel + coincident_endpoint)."""
    idx: Dict[Tuple[str, str], List[Constraint]] = {}
    for c in constraints:
        a, b = c.primitive_ids[0], c.primitive_ids[1]
        idx.setdefault((a, b), []).append(c)
        idx.setdefault((b, a), []).append(c)
    return idx


def _constraints_between(
    idx: Dict[Tuple[str, str], List[Constraint]],
    a: str, b: str, ctype: Optional[str] = None,
) -> List[Constraint]:
    """Lấy mọi constraint giữa primitive a-b, tuỳ chọn lọc theo type."""
    cs = idx.get((a, b), [])
    if ctype is None:
        return cs
    return [c for c in cs if c.type == ctype]


def _circle_near_point(
    prim_by_id: Dict[str, Primitive], pids_circle: List[str],
    point: Point2D, max_distance_mm: float,
) -> Optional[str]:
    """Tìm circle primitive gần `point` nhất, trong ngưỡng max_distance_mm
    (tính từ tâm circle tới point — vì lỗ bắt vít thực tế tâm trùng điểm bắt).
    Trả id circle gần nhất hoặc None."""
    best_id: Optional[str] = None
    best_dist = max_distance_mm
    for cid in pids_circle:
        prim = prim_by_id.get(cid)
        if prim is None or prim.type != "circle" or prim.geometry is None:
            continue
        assert isinstance(prim.geometry, CircleGeometry)
        d = math.hypot(prim.geometry.center.x - point.x, prim.geometry.center.y - point.y)
        if d <= best_dist:
            best_dist = d
            best_id = cid
    return best_id


def _avg_confidence(constraints: List[Constraint]) -> float:
    """Trung bình confidence của danh sách constraint (dùng cho compound).
    Danh sách rỗng -> 0.0 (compound không thể tạo mà không có constraint)."""
    if not constraints:
        return 0.0
    return sum(c.confidence for c in constraints) / len(constraints)


def _point_to_infinite_line_distance(pt: Point2D, a: Point2D, b: Point2D) -> float:
    """Khoảng cách từ pt tới ĐƯỜNG THẲNG vô hạn qua a-b (không phải đoạn).
    Dùng cho ban_le: đo gap giữa 2 line song song (point-to-line). Trùng định
    nghĩa với constraint_detection._point_to_infinite_line_distance nhưng tách
    ra ở đây để module này độc lập, không import ngược sang detection."""
    ax, ay = b.x - a.x, b.y - a.y
    seg_len = math.hypot(ax, ay)
    if seg_len == 0:
        return math.hypot(pt.x - a.x, pt.y - a.y)
    cross = ax * (pt.y - a.y) - ay * (pt.x - a.x)
    return abs(cross) / seg_len


# ============================================================ khung_chu_nhat ==
def _find_khung_chu_nhat(
    line_ids: List[str],
    idx: Dict[Tuple[str, str], List[Constraint]],
) -> List[SemanticPart]:
    """Tìm khung chữ nhật kín: 4 line thoả mãn đồng thời:
    - 2 cặp parallel (mỗi cặp 2 line trong 4 line);
    - perpendicular giữa mọi line khác nhóm;
    - coincident_endpoint khép kín tại 4 góc (mỗi line nối 2 line khác qua
      coincident_endpoint, tạo chu trình 4 đỉnh).

    Thuật toán: với mỗi cặp parallel (a,b), tìm 1 cặp parallel khác (c,d) sao
    cho a-c, a-d, b-c, b-d đều có coincident_endpoint và perpendicular. Để
    tránh trùng, cặp (c,d) chỉ xét khi (c,d) > (a,b) theo thứ tự id.

    Chấp nhận khung có sai số nhỏ (detect từ ảnh scan không khép kín hoàn hảo)
    — đã được constraint_detection bắt qua ngưỡng distance/angle tolerance.
    """
    parts: List[SemanticPart] = []
    used: Set[Tuple[str, str, str, str]] = set()  # tránh khung trùng (cùng 4 line khác thứ tự)

    # gom tất cả cặp parallel thành list, index nhanh
    parallel_pairs: List[Tuple[str, str]] = []
    seen_parallel: Set[Tuple[str, str]] = set()
    for la in line_ids:
        for lb in line_ids:
            if la >= lb:
                continue
            if _constraints_between(idx, la, lb, "parallel"):
                parallel_pairs.append((la, lb))
                seen_parallel.add((la, lb))

    n = len(parallel_pairs)
    for i in range(n):
        a, b = parallel_pairs[i]
        for j in range(i + 1, n):
            c, d = parallel_pairs[j]
            if len({a, b, c, d}) != 4:
                continue  # có primitive trùng giữa 2 cặp parallel -> không phải khung 4 line

            # 4 góc khép kín: mỗi line phải coincident_endpoint với 2 line thuộc cặp kia
            coincs = [
                _constraints_between(idx, a, c, "coincident_endpoint"),
                _constraints_between(idx, a, d, "coincident_endpoint"),
                _constraints_between(idx, b, c, "coincident_endpoint"),
                _constraints_between(idx, b, d, "coincident_endpoint"),
            ]
            # mỗi line phải nối >=2 line khác qua coincident -> cần >=3/4 góc
            # (cho phép 1 góc hở do ảnh scan, nhưng không dưới 3)
            corners_present = sum(1 for cc in coincs if cc)
            if corners_present < 3:
                continue

            # perpendicular giữa 2 nhóm: >=1 cặp perpendicular làm chứng
            # (không yêu cầu cả 4 vì constraint_pruning sẽ rút gọn nhóm sau)
            has_perp = any(
                _constraints_between(idx, x, y, "perpendicular")
                for x in (a, b) for y in (c, d)
            )
            if not has_perp:
                continue

            key = tuple(sorted([a, b, c, d]))
            if key in used:
                continue
            used.add(key)

            # confidence: trung bình confidence các constraint thành phần
            all_cs: List[Constraint] = []
            all_cs += _constraints_between(idx, a, b, "parallel")
            all_cs += _constraints_between(idx, c, d, "parallel")
            for cc in coincs:
                all_cs += cc
            base_conf = _avg_confidence(all_cs) if all_cs else 0.0
            # hệ số khớp: 4/4 góc = 1.0, 3/4 góc = 0.85 (cho phép hở nhẹ)
            fit = 1.0 if corners_present == 4 else 0.85
            confidence = round(min(1.0, max(0.5, base_conf * fit)), 3)

            parts.append(SemanticPart(
                part_type="khung_chu_nhat",
                primitive_ids=list(key),
                confidence=confidence,
                source="rule_geometry",
                geometry_summary=GeometrySummary(),  # khung không có 1 length/orientation duy nhất
            ))
    return parts


# ================================================================== gia_do ===
def _find_gia_do(
    line_ids: List[str],
    idx: Dict[Tuple[str, str], List[Constraint]],
) -> List[SemanticPart]:
    """Tìm L-bracket (gia đỡ góc vuông): 2 line perpendicular + coincident
   _endpoint tại 1 đầu chung. Đây là compound đơn giản nhất — dạng chữ L.

    Chú ý: mọi cặp line perpendicular + coincident_endpoint đều thoả, nhưng
    để tránh trùng với khung_chu_nhat (4 line cũng chứa nhiều cặp L), module
    này tạo TẤT CẢ cặp thoả mãn — bước lọc trùng/lựa chọn ưu tiên (compound
    nào 'ăn' primitive nào) để lại cho caller/demo quyết định. Mặc định
    assemble.py gộp tất cả, Reviewer #2 (Phase 4) sẽ chọn nhìn cái nào.
    """
    parts: List[SemanticPart] = []
    n = len(line_ids)
    for i in range(n):
        a = line_ids[i]
        for j in range(i + 1, n):
            b = line_ids[j]
            perp = _constraints_between(idx, a, b, "perpendicular")
            coinc = _constraints_between(idx, a, b, "coincident_endpoint")
            if not perp or not coinc:
                continue
            all_cs = perp + coinc
            confidence = round(_avg_confidence(all_cs), 3)
            parts.append(SemanticPart(
                part_type="gia_do",
                primitive_ids=[a, b],
                confidence=confidence,
                source="rule_geometry",
                geometry_summary=GeometrySummary(),  # 2 line khác hướng -> không có orientation đơn
            ))
    return parts


# ================================================================== ban_le ===
def _find_ban_le(
    prim_by_id: Dict[str, Primitive],
    line_ids: List[str],
    circle_ids: List[str],
    idx: Dict[Tuple[str, str], List[Constraint]],
    bolt_hole_search_radius_mm: float = 30.0,
    parallel_gap_max_mm: float = 50.0,
) -> List[SemanticPart]:
    """Tìm bản lề (hinge): 2 line gần song song + 2 circle nhỏ (lo_bat_vit)
    gần endpoint của line.

    Cấu trúc bản lề thực tế: 2 lá kim loại song song ghép bằng 1 trục (circle)
    ở 1 đầu, và bắt vít (circle) ở đầu kia. Module này tìm pattern: cặp line
    parallel, mỗi line có circle nhỏ gần endpoint.

    KHÁC gia_do/khung_chu_nhat: 2 line của bản lề KHÔNG coincident_endpoint
    (lá kim loại có độ dày nên 2 line song song cách nhau vài mm). Do đó luật
    ban_le chỉ yêu cầu parallel + 2 circle, KHÔNG yêu cầu coincident_endpoint.

    bolt_hole_search_radius_mm: khoảng cách tối đa từ tâm circle tới endpoint
    của line để coi circle thuộc bản lề đó (ngưỡng đề xuất, chưa benchmark).
    parallel_gap_max_mm: khoảng cách tối đa giữa 2 line song song để coi là
    cùng bản lề (tránh ghép 2 line song song ở 2 view khác nhau). Ngưỡng này
    đo khoảng cách point-to-line giữa endpoint line này với đường vô hạn line kia.
    """
    parts: List[SemanticPart] = []
    n = len(line_ids)
    for i in range(n):
        la_id = line_ids[i]
        la = prim_by_id.get(la_id)
        if la is None or la.geometry is None:
            continue
        for j in range(i + 1, n):
            lb_id = line_ids[j]
            lb = prim_by_id.get(lb_id)
            if lb is None or lb.geometry is None:
                continue

            parallel = _constraints_between(idx, la_id, lb_id, "parallel")
            if not parallel:
                continue

            # kiểm gap giữa 2 line song song (point-to-line distance) để loại
            # 2 line song song ở 2 view khác nhau
            gap = _point_to_infinite_line_distance(
                la.geometry.start, lb.geometry.start, lb.geometry.end)
            if gap > parallel_gap_max_mm:
                continue

            # 2 circle gần endpoint của line (thường 1 đầu là trục, 1 đầu bắt vít).
            # Tìm 2 circle khác nhau, mỗi cái gần 1 endpoint.
            endpoints_la = [la.geometry.start, la.geometry.end]
            endpoints_lb = [lb.geometry.start, lb.geometry.end]
            candidate_points = endpoints_la + endpoints_lb

            found_circles: List[str] = []
            for pt in candidate_points:
                cid = _circle_near_point(prim_by_id, circle_ids, pt, bolt_hole_search_radius_mm)
                if cid is not None and cid not in found_circles:
                    found_circles.append(cid)
                if len(found_circles) >= 2:
                    break

            if len(found_circles) < 2:
                continue  # thiếu circle -> không đủ bằng kiện bản lề, KHÔNG đoán bừa

            prim_ids = [la_id, lb_id] + found_circles
            base_conf = _avg_confidence(parallel) if parallel else 0.5
            # có đủ 2 circle -> hệ số khớp 1.0 (đã kiểm ở trên)
            confidence = round(min(1.0, base_conf), 3)
            parts.append(SemanticPart(
                part_type="ban_le",
                primitive_ids=prim_ids,
                confidence=confidence,
                source="rule_geometry",
                geometry_summary=GeometrySummary(),  # compound phức -> không có summary đơn
            ))
    return parts


# ================================================================ diem_noi ===
def _find_diem_noi(
    prim_by_id: Dict[str, Primitive],
    line_ids: List[str],
    idx: Dict[Tuple[str, str], List[Constraint]],
    coincident_distance_mm: float = 2.0,
) -> List[SemanticPart]:
    """Tìm điểm nối (điểm hàn/gia cố): nhóm >=2 line có coincident_endpoint
    tại cùng 1 điểm không gian. Khác gia_do (chỉ 2 line, không yêu cầu
    perpendicular), diem_noi gom mọi line gặp nhau tại 1 điểm — thường là nút
    cấu trúc có nhiều thanh hội tụ.

    Thuật toán: cluster endpoint của các line theo khoảng cách (ngưỡng
    coincident_distance_mm, đồng bộ với distance_tolerance_mm mặc định của
    constraint_detection). Mỗi cluster có >=3 line endpoint (>=2 line, vì 1
    line có thể đóng góp 2 endpoint) -> 1 diem_noi.

    Để tránh trùng lặp quá mức với gia_do: diem_noi chỉ tạo khi cluster có
    >=3 line endpoint (nhiều hơn 1 cặp đơn giản). Cluster 2 endpoint chỉ là
    gia_do/điểm nối 2 line, đã được part_type khác bao phủ.
    """
    # gom endpoint: (line_id, point)
    endpoints: List[Tuple[str, Point2D]] = []
    for lid in line_ids:
        prim = prim_by_id.get(lid)
        if prim is None or prim.geometry is None:
            continue
        assert isinstance(prim.geometry, LineGeometry)
        endpoints.append((lid, prim.geometry.start))
        endpoints.append((lid, prim.geometry.end))

    # Union-Find theo khoảng cách: 2 endpoint cùng cluster nếu gần nhau
    parent = list(range(len(endpoints)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    n = len(endpoints)
    for i in range(n):
        for j in range(i + 1, n):
            _, pi = endpoints[i]
            _, pj = endpoints[j]
            if math.hypot(pi.x - pj.x, pi.y - pj.y) <= coincident_distance_mm:
                union(i, j)

    # nhóm cluster theo root
    clusters: Dict[int, List[int]] = {}
    for k in range(n):
        clusters.setdefault(find(k), []).append(k)

    parts: List[SemanticPart] = []
    for members in clusters.values():
        line_set: Set[str] = set()
        for k in members:
            line_set.add(endpoints[k][0])
        if len(line_set) < 3:
            continue  # cluster < 3 line -> không phải nút đa thanh, để gia_do xử lý

        # confidence: xác minh mọi cặp line trong cluster ĐÃ có coincident_endpoint
        # constraint (nếu detect đã chạy đúng, phải có) — hệ số = tỷ lệ cặp có constraint
        line_list = sorted(line_set)
        pair_total = 0
        pair_with_constraint = 0
        all_cs: List[Constraint] = []
        for x in range(len(line_list)):
            for y in range(x + 1, len(line_list)):
                pair_total += 1
                cs = _constraints_between(idx, line_list[x], line_list[y], "coincident_endpoint")
                if cs:
                    pair_with_constraint += 1
                    all_cs.extend(cs)
        if pair_total == 0:
            continue
        # không yêu cầu 100% cặp có constraint (cluster nhóm theo điểm có thể
        # nối qua trung gian) nhưng yêu cầu >=50% để chắc đây là nút thật
        if pair_with_constraint / pair_total < 0.5:
            continue
        base_conf = _avg_confidence(all_cs) if all_cs else 0.5
        fit = pair_with_constraint / pair_total
        confidence = round(min(1.0, max(0.5, base_conf * (0.5 + 0.5 * fit))), 3)
        parts.append(SemanticPart(
            part_type="diem_noi",
            primitive_ids=line_list,
            confidence=confidence,
            source="rule_geometry",
            geometry_summary=GeometrySummary(),
        ))
    return parts


# ============================================================= entry point ===
def build_compound_parts(
    primitives: List[Primitive],
    constraints: List[Constraint],
    bolt_hole_search_radius_mm: float = 30.0,
    parallel_gap_max_mm: float = 50.0,
    coincident_distance_mm: float = 2.0,
) -> List[SemanticPart]:
    """Entry point Phase 2 nâng cao. Nhận primitives + constraints đã detect
    (tái dùng, không đo lại), trả DANH SÁCH compound parts.

    Args:
        primitives: danh sách Primitive gốc (cần để tra circle/endpoint line).
        constraints: danh sách Constraint do constraint_detection.py sinh ra.
        bolt_hole_search_radius_mm: ngưỡng circle gần endpoint cho ban_le.
        parallel_gap_max_mm: gap tối đa giữa 2 line song song cho ban_le.
        coincident_distance_mm: ngưỡng cluster endpoint cho diem_noi (nên đồng
            bộ với distance_tolerance_mm của constraint_detection, mặc định 2.0).

    Returns:
        List[SemanticPart] — chỉ compound parts (khung_chu_nhat/gia_do/ban_le/
        diem_noi). Single-primitive parts do pattern_recognition.py tạo riêng,
        caller tự gộp (xem assemble.py). Trả rỗng nếu không có pattern nào
        thoả mãn — KHÔNG ép gán bừa.
    """
    prim_by_id: Dict[str, Primitive] = {p.id: p for p in primitives}
    line_ids = [p.id for p in primitives if p.type == "line"]
    circle_ids = [p.id for p in primitives if p.type == "circle"]
    idx = _index_constraints_by_pair(constraints)

    raw: List[SemanticPart] = []
    raw += _find_khung_chu_nhat(line_ids, idx)
    raw += _find_gia_do(line_ids, idx)
    raw += _find_ban_le(prim_by_id, line_ids, circle_ids, idx, bolt_hole_search_radius_mm, parallel_gap_max_mm)
    raw += _find_diem_noi(prim_by_id, line_ids, idx, coincident_distance_mm)

    # Ưu tiên compound lớn: 1 primitive chỉ thuộc nhiều nhất 1 compound. Xếp
    # theo số primitive giảm dần + confidence giảm dần, rồi lấy compound greedily
    # nếu chưa có primitive nào trong nó bị "ăn" bởi compound trước. Lý do: nếu
    # 4 line tạo khung_chu_nhat thì KHÔNG nên tách thành 4 gia_do riêng lẻ —
    # đúng ngữ nghĩa là 1 linh kiện khung, không phải 4 giá đỡ. Nguyên tắc
    # "không đoán bừa": không gán trùng primitive vào nhiều compound (gây
    # Reviewer #2 hiểu sai số lượng linh kiện thật).
    raw.sort(key=lambda p: (-len(p.primitive_ids), -p.confidence))
    consumed: Set[str] = set()
    parts: List[SemanticPart] = []
    for p in raw:
        if any(pid in consumed for pid in p.primitive_ids):
            continue
        parts.append(p)
        consumed.update(p.primitive_ids)
    return parts
