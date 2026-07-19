# semantic_ir_lib

Code Phase 2 của dự án CAD Agent (xem `CAD-Agent-Kien-Truc-v1_3.md` mục 11):
sinh **Semantic IR** đúng `semantic_ir.schema.json` từ 1 `PrimitiveIRDocument`
(output Phase 1) — Pattern Recognition + Constraint Detection bước đầu.

## Cấu trúc module

| File | Vai trò |
|---|---|
| `models.py` | Dataclass khớp 1-1 `semantic_ir.schema.json`. |
| `pattern_recognition.py` | `build_parts_from_primitives()` — suy `part_type` (thanh_ngang/thanh_doc/thanh_xien/lo_bat_vit/duong_vien_tron) từ hình học 1 primitive đơn lẻ. CỐ Ý không ghép nhiều primitive thành 1 linh kiện phức hợp (xem mục 11.2). |
| `constraint_detection.py` | `detect_constraints()` — so từng cặp line, phát hiện parallel/perpendicular/equal_length/coincident_endpoint/collinear bằng công thức hình học thuần. |
| `assemble.py` | `build_semantic_document()` — ghép Pattern Recognition + Constraint Detection thành `SemanticIRDocument` hoàn chỉnh. |
| `validator.py` | Kiểm tra nhẹ theo schema + phát hiện `primitive_ids` tham chiếu treo (dangling reference) đối chiếu ngược Primitive IR gốc. |
| `io_utils.py` | Lưu Semantic IR + **đọc lại** 1 file JSON Primitive IR đã lưu (Phase 2 chạy độc lập với Phase 1, không cần nối liền script). |
| `constraint_pruning.py` | `prune_constraints()` — lọc constraint yếu (confidence thấp), trùng lặp, và **dư thừa bắc cầu** (parallel/equal_length/collinear qua Union-Find) + **dư thừa theo nhóm** (perpendicular dư giữa 2 nhóm song song đã biết) trước khi đưa vào solver. |
| `constraint_solving.py` | `solve_constraints()` — tích hợp `python-solvespace` THẬT, "làm sạch" toạ độ line theo constraint đã phát hiện. Tự thử nhiều thứ tự áp constraint để tránh `DIDNT_CONVERGE` do Newton-Raphson nhạy thứ tự (xem docstring trong file). |
| `demo_pipeline.py` | Chạy toàn bộ Phase 2 (Pattern Recognition → Constraint Detection → Pruning → Solving) trên chính output THẬT của demo Phase 1. |

## Chạy demo

```bash
pip install python-solvespace --break-system-packages   # optional, cần cho bước Constraint Solving
python3 -m primitive_ir_lib.demo_pipeline   # sinh demo_output/primitive_ir_demo_output.json trước
python3 -m semantic_ir_lib.demo_pipeline    # đọc file đó, chạy Pattern Recognition -> Constraint Detection -> Pruning -> Solving
```

Nếu chưa cài `python-solvespace`, demo vẫn chạy hết Pattern Recognition/Constraint
Detection/Pruning và bỏ qua bước Solving (in rõ lý do), không crash.

## Chạy test

```bash
python3 -m semantic_ir_lib.tests.test_semantic_ir
python3 -m semantic_ir_lib.tests.test_constraint_pruning
python3 -m semantic_ir_lib.tests.test_constraint_solving   # cần python-solvespace, tự SKIP nếu chưa cài
```

- `test_semantic_ir.py` — 15 test: pattern_recognition (7 — phân loại ngang/dọc/xiên/lỗ vít/đường viền tròn/bỏ qua text-arc/line suy biến), constraint_detection (6 — 5 loại quan hệ + case reject sai type), validator (2 — pass + bắt dangling reference).
- `test_constraint_pruning.py` — 9 test thuần logic (luôn chạy được, không cần solvespace): lọc confidence thấp, khử trùng lặp, khử dư thừa bắc cầu, khử dư thừa perpendicular theo nhóm, và 1 test tích hợp prune→solve thật.
- `test_constraint_solving.py` — 7 test THẬT với solvespace (parallel/perpendicular/equal_length/coincident_endpoint/collinear + case bỏ qua constraint không hỗ trợ/thiếu primitive).

## Việc CHƯA làm (xem mục 11.4 tài liệu kiến trúc)

- Ghép nhiều primitive thành 1 part phức hợp (bản lề, giá đỡ, mối hàn) — cần rule hình dạng hoặc Vision-assisted.
- Constraint line-circle/circle-circle (tangent, concentric) — hiện `constraint_detection.py` chỉ xét line-line, `constraint_solving.py` chỉ nhận primitive type line.
- Benchmark ngưỡng góc/bán kính/confidence trên ảnh scan thật (hiện là giá trị đề xuất ban đầu, bao gồm `min_confidence=0.6` mặc định của pruning).
- Xuất `solved_primitives` sang DXF Builder (ezdxf) — bước kế tiếp trong pipeline theo mục 2 tài liệu kiến trúc, chưa bắt đầu.
