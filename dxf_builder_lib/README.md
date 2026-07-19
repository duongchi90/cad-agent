# dxf_builder_lib

Code Phase 3 của dự án CAD Agent (xem `CAD-Agent-Kien-Truc-v1_3.md`
mục 2 sơ đồ pipeline + mục 6 roadmap): **DXF Builder** (build 1 lần bằng
`ezdxf`, không vẽ từng entity qua MCP) + **Reviewer #1 headless** (IR ⇄ DXF,
deterministic, chỉ bắt lỗi dịch thuật của Builder — không bắt lỗi nhận thức,
việc đó để Reviewer #2 visual+zoom ở Phase 4) + **Repair #1 headless** (xoá/
vẽ lại entity bị lỗi dịch thuật theo handle, rồi chạy lại Reviewer #1 để xác
nhận).

## Cấu trúc module

| File | Vai trò |
|---|---|
| `builder.py` | `build_dxf()` — build file `.dxf` thật từ `PrimitiveIRDocument` (Phase 1), có thể ghi đè toạ độ line bằng `solved_primitives` (Phase 2, `constraint_solving.solve_constraints()`) và suy layer theo `part_type` từ `SemanticIRDocument` (Phase 2) nếu có. Ghi `handle` CAD thật ngược lại lên chính `Primitive.handle`. |
| `reviewer.py` | `review_dxf()` — Reviewer #1: đọc lại file `.dxf` vừa build bằng `ezdxf.readfile()`, tra theo `handle`, so khớp tuyệt đối với `written_geometry_by_primitive_id` mà `builder.py` trả về. Bắt lỗi round-trip/serialize, không phán đoán Pattern Recognition đúng/sai. |
| `repair.py` | `repair_dxf()` — Repair #1: nhận `mismatches` từ `review_dxf()`, xoá entity bị lỗi theo handle và vẽ lại đúng từ `BuildResult.written_geometry_by_primitive_id`. Ghi đè vào đúng file gốc; caller chạy lại `review_dxf()` sau để xác nhận hết lỗi. |
| `demo_pipeline.py` | Đọc `primitive_ir_demo_output.json` (Phase 1) + `semantic_ir_demo_output.json` (Phase 2) — 2 file độc lập, không cần chạy lại Phase 1/2 trong cùng tiến trình — tự chạy lại `prune_constraints()` + `solve_constraints()` để có toạ độ sạch, rồi build DXF → Reviewer #1 → Repair #1 (nếu có lỗi) → Reviewer #1 lần 2. |

## Cài đặt

```bash
pip install ezdxf --break-system-packages   # optional, cần cho build_dxf()/review_dxf()/repair_dxf() thật
```

Nếu chưa cài `ezdxf`, `build_dxf()`/`review_dxf()`/`repair_dxf()` raise `ImportError` với
hướng dẫn cài đặt rõ ràng — không import ngầm, không crash im lặng (cùng
chiến lược lazy-import đã dùng cho `vision_client.py`/`constraint_solving.py`).

## Chạy demo

```bash
python3 -m primitive_ir_lib.demo_pipeline
python3 -m semantic_ir_lib.demo_pipeline
python3 -m dxf_builder_lib.demo_pipeline    # -> demo_output/cad_agent_demo_output.dxf
```

## Chạy test

```bash
python3 -m dxf_builder_lib.tests.test_builder    # 5 test — 1 luôn chạy được, 4 cần ezdxf (tự SKIP nếu chưa cài)
python3 -m dxf_builder_lib.tests.test_reviewer   # 5 test — 1 luôn chạy được, 4 cần ezdxf (tự SKIP nếu chưa cài)
python3 -m dxf_builder_lib.tests.test_repair     # 5 test — 1 luôn chạy được, 4 cần ezdxf (tự SKIP nếu chưa cài)
```

- `test_builder.py`: raise ImportError rõ ràng khi chưa cài ezdxf; build line/circle/text gán handle đúng + ghi ngược lên `Primitive.handle`; layer suy đúng theo `part_type`; `solved_primitives` ghi đè toạ độ thô; primitive thiếu geometry bị skip chứ không crash cả file.
- `test_reviewer.py`: raise ImportError rõ ràng; review pass trên file build đúng; bắt được handle không tìm thấy, toạ độ lệch sau khi file bị sửa tay, và layer ghi nhận sai so với layer thật trong file.
- `test_repair.py`: raise ImportError rõ ràng; repair với mismatches rỗng không làm gì; sửa đúng mismatch toạ độ LINE; sửa đúng mismatch layer CIRCLE; sửa nhiều entity độc lập — tất cả xác nhận bằng `review_dxf()` lần 2 sau repair (review pass = hết lỗi).

## Việc CHƯA làm

- Semantic API cho domain khung xương/thùng xe cải tạo (vd `frame_insert_beam`, `panel_insert`...) — hiện `build_dxf()` chỉ vẽ hình học thô (line/circle/arc/text), chưa có khái niệm "linh kiện" ở tầng DXF.
- Xử lý `arc` — `constraint_detection.py`/`constraint_solving.py` chưa hỗ trợ constraint cho arc, nên arc trong Primitive IR được vẽ nguyên trạng (không qua Constraint Solving) nếu có.
- Tích hợp AutoCAD MCP thật (`drawing_open`) — Phase 4, xem mục 6 tài liệu kiến trúc.
