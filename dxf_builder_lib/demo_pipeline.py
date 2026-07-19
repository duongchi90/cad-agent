"""
demo_pipeline.py — chạy thử Phase 3 (DXF Builder + Reviewer #1 headless)
trên chính output THẬT đã lưu của Phase 1 (`primitive_ir_demo_output.json`)
+ Phase 2 (`semantic_ir_demo_output.json`) — đọc 2 file JSON độc lập, đúng
nguyên tắc "hợp đồng dữ liệu" đã áp dụng xuyên suốt dự án (Phase 2 không
cần chạy lại Phase 1 trong cùng tiến trình, Phase 3 cũng vậy với Phase 1+2).

`semantic_ir_demo_output.json` lưu constraints[] CHƯA PRUNE (Constraint
Detection thô — xem semantic_ir_lib/demo_pipeline.py, pruning/solving chỉ
chạy trong bộ nhớ ở đó, không lưu lại thành file riêng). Demo này tự chạy
lại `prune_constraints()` + `solve_constraints()` từ constraints[] đã đọc
được, để có toạ độ "đã làm sạch" trước khi build DXF — không phá vỡ tính
độc lập giữa các phase (không cần Phase 2 lưu thêm 1 file trung gian riêng
chỉ để phục vụ Phase 3).

Nếu chưa cài `ezdxf`, demo dừng ở bước load/prune/solve và in rõ lý do bỏ
qua Builder/Reviewer, không crash.

Chạy:
    python3 -m primitive_ir_lib.demo_pipeline
    python3 -m semantic_ir_lib.demo_pipeline
    python3 -m dxf_builder_lib.demo_pipeline
"""

from __future__ import annotations

import os

from semantic_ir_lib.constraint_pruning import prune_constraints
from semantic_ir_lib.io_utils import load_primitive_ir_document, load_semantic_ir_document

_DEFAULT_PRIMITIVE_IR_PATH = "/home/claude/demo_output/primitive_ir_demo_output.json"
_DEFAULT_SEMANTIC_IR_PATH = "/home/claude/demo_output/semantic_ir_demo_output.json"


def run_demo(
    primitive_ir_path: str = _DEFAULT_PRIMITIVE_IR_PATH,
    semantic_ir_path: str = _DEFAULT_SEMANTIC_IR_PATH,
    output_dir: str = "/home/claude/demo_output",
) -> dict:
    for p in (primitive_ir_path, semantic_ir_path):
        if not os.path.exists(p):
            raise FileNotFoundError(
                f"Không thấy {p} — chạy `python3 -m primitive_ir_lib.demo_pipeline` "
                f"và `python3 -m semantic_ir_lib.demo_pipeline` trước để sinh file này."
            )
    os.makedirs(output_dir, exist_ok=True)

    primitive_doc = load_primitive_ir_document(primitive_ir_path)
    semantic_doc = load_semantic_ir_document(semantic_ir_path)
    print(
        f"[load] {len(primitive_doc.primitives)} primitives từ {primitive_ir_path}, "
        f"{len(semantic_doc.parts)} parts + {len(semantic_doc.constraints)} constraints "
        f"từ {semantic_ir_path}"
    )

    pruned = prune_constraints(semantic_doc.constraints)
    print(f"[constraint-pruning] {len(semantic_doc.constraints)} -> {len(pruned.kept)} constraints")

    solved_primitives = {}
    try:
        from semantic_ir_lib.constraint_solving import solve_constraints
        solve_result = solve_constraints(primitive_doc, pruned.kept)
        print(
            f"[constraint-solving] status={solve_result.status} "
            f"applied={solve_result.applied_constraint_count}"
        )
        if solve_result.status == "okay":
            solved_primitives = solve_result.solved_primitives
        else:
            print("[constraint-solving] status khác 'okay' -> DXF Builder dùng toạ độ đo thô (không override)")
    except ImportError as exc:
        print(f"[constraint-solving] BỎ QUA — {exc}")

    from .builder import build_dxf

    out_path = os.path.join(output_dir, "cad_agent_demo_output.dxf")
    try:
        build_result = build_dxf(
            primitive_doc, out_path, semantic_doc=semantic_doc, solved_primitives=solved_primitives,
            build_components=True,
        )
    except ImportError as exc:
        print(f"[dxf-builder] BỎ QUA — {exc}")
        return {"solved_primitives": len(solved_primitives)}

    print(
        f"[dxf-builder] đã build {build_result.entity_count} entity -> {out_path} "
        f"(bỏ qua {len(build_result.skipped_primitive_ids)} primitive thiếu geometry/text_data)"
    )
    for pid, layer in build_result.layer_by_primitive_id.items():
        print(f"    - {pid}: layer={layer} handle={build_result.handle_by_primitive_id[pid]}")

    print(
        f"[semantic-components] đã chèn {build_result.component_count} linh kiện "
        f"(bỏ qua {len(build_result.skipped_part_ids)} part chưa hỗ trợ được)"
    )
    for part_id, comp_type in build_result.component_type_by_part_id.items():
        print(f"    - {part_id}: {comp_type} handle={build_result.component_handle_by_part_id[part_id]}")
    for part_id, reason in build_result.skipped_part_reasons.items():
        print(f"    - SKIP {part_id}: {reason}")

    from .reviewer import review_dxf
    review_result = review_dxf(build_result)
    if review_result.passed:
        print(f"[reviewer#1] OK — {review_result.checked_count} entity khớp tuyệt đối sau khi đọc lại DXF")
    else:
        print(f"[reviewer#1] LỖI DỊCH THUẬT ({len(review_result.mismatches)}):")
        for m in review_result.mismatches:
            print("   -", m)

        # --- Repair #1: xoá/vẽ lại entity bị lỗi dịch thuật rồi review lại --
        from .repair import repair_dxf
        repair_result = repair_dxf(build_result, review_result.mismatches)
        print(
            f"[repair#1] sửa {repair_result.repaired_count} entity "
            f"(bỏ qua {repair_result.skipped_count} không sửa được):"
        )
        for d in repair_result.details:
            print(f"    - {d}")

        review_after = review_dxf(build_result)
        if review_after.passed:
            print(f"[reviewer#1 sau repair] OK — {review_after.checked_count} entity khớp tuyệt đối")
        else:
            print(f"[reviewer#1 sau repair] VẪN CÒN LỖI ({len(review_after.mismatches)}):")
            for m in review_after.mismatches:
                print("   -", m)
        review_result = review_after

    return {
        "dxf_path": out_path,
        "entity_count": build_result.entity_count,
        "reviewer_passed": review_result.passed,
    }


if __name__ == "__main__":
    run_demo()
