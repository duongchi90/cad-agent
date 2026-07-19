"""
constraint_pruning.py — bước "Constraint Pruning" đứng giữa Constraint
Detection (constraint_detection.py, sinh constraint THÔ theo từng cặp
line độc lập) và Constraint Solving (constraint_solving.py, cần
`constraints[]` KHÔNG dư thừa/mâu thuẫn — xem ghi chú trong docstring của
constraint_solving.py: đưa thẳng list chưa lọc dễ khiến solver thật báo
INCONSISTENT).

VÌ SAO CẦN PRUNE: `detect_constraints()` xét TỪNG CẶP line độc lập
(O(n^2)), nên với 1 nhóm >=3 line có cùng quan hệ (vd 3 thanh song song,
hoặc 4 thanh bằng độ dài) sẽ sinh ra constraint cho MỌI cặp trong nhóm —
tức là dư thừa về mặt đại số: nếu A//B và B//C thì A//C đã bị ép buộc,
không cần thêm 1 constraint 'parallel' riêng cho (A,C). Đưa cả 3 cạnh dư
thừa này vào solver không sai về mặt toán (vẫn có nghiệm), nhưng với dữ
liệu đo từ ảnh scan có sai số nhỏ khác nhau ở mỗi cặp, các phương trình dư
thừa đó có thể xung đột nhau ở mức dưới ngưỡng hội tụ của solver, khiến
SolverSystem trả INCONSISTENT dù về hình học tổng thể là hợp lý.

CHIẾN LƯỢC (đã cân nhắc, xem test_constraint_pruning.py):
1) Lọc ngưỡng tin cậy: bỏ constraint có confidence < min_confidence (default
   0.6) — quan hệ đo được yếu, không nên ép cứng vào hình học đã "làm sạch".
2) Khử trùng lặp tuyệt đối: cùng type + cùng cặp primitive (không phân biệt
   thứ tự) chỉ giữ 1 bản duy nhất, ưu tiên confidence cao nhất.
3) Khử dư thừa bắc cầu CHỈ áp dụng cho 3 loại quan hệ có tính chất bắc cầu
   thật sự (A~B và B~C => A~C): 'parallel', 'equal_length', 'collinear'.
   Dùng Union-Find: duyệt constraint theo thứ tự confidence giảm dần, với
   mỗi constraint — nếu 2 primitive đã cùng nhóm (đã có đường nối bắc cầu
   qua constraint khác cùng loại) thì bỏ (dư thừa, cạnh này tạo chu trình
   trong đồ thị quan hệ); nếu chưa cùng nhóm thì giữ và hợp nhất nhóm (cạnh
   này là 1 nhánh mới trong cây khung — spanning tree). Kết quả: mỗi nhóm
   N line có cùng quan hệ chỉ còn đúng N-1 constraint (đủ để solver suy ra
   toàn bộ quan hệ bắc cầu, không dư).
   'coincident_endpoint' KHÔNG bắc cầu (2 điểm trùng nhau ở 2 đầu khác nhau
   của cùng 1 line không suy ra được điểm thứ 3) nên chỉ áp dụng bước (1)
   và (2).

4) 'perpendicular' tự nó KHÔNG bắc cầu (A⊥B và B⊥C => A//C chứ không phải
   A⊥C), NHƯNG dư thừa THEO NHÓM: nếu bước (3) đã gộp orientation của nhiều
   line vào cùng 1 "nhóm song song" (qua parallel/collinear), thì giữa 2
   NHÓM song song bất kỳ chỉ cần ĐÚNG 1 constraint perpendicular làm chứng
   — mọi cặp line khác thuộc 2 nhóm đó tự động vuông góc theo (parallel
   trong nhóm + perpendicular của cặp chứng), không cần constraint riêng.
   Đây chính là nguyên nhân THẬT đã gặp khi chạy demo_pipeline.py trên dữ
   liệu Phase 1 thật: 4 line cùng nhóm ngang + 2 line cùng nhóm dọc sinh ra
   8 constraint 'perpendicular' (mọi cặp ngang×dọc), nhưng chỉ cần 1 —
   đưa cả 8 vào solver khiến SolverSystem báo INCONSISTENT vì các cặp đo
   từ ảnh scan có sai số góc khác nhau (0.63° ở 1 line) xung đột nhau dưới
   ngưỡng hội tụ. Sau khi chỉ giữ 1 constraint/cặp-nhóm, solver ra 'okay'
   (xem test_constraint_pruning.py::test_perpendicular_redundant_across_group_pair_pruned
   và test tích hợp giống hệt tình huống này).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .models import Constraint

_DEFAULT_MIN_CONFIDENCE = 0.6
_TRANSITIVE_TYPES = {"parallel", "equal_length", "collinear"}


class _UnionFind:
    def __init__(self) -> None:
        self._parent: Dict[str, str] = {}

    def find(self, x: str) -> str:
        self._parent.setdefault(x, x)
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: str, b: str) -> bool:
        """Trả True nếu 2 phần tử TRƯỚC ĐÓ khác nhóm (hợp nhất thành công —
        cạnh này là cạnh cây khung, không dư thừa). Trả False nếu đã cùng
        nhóm từ trước (cạnh này tạo chu trình — dư thừa bắc cầu)."""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self._parent[ra] = rb
        return True


@dataclass
class PruneResult:
    kept: List[Constraint] = field(default_factory=list)
    dropped_low_confidence: List[str] = field(default_factory=list)  # constraint id
    dropped_duplicate: List[str] = field(default_factory=list)
    dropped_transitive_redundant: List[str] = field(default_factory=list)
    dropped_group_redundant: List[str] = field(default_factory=list)  # xem bước (4) trong docstring


def _pair_key(c: Constraint) -> Tuple[str, str, str]:
    a, b = c.primitive_ids
    return (c.type, a, b) if a <= b else (c.type, b, a)


def prune_constraints(
    constraints: List[Constraint],
    min_confidence: float = _DEFAULT_MIN_CONFIDENCE,
) -> PruneResult:
    """Trả về `PruneResult` với `kept` là danh sách constraint SẴN SÀNG đưa
    vào `constraint_solving.solve_constraints()`. Hàm này KHÔNG tự chạy
    solver — chỉ quyết định constraint nào dư thừa/yếu (tách trách nhiệm,
    xem docstring constraint_solving.py)."""

    result = PruneResult()

    # --- bước 1: ngưỡng tin cậy ---
    survivors: List[Constraint] = []
    for c in constraints:
        if c.confidence < min_confidence:
            result.dropped_low_confidence.append(c.id)
        else:
            survivors.append(c)

    # --- bước 2: khử trùng lặp tuyệt đối (cùng type + cùng cặp) ---
    best_by_key: Dict[Tuple[str, str, str], Constraint] = {}
    for c in survivors:
        key = _pair_key(c)
        existing = best_by_key.get(key)
        if existing is None:
            best_by_key[key] = c
        elif c.confidence > existing.confidence:
            result.dropped_duplicate.append(existing.id)
            best_by_key[key] = c
        else:
            result.dropped_duplicate.append(c.id)

    deduped = list(best_by_key.values())

    # --- bước 3: khử dư thừa bắc cầu (chỉ cho type có tính bắc cầu) ---
    non_transitive = [c for c in deduped if c.type not in _TRANSITIVE_TYPES]
    transitive = [c for c in deduped if c.type in _TRANSITIVE_TYPES]

    # nhóm riêng theo type — 'parallel' và 'equal_length' là 2 quan hệ độc
    # lập, không được dùng chung Union-Find (2 line có thể equal_length mà
    # không parallel và ngược lại)
    by_type: Dict[str, List[Constraint]] = {}
    for c in transitive:
        by_type.setdefault(c.type, []).append(c)

    for ctype, group in by_type.items():
        # ưu tiên giữ cạnh confidence cao trước khi xét dư thừa, để nếu
        # phải bỏ bớt trong 1 nhóm thì bỏ cạnh yếu hơn, không phải cạnh
        # mạnh hơn
        group_sorted = sorted(group, key=lambda c: c.confidence, reverse=True)
        uf = _UnionFind()
        for c in group_sorted:
            a, b = c.primitive_ids
            if uf.union(a, b):
                result.kept.append(c)
            else:
                result.dropped_transitive_redundant.append(c.id)

    # --- bước 4: khử dư thừa perpendicular theo cặp NHÓM song song ---
    # nhóm song song được suy ra từ chính các constraint 'parallel'/'collinear'
    # ĐÃ GIỮ ở bước 3 (không dùng lại constraint gốc trước prune — phải dùng
    # kết quả sau prune để nhóm phản ánh đúng những gì solver thật sự thấy)
    orientation_groups = _UnionFind()
    for c in result.kept:
        if c.type in ("parallel", "collinear"):
            a, b = c.primitive_ids
            orientation_groups.union(a, b)

    perpendicular = [c for c in non_transitive if c.type == "perpendicular"]
    other_non_transitive = [c for c in non_transitive if c.type != "perpendicular"]

    perpendicular_sorted = sorted(perpendicular, key=lambda c: c.confidence, reverse=True)
    seen_group_pairs: set = set()
    for c in perpendicular_sorted:
        a, b = c.primitive_ids
        ga, gb = orientation_groups.find(a), orientation_groups.find(b)
        pair_key = (ga, gb) if ga <= gb else (gb, ga)
        if pair_key in seen_group_pairs:
            result.dropped_group_redundant.append(c.id)
        else:
            seen_group_pairs.add(pair_key)
            result.kept.append(c)

    result.kept.extend(other_non_transitive)

    return result
