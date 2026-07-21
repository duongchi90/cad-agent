# CAD Agent — Phase 1–5

Xem `CAD-Agent-Kien-Truc-v1_3.md` cho toàn bộ bối cảnh/kiến trúc dự án.
Các tài liệu benchmark/kế hoạch bổ sung nằm trong `docs/`:

- `docs/benchmarks/layer1-tick-mark-real-image-benchmark.md` — benchmark Lớp 1
  (tick-mark / witness-line detection) trên ảnh thật "TP-TL-A001/07/26": 3 ca
  (witness-line 1700, dim-chain 2760/1525, outer 5500), kết quả mong đợi,
  false-positive cần tránh và cách tái lập test.

5 package trong repo này:

- **`primitive_ir_lib/`** (Phase 1) — sinh Primitive IR từ ảnh scan/PDF:
  Geometry Extraction (OpenCV Canny+Hough), Text Extraction (Tesseract +
  Vision API thật, 3 tier), Cross-validation, Calibration (quy đổi px→mm,
  xem mục "Calibration (px → mm)" bên dưới). Xem `primitive_ir_lib/README.md`.
- **`semantic_ir_lib/`** (Phase 2) — sinh Semantic IR từ Primitive IR:
  Pattern Recognition (primitive → linh kiện: thanh ngang/dọc/xiên, lỗ
  bắt vít...) + Pattern Compound (ghép nhiều primitive thành 1 linh kiện
  phức hợp: khung_chu_nhat/gia_do/ban_le/diem_noi, tái dùng constraint đã
  detect, không đo lại hình học) + Constraint Detection (song song/vuông
  góc/bằng nhau/trùng điểm đầu/thẳng hàng) + Constraint Pruning (lọc
  constraint yếu/trùng/dư thừa bắc cầu) + Constraint Solving (tích hợp
  `python-solvespace` THẬT, "làm sạch" toạ độ line). Xem
  `semantic_ir_lib/README.md`.
- **`dxf_builder_lib/`** (Phase 3) — DXF Builder (`ezdxf` THẬT,
  build 1 lần từ Primitive IR + toạ độ đã solve + layer theo Semantic IR)
  + Reviewer #1 headless (đọc lại DXF, so khớp tuyệt đối theo handle, bắt
  lỗi dịch thuật của Builder) + Repair #1 headless (xoá/vẽ lại entity bị
  lỗi, review lại để xác nhận). Xem `dxf_builder_lib/README.md`.
- **`mcp_integration_lib/`** (Phase 4) — Reviewer #2 và Repair #2 qua
  AutoCAD MCP. Reviewer xác minh handle/type/layer và geometry khi MCP hỗ trợ
  `entity:get`; khi timeout, kiểm tra cấu trúc vẫn chạy và báo degraded rõ ràng.
- **`agent_lib/`** (Phase 5) — xử lý các case mơ hồ/confidence thấp sau
  Semantic IR: đọc lại text, phân loại lại part, giải quyết conflict
  text–geometry bằng Vision và đề xuất bỏ constraint bằng rule-based.
  Agent chỉ tạo `AgentReport` có audit trail; caller mới quyết định apply.

## Cài đặt

```bash
pip install opencv-python numpy pytesseract pillow --break-system-packages
# + cài binary tesseract-ocr của hệ điều hành (vd apt-get install tesseract-ocr tesseract-ocr-vie)

# optional — chỉ cần nếu dùng Claude Vision API thật (primitive_ir_lib/vision_client.py)
pip install anthropic --break-system-packages
export ANTHROPIC_API_KEY=sk-ant-...

# optional — chỉ cần cho bước Constraint Solving (semantic_ir_lib/constraint_solving.py)
pip install python-solvespace --break-system-packages

# optional — chỉ cần cho bước DXF Builder/Reviewer #1 (dxf_builder_lib/)
pip install ezdxf --break-system-packages
```

## Environment notes

- Install all runtime dependencies with `pip install -r requirements.txt`.
  This includes PyMuPDF (`fitz`) and pypdf, which are required for PDF input.
- Copy `.env.example` to `.env` only for optional Claude Vision calls. Keep
  `ANTHROPIC_API_KEY` out of Git; `.env` files are ignored by this repository.

## Chạy demo pipeline (Phase 1–5)

```bash
python3 -m primitive_ir_lib.demo_pipeline            # -> demo_output/primitive_ir_demo_output.json
python3 -m semantic_ir_lib.demo_pipeline             # đọc file trên -> Pattern Recognition -> Constraint
                                                       # Detection -> Pruning -> Solving -> demo_output/semantic_ir_demo_output.json
python3 -m dxf_builder_lib.demo_pipeline             # đọc 2 file trên -> DXF Builder -> Reviewer #1
                                                       # -> demo_output/cad_agent_demo_output.dxf
python3 -m agent_lib.demo_pipeline                    # Phase 1 -> 2 -> 5 -> 3 với Vision stub
python3 -m mcp_integration_lib.demo_pipeline           # Phase 4: Reviewer #2 -> Repair #2 (Fake MCP)

# hoặc dùng Claude Vision API thật cho Phase 1 thay vì mock:
python3 -m primitive_ir_lib.demo_pipeline --real-vision
python3 -m semantic_ir_lib.demo_pipeline
python3 -m dxf_builder_lib.demo_pipeline
python3 -m agent_lib.demo_pipeline
python3 -m mcp_integration_lib.demo_pipeline
```

Nếu chưa cài `python-solvespace`/`ezdxf`, các bước Solving/Builder tự bỏ
qua (in rõ lý do), không crash — phần còn lại của pipeline vẫn chạy đầy đủ.

## Chạy toàn bộ test

```bash
python3 -m primitive_ir_lib.tests.test_basic            # 17 test
python3 -m primitive_ir_lib.tests.test_vision_client     # 4 test
python3 -m semantic_ir_lib.tests.test_semantic_ir        # 24 test
python3 -m semantic_ir_lib.tests.test_constraint_pruning # 9 test (thuần logic, luôn chạy được)
python3 -m semantic_ir_lib.tests.test_constraint_solving # 7 test (cần python-solvespace, tự SKIP nếu chưa cài)
python3 -m dxf_builder_lib.tests.test_builder            # 5 test (1 luôn chạy được, 4 cần ezdxf, tự SKIP nếu chưa cài)
python3 -m dxf_builder_lib.tests.test_reviewer           # 5 test (1 luôn chạy được, 4 cần ezdxf, tự SKIP nếu chưa cài)
python3 -m dxf_builder_lib.tests.test_repair             # 5 test (1 luôn chạy được, 4 cần ezdxf, tự SKIP nếu chưa cài)
python3 -m unittest discover -s mcp_integration_lib/tests -v # 4 test Phase 4
python3 -m unittest discover -s agent_lib/tests -v        # 64 test Phase 5
```

57/57 test PASS (tính đến thời điểm cập nhật README này); 7 test trong
`test_constraint_solving.py` cần `python-solvespace` và 12 test trong
`dxf_builder_lib/tests/` cần `ezdxf` để chạy thật, tự SKIP (không fail)
nếu chưa cài các package optional này.

## Calibration (px → mm)

Toạ độ hình học đọc từ ảnh/PDF là pixel; DXF cần mm. `primitive_ir_lib/calibration.py`
và `calibration_registry.py` cung cấp 2 bước:

- **`auto_estimate_calibration(raw_texts, raw_lines, image_height_px)`** — tự động
  quét `raw_texts` tìm text đầu tiên có `semantic_role == "dimension_value"`, ghép
  với `RawLine` gần nhất (`find_nearest_line`, ngưỡng `max_distance_px`), dùng cặp
  đó làm mốc quy đổi (`method="known_dimension_reference"`, xem mục 10.3
  `CAD-Agent-Kien-Truc-v1_3.md`). Trả về `None` nếu không tìm được cặp phù hợp.
- **`calibration_registry.py`** — sổ ghi calibration đã xác nhận, mỗi bản ghi gắn
  `sha256` của đúng file ảnh/PDF đã dùng để đo. Có 2 trạng thái:
  - `verified` — người dùng đã tự kiểm tra, `get_verified_scale()` chấp nhận dùng.
  - `needs_verification` — dành cho kết quả từ `auto_estimate_calibration()`;
    `get_verified_scale()` **từ chối** trả scale cho tới khi ai đó đổi lại thành
    `verified`. Cố ý không tự tin dùng calibration suy đoán cho DXF sản xuất —
    đúng nguyên tắc "rule-based/deterministic trước, AI/suy đoán chỉ hỗ trợ" đã
    thống nhất trong dự án.

Còn thiếu: benchmark `auto_estimate_calibration()` trên ảnh scan thật (hiện chỉ có
unit test trên fixture tổng hợp) — cùng loại benchmark mà Phase 1 các bước
geometry/text extraction khác đã làm.

## Trạng thái

- **Phase 1**: hoàn chỉnh về code (geometry/text/table extraction,
  cross-validation, Vision API thật). Còn thiếu duy nhất: benchmark
  `vision_client.py` với ảnh scan thật + API key thật.
- **Phase 2**: Pattern Recognition + Pattern Compound (ghép linh kiện phức
  hợp: khung_chu_nhat/gia_do/ban_le/diem_noi, `semantic_ir_lib/pattern_compound.py`,
  17 test — xem mục 11.6 tài liệu kiến trúc) + Constraint Detection +
  Constraint Pruning + Constraint Solving (thật, `python-solvespace`) đã có
  code + test. Ngưỡng `coincident_endpoint` đã sửa (2.0mm → 5.0mm, dựa trên
  nhiễu Hough thật đo được — mục 11.6): demo pipeline giờ phát hiện được
  compound thật (`gia_do`) thay vì luôn rỗng. Constraint line-circle/
  circle-circle (`tangent`/`concentric`, `detect_circle_constraints()`) đã
  làm — xem mục 11.4. Còn thiếu: benchmark đầy đủ các ngưỡng (góc/bán
  kính/confidence/compound) trên ảnh scan thật domain khung xe — ngưỡng
  5.0mm mới benchmark trên 1 ảnh tổng hợp, và Constraint Solving
  (`python-solvespace`) hiện chỉ áp dụng `tangent`/`concentric` được ghi
  nhận nhưng chưa hỗ trợ solve (circle primitive chưa đưa vào solver, bị
  skip ở bước đó). Xem mục 11.6 tài liệu kiến trúc cho chi tiết.
- **Phase 3**: DXF Builder + Reviewer #1 + Repair #1 (cả 3 dùng `ezdxf`,
  tự SKIP khi chưa cài) đã có code + test. Còn thiếu: Semantic API riêng
  cho domain khung xương/thùng xe cải tạo, constraint arc, benchmark thật
   khi có `ezdxf`. Xem mục 12 tài liệu kiến trúc.
- **Portability**: `primitive_ir_lib/demo_pipeline.py` và
  `dxf_builder_lib/demo_pipeline.py` từng hardcode `output_dir`/đường dẫn
  input mặc định là `/home/claude/demo_output` (tuyệt đối, đặc thù 1
  sandbox) — trên máy/sandbox khác, 3 lệnh demo ở trên sẽ KHÔNG tự nối
  được với nhau (mỗi bước ghi/đọc nhầm chỗ, có thể âm thầm dùng lại fixture
  cũ đã commit sẵn trong repo thay vì output vừa chạy). Đã sửa: cả 3 file
  demo_pipeline.py (kể cả `semantic_ir_lib/`) giờ dùng path portable tính
  từ `__file__` (`primitive_ir_lib/demo_output/` cho Phase 1,
  `<repo_root>/demo_output/` cho Phase 2/3) — 3 lệnh chạy tuần tự ở trên
  giờ tự nối đúng trên mọi máy, không cần chỉnh `output_dir=` tay.
  Đã xác nhận bằng chứng cụ thể: fixture `primitive_ir_lib/demo_output/`
  và `demo_output/semantic_ir_demo_output.json` đã commit trước đó cực kỳ
  stale (từ trước khi có Pattern Compound/tangent-concentric/ngưỡng
  5.0mm) — 7 parts/17 constraints, không `gia_do`/`khung_chu_nhat`/
  `tangent` nào. Regenerate lại bằng đúng code hiện tại ra 37 parts/253
  constraints, có đủ `gia_do`/`khung_chu_nhat`/`tangent` — đã commit đè
  fixture mới này.
- **Phase 5**: hoàn chỉnh về code + 64 test: Text Re-reader, Part
  Re-classifier, Conflict Resolver, Constraint Advisor, `AgentReport` schema,
  apply có kiểm soát, demo và CLI chạy trên IR/ảnh thật. Vision thật là tuỳ
  chọn (cần `anthropic` + `ANTHROPIC_API_KEY`); khi không có, các module Vision
  skip an toàn còn advisor rule-based vẫn hoạt động.
- **Phase 4**: hoàn chỉnh mô-đun tích hợp MCP với interface `LiveMCPClient`,
  reviewer/repair theo handle, test Fake MCP và demo phục hồi lỗi. Để chạy với
  AutoCAD thật, inject callback `call_tool` của MCP runtime vào `LiveMCPClient`.
