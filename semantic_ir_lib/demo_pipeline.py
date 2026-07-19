"""
demo_pipeline.py — chạy thử TOÀN BỘ Phase 2 (Pattern Recognition ->
Constraint Detection -> Constraint Pruning -> Constraint Solving) trên
chính output THẬT đã lưu của demo Phase 1
(`primitive_ir_lib/demo_output/primitive_ir_demo_output.json`) — không
dùng dữ liệu tổng hợp riêng, để chứng minh 2 lib nối được với nhau qua
đúng 1 file JSON trung gian (đúng vai trò "hợp đồng dữ liệu" của Primitive
IR đã ghi ở mục 10.1 tài liệu kiến trúc).

Bước Solving CẦN `python-solvespace` (optional dependency) — nếu chưa cài,
demo vẫn chạy hết Pattern Recognition/Constraint Detection/Pruning, in rõ
lý do bỏ qua Solving, KHÔNG crash (cùng chiến lược lazy-import/graceful-skip
đã dùng cho vision_client.py).

Chạy:
    python3 -m primitive_ir_lib.demo_pipeline   # sinh file JSON Phase 1 trước
    python3 -m semantic_ir_lib.demo_pipeline    # rồi mới chạy được demo này
"""

from __future__ import annotations

import os

from .assemble import build_semantic_document
from .constraint_pruning import prune_constraints
from .io_utils import load_primitive_ir_document, save_document
from .validator import validate_document

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_PRIMITIVE_IR_PATH = os.path.join(_REPO_ROOT, "primitive_ir_lib", "demo_output", "primitive_ir_demo_output.json")


def run_demo(
    primitive_ir_path: str = _DEFAULT_PRIMITIVE_IR_PATH,
    output_dir: str = os.path.join(_REPO_ROOT, "demo_output"),
) -> dict:
    if not os.path.exists(primitive_ir_path):
        raise FileNotFoundError(
            f"Không thấy {primitive_ir_path} — chạy "
            f"`python3 -m primitive_ir_lib.demo_pipeline` trước để sinh file này."
        )
    os.makedirs(output_dir, exist_ok=True)

    primitive_doc = load_primitive_ir_document(primitive_ir_path)
    print(f"[load] đọc {len(primitive_doc.primitives)} primitives từ {primitive_ir_path}")

    semantic_doc = build_semantic_document(
        primitive_doc,
        primitive_ir_file_name=os.path.basename(primitive_ir_path),
    )
    line_count = sum(1 for p in primitive_doc.primitives if p.type == "line")
    circle_count = sum(1 for p in primitive_doc.primitives if p.type == "circle")
    print(f"[pattern-recognition] {line_count} line + {circle_count} circle -> "
          f"{len(semantic_doc.parts)} parts")
    for p in semantic_doc.parts:
        gs = p.geometry_summary
        detail = (f"length={gs.length_mm}mm orientation={gs.orientation_deg}°"
                  if gs and gs.length_mm is not None
                  else f"radius={gs.radius_mm}mm" if gs else "")
        print(f"    - {p.part_type} (conf={p.confidence}) primitive={p.primitive_ids[0]} {detail}")

    print(f"[constraint-detection] {len(semantic_doc.constraints)} constraints")
    for c in semantic_doc.constraints:
        print(f"    - {c.type} (conf={c.confidence}) giữa {c.primitive_ids} measured={c.measured}")

    # --- Constraint Pruning: bỏ constraint yếu/trùng/dư thừa bắc cầu trước
    # khi đưa vào solver thật (xem docstring constraint_pruning.py) ---
    pruned = prune_constraints(semantic_doc.constraints)
    print(
        f"[constraint-pruning] {len(semantic_doc.constraints)} -> {len(pruned.kept)} constraints "
        f"(bỏ {len(pruned.dropped_low_confidence)} confidence thấp, "
        f"{len(pruned.dropped_duplicate)} trùng lặp, "
        f"{len(pruned.dropped_transitive_redundant)} dư thừa bắc cầu, "
        f"{len(pruned.dropped_group_redundant)} dư thừa theo nhóm)"
    )
    for c in pruned.kept:
        print(f"    - {c.type} (conf={c.confidence}) giữa {c.primitive_ids}")

    # --- Constraint Solving: "làm sạch" toạ độ line theo constraint đã giữ.
    # Optional dependency (python-solvespace) -- bỏ qua nếu chưa cài, không
    # crash demo (cùng chiến lược lazy-import/graceful-skip của vision_client.py) ---
    try:
        from .constraint_solving import solve_constraints
        solve_result = solve_constraints(primitive_doc, pruned.kept)
    except ImportError as exc:
        solve_result = None
        print(f"[constraint-solving] BỎ QUA — {exc}")

    if solve_result is not None:
        print(
            f"[constraint-solving] status={solve_result.status} dof={solve_result.dof} "
            f"applied={solve_result.applied_constraint_count} "
            f"skipped={len(solve_result.skipped_constraints)}"
        )
        for pid, sp in solve_result.solved_primitives.items():
            print(
                f"    - {pid}: ({sp.start.x}, {sp.start.y}) -> ({sp.end.x}, {sp.end.y}) "
                f"displacement={sp.displacement_mm}mm"
            )

    doc_dict = semantic_doc.to_dict()
    known_ids = {p.id for p in primitive_doc.primitives}
    errors = validate_document(doc_dict, known_primitive_ids=known_ids)
    if errors:
        print("[validate] LỖI SCHEMA:")
        for e in errors:
            print("   -", e)
    else:
        print("[validate] OK — document khớp các ràng buộc chính của semantic_ir.schema.json")

    out_path = os.path.join(output_dir, "semantic_ir_demo_output.json")
    save_document(semantic_doc, out_path)
    print(f"[save] đã lưu {out_path} ({len(semantic_doc.parts)} parts, "
          f"{len(semantic_doc.constraints)} constraints)")

    return doc_dict


if __name__ == "__main__":
    run_demo()
