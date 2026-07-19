"""
run.py — CLI runner Phase 5 (Agent): chạy trên ảnh thật + Primitive/Semantic IR
JSON đã có sẵn (output của Phase 1 + Phase 2).

Pipeline: load ảnh + JSON → Phase 2 (prune + solve) → Phase 5 (Agent) → Phase 3 (DXF)

Bổ sung demo_pipeline.py vốn chỉ chạy ảnh synthetic + _StubVisionReader.
run.py load ảnh thật + IR thật từ file, dùng Vision API thật (nếu có key).

Chạy (từ thư mục cad_agent):
    python -m agent_lib.run --image path/to/ban_ve.png

Hoặc chỉ chạy Agent, bỏ qua DXF build:
    python -m agent_lib.run --image path/to/ban_ve.png --no-dxf

Dùng Claude Vision API thật (cần anthropic + ANTHROPIC_API_KEY):
    pip install anthropic
    python -m agent_lib.run --image path/to/ban_ve.png --real-vision

Đọc từ Primitive/Semantic IR khác:
    python -m agent_lib.run --image img.png --primitive-ir prim.json --semantic-ir sem.json
"""

from __future__ import annotations

import os
import sys

# đảm bảo import được package khi chạy từ thư mục cha (cad_agent/)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_DEFAULT_PRIMITIVE_IR = os.path.join(_REPO_ROOT, "demo_output", "primitive_ir_demo_output.json")
_DEFAULT_SEMANTIC_IR = os.path.join(_REPO_ROOT, "demo_output", "semantic_ir_demo_output.json")
_DEFAULT_OUTPUT_DIR = os.path.join(_REPO_ROOT, "demo_output")


def _configure_console_output() -> None:
    """Ensure Vietnamese CLI output works in legacy Windows terminals."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def run(
    image_path: str,
    primitive_ir_path: str = _DEFAULT_PRIMITIVE_IR,
    semantic_ir_path: str = _DEFAULT_SEMANTIC_IR,
    output_dir: str = _DEFAULT_OUTPUT_DIR,
    use_real_vision: bool = False,
    text_confidence_threshold: float = 0.5,
    part_confidence_threshold: float = 0.7,
    run_dxf: bool = True,
) -> int:
    """CLI runner Phase 5: load ảnh thật + 2 file JSON IR, chạy Agent,
    apply actions, lưu report (và tùy chọn build DXF).

    Parameters:
        image_path: đường dẫn ảnh bản vẽ gốc (PNG/JPG).
        primitive_ir_path: file JSON Primitive IR (output Phase 1).
        semantic_ir_path: file JSON Semantic IR (output Phase 2).
        output_dir: thư mục lưu output (AgentReport JSON, DXF).
        use_real_vision: dùng Claude Vision API thật cho module 1/2/3.
        text_confidence_threshold: ngưỡng confidence đẩy text sang rereader.
        part_confidence_threshold: ngưỡng confidence đẩy part sang classifier.
        run_dxf: chạy Phase 3 (build DXF + review) sau Agent.
    """
    _configure_console_output()

    import cv2

    print("=" * 60)
    print("CAD Agent — Phase 5 Runner (ảnh thật + IR thật)")
    print("Pipeline: Phase 2 (prune+solve) → Phase 5 → Phase 3 (DXF)")
    print("=" * 60)

    # ================================================================
    # 0. Kiểm tra file đầu vào
    # ================================================================
    for label, p in [("ảnh", image_path), ("Primitive IR", primitive_ir_path),
                     ("Semantic IR", semantic_ir_path)]:
        if not os.path.exists(p):
            print(f"LỖI: không thấy {label}: {p}")
            return 1

    os.makedirs(output_dir, exist_ok=True)

    # ================================================================
    # 1. Load ảnh gốc
    # ================================================================
    print(f"\n--- Load input ---")
    image = cv2.imread(image_path)
    if image is None:
        print(f"LỖI: không đọc được ảnh {image_path} (cv2.imread trả None)")
        return 1
    print(f"[image] {image.shape[1]}x{image.shape[0]} px <- {image_path}")

    # ================================================================
    # 2. Load Primitive IR + Semantic IR
    # ================================================================
    from semantic_ir_lib.io_utils import (
        load_primitive_ir_document, load_semantic_ir_document,
    )

    primitive_doc = load_primitive_ir_document(primitive_ir_path)
    print(f"[load] {len(primitive_doc.primitives)} primitives <- {os.path.basename(primitive_ir_path)}")

    semantic_doc = load_semantic_ir_document(semantic_ir_path)
    print(f"[load] {len(semantic_doc.parts)} parts, {len(semantic_doc.constraints)} constraints <- {os.path.basename(semantic_ir_path)}")

    # ================================================================
    # 3. Vision reader (optional — Claude Vision API)
    # ================================================================
    print(f"\n--- Vision ---")
    vision_reader = None
    if use_real_vision:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("[vision] --real-vision được yêu cầu nhưng thiếu ANTHROPIC_API_KEY "
                  "trong env -> Agent module 1/2/3 sẽ skip")
        else:
            try:
                from primitive_ir_lib.vision_client import make_vision_reader
                vision_reader = make_vision_reader()
                print("[vision] dùng Claude Vision API thật")
            except ImportError as exc:
                print(f"[vision] {exc} -> Agent module 1/2/3 sẽ skip")
    else:
        print("[vision] không dùng Vision API thật (--real-vision chưa bật) "
              "-> Agent module 1/2/3 sẽ skip")

    # ================================================================
    # 4. Phase 2 bổ sung: prune + solve (nếu chưa có solved primitives)
    # ================================================================
    print(f"\n--- Phase 2: Constraint Pruning + Solving ---")
    from semantic_ir_lib.constraint_pruning import prune_constraints

    pruned = prune_constraints(semantic_doc.constraints)
    print(f"[constraint-pruning] {len(semantic_doc.constraints)} -> {len(pruned.kept)} constraints")

    solve_result = None
    try:
        from semantic_ir_lib.constraint_solving import solve_constraints
        solve_result = solve_constraints(primitive_doc, pruned.kept)
        print(f"[constraint-solving] status={solve_result.status}")
    except ImportError as exc:
        print(f"[constraint-solving] BỎ QUA — {exc}")

    # ================================================================
    # 5. Phase 5: Agent
    # ================================================================
    print(f"\n--- Phase 5: Agent ---")
    from agent_lib.batch_agent import run_agent, apply_agent_report

    report = run_agent(
        primitive_doc=primitive_doc,
        semantic_doc=semantic_doc,
        image_bgr=image,
        solve_result=solve_result,
        vision_reader=vision_reader,
        text_confidence_threshold=text_confidence_threshold,
        part_confidence_threshold=part_confidence_threshold,
    )

    print(f"[agent] tasks={report.task_count}, actions={report.action_count}, "
          f"skipped={report.skipped_count}")
    for action in report.actions:
        if action.notes:
            print(f"    - {action.action_type}: {action.notes[:100]}")
        else:
            print(f"    - {action.action_type}")

    # Apply agent actions
    if report.action_count > 0:
        summary = apply_agent_report(
            primitive_doc, semantic_doc,
            primitive_doc.cross_validations, semantic_doc.constraints,
            report,
        )
        print(f"[agent-apply] {summary}")
    else:
        print("[agent-apply] không có action cần apply")

    # Save agent report
    from agent_lib.io_utils import save_document
    report_path = os.path.join(output_dir, "agent_report.json")
    save_document(report, report_path)
    print(f"[save] agent report -> {report_path}")

    # ================================================================
    # 6. Phase 3: DXF Builder + Reviewer (optional)
    # ================================================================
    if run_dxf:
        print(f"\n--- Phase 3: DXF Builder ---")
        try:
            from dxf_builder_lib.builder import build_dxf
            from dxf_builder_lib.reviewer import review_dxf

            out_path = os.path.join(output_dir, "agent_run_output.dxf")
            build_result = build_dxf(
                primitive_doc, out_path,
                semantic_doc=semantic_doc,
                solved_primitives=(
                    solve_result.solved_primitives
                    if solve_result and solve_result.status == "okay" else {}
                ),
                build_components=True,
            )
            print(f"[dxf-builder] {build_result.entity_count} entity -> {out_path}")
            print(f"[semantic-components] {build_result.component_count} linh kiện")

            review_result = review_dxf(build_result)
            if review_result.passed:
                print(f"[reviewer#1] OK — {review_result.checked_count} entity khớp tuyệt đối")
            else:
                print(f"[reviewer#1] LỖI ({len(review_result.mismatches)}):")
                for m in review_result.mismatches[:5]:
                    print(f"  - {m}")
        except ImportError as exc:
            print(f"[dxf-builder] BỎ QUA — {exc}")
    else:
        print(f"\n--- Phase 3: BỎ QUA (--no-dxf) ---")

    print("\n" + "=" * 60)
    print(">>> PHASE 5 RUN COMPLETE")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--image", required=True,
        help="Đường dẫn ảnh bản vẽ gốc (PNG/JPG)",
    )
    parser.add_argument(
        "--primitive-ir", default=_DEFAULT_PRIMITIVE_IR,
        help=f"File JSON Primitive IR (default: demo_output/primitive_ir_demo_output.json)",
    )
    parser.add_argument(
        "--semantic-ir", default=_DEFAULT_SEMANTIC_IR,
        help=f"File JSON Semantic IR (default: demo_output/semantic_ir_demo_output.json)",
    )
    parser.add_argument(
        "--output-dir", default=_DEFAULT_OUTPUT_DIR,
        help=f"Thư mục lưu output (default: demo_output/)",
    )
    parser.add_argument(
        "--real-vision", action="store_true",
        help="Dùng Claude Vision API thật (cần pip install anthropic + ANTHROPIC_API_KEY)",
    )
    parser.add_argument(
        "--text-threshold", type=float, default=0.5,
        help="Ngưỡng confidence đẩy text sang rereader (default: 0.5)",
    )
    parser.add_argument(
        "--part-threshold", type=float, default=0.7,
        help="Ngưỡng confidence đẩy part sang classifier (default: 0.7)",
    )
    parser.add_argument(
        "--no-dxf", action="store_true",
        help="Bỏ qua Phase 3 (DXF build), chỉ chạy Agent",
    )

    args = parser.parse_args()
    sys.exit(run(
        image_path=args.image,
        primitive_ir_path=args.primitive_ir,
        semantic_ir_path=args.semantic_ir,
        output_dir=args.output_dir,
        use_real_vision=args.real_vision,
        text_confidence_threshold=args.text_threshold,
        part_confidence_threshold=args.part_threshold,
        run_dxf=not args.no_dxf,
    ))
