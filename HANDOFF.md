# CAD Agent — handoff Phase 1–3

## Gói này gồm

- `primitive_ir_lib/`: Phase 1 — trích xuất và kiểm tra Primitive IR.
- `semantic_ir_lib/`: Phase 2 — nhận diện part, constraint detection/pruning/solving.
- `dxf_builder_lib/`: Phase 3 — DXF Builder, Reviewer #1, Repair #1 và Semantic Component API.
- `mcp_integration_lib/`: Phase 4 — adapter MCP, Reviewer #2 và Repair #2
  theo handle, có Fake MCP để test/demo không cần AutoCAD đang chạy.
- `agent_lib/`: Phase 5 — AgentReport/audit trail, Text Re-reader, Part
  Re-classifier, Conflict Resolver và Constraint Advisor. Agent chỉ đề xuất;
  caller dùng `apply_agent_report()` để áp dụng action đã duyệt.
- Schema, ví dụ IR, tài liệu kiến trúc và script kiểm tra ở thư mục gốc.

## Trạng thái tại thời điểm bàn giao (2026-07-17)

Bản Phase 3 hiện có Semantic Component API mở rộng: frame beam, bracket, panel round/rect, bracket L, hinge và node. DXF Builder lưu handle của primitive và component theo part.

Các lần thử bổ sung kiểm tra `INSERT` component trong Reviewer #1 chưa được áp dụng vào mã nguồn; mã trong gói là nguyên trạng dự án tại thời điểm xuất.

Phase 5 đã có 64 unit test, demo end-to-end và CLI `python -m agent_lib.run`.
CLI/demo tự cấu hình UTF-8 để chạy được trong PowerShell Windows dùng code page cũ.

Phase 4 đã được tích hợp với Phase 5. Chạy `python -m unittest discover -s
mcp_integration_lib/tests -v` để kiểm tra Reviewer #2/Repair #2; muốn nối
AutoCAD MCP thật, cung cấp callback runtime cho `LiveMCPClient`.

## Kiểm tra môi trường

Các test khi chạy bằng Python mặc định 3.7 dừng ở lỗi `typing.Literal` trong `primitive_ir_lib.models` (Literal thuộc Python 3.8+). Dùng Python 3.8+ (khuyến nghị 3.10+) và cài dependencies trước khi chạy.

```powershell
python -m pip install ezdxf
python -m unittest discover -s dxf_builder_lib\tests -v
```

Chạy lệnh từ thư mục `cad_agent` để các package Phase 1–5 cùng nằm trên import path.

## Việc nên làm tiếp

1. Mở rộng Reviewer #1 để round-trip kiểm tra `INSERT` component: handle, block name, layer, insert point, x/y/z scale, rotation và ATTRIB.
2. Sau đó thêm Repair #1 cho component INSERT hoặc tách rõ phần này sang Repair #2 MCP.
3. Phase 4: tích hợp AutoCAD MCP (file_ipc), Reviewer #2 visual/zoom và Repair #2 theo handle.
4. Duy trì ranh giới: Reviewer #1 chỉ kiểm tra chuyển đổi IR → DXF; lỗi nhận thức/pattern phải do Reviewer #2 đánh giá với ảnh gốc.

---

## Bàn giao bổ sung — Lớp 1 tick-mark detection, benchmark ảnh thật (19/07/2026)

Xem thêm `PHUONG_AN_BO_SUNG_LOP1_TICK_MARK.md` cho bối cảnh gốc của Lớp 1
(trước phiên làm việc này). Phiên này benchmark Lớp 1 trên đúng ảnh thật
"TP-TL-A001/07/26" (`2026-07-18_101706.png`, do người dùng cung cấp) và
implement P1 trong "Phương án tổng thể".

### Đã làm (đã test, đã xác nhận đúng)

- **Benchmark Lớp 1 trên ảnh thật**: phát hiện Lớp 1 (tick-mark chéo 45°,
  `detect_tick_mark_at_point`) không gây gộp nhầm trên ảnh thật, nhưng cũng
  KHÔNG cải thiện được gì—vì bản vẽ "TP-TL-A001/07/26" dùng witness-line
  DỌC (~90° với dim-line), không phải tick-mark chéo 45°. Chi tiết 3 case
  test (witness-line 1700, dim-chain 2760/1525, outer dim-line 5500) đã được
  ghi lại đầy đủ trong báo cáo benchmark
  [`docs/benchmarks/layer1-tick-mark-real-image-benchmark.md`](docs/benchmarks/layer1-tick-mark-real-image-benchmark.md)
  (kết quả mong đợi, false-positive cần tránh x=673, và cách tái lập test).

- **Xác định đúng vị trí ranh giới thật** giữa "2760" và "1525" trên ảnh
  thật: x≈776 (không phải x≈524 như nhận định sai ban đầu trong phiên —
  x=524 thực ra là điểm bắt đầu của cả chuỗi "2760", không phải ranh giới
  nội bộ). Xác nhận bằng tính tỷ lệ px/mm nhất quán (2760mm→253px,
  1525mm→140px, cùng scale ~0.0917px/mm) và bằng pixel thật (witness-line
  liên tục từ y=340 đến y=357, chạm trực tiếp dim-line tại y=356).

- **Implement `_perpendicular_witness_at_point()`** trong
  `primitive_ir_lib/tick_mark_detection.py` — hàm MỚI (khác
  `detect_tick_mark_at_point` vốn dò tick chéo 45°), dùng column-projection
  dò witness-line VUÔNG GÓC. Đã qua 2 vòng sửa sau khi test trên toạ độ
  thật (x=776) và toạ độ false-positive đã biết (x=673):
  - Bản đầu (tiêu chí "chạm N hàng đầu + đủ tổng số hàng tối cả cửa sổ")
    vừa bỏ sót witness-line thật vừa bắt nhầm text/hatch rời rạc.
  - Bản sửa (hiện tại): đếm CHUỖI pixel tối LIÊN TỤC từ dim-line ra, cho
    phép standoff nhỏ ở đầu (`leading_gap_max_px`) nhưng không cho phép hở
    giữa chuỗi (`run_gap_tol_px`). Đã verify đúng cả ở x=776 (True) và
    x=673 (False).

- **Implement `find_internal_boundary_offsets()` và
  `split_raw_line_at_tick_marks()`** trong cùng file — quét dọc 1 RawLine,
  gọi `_perpendicular_witness_at_point()` tại từng điểm, cluster các vị trí
  liền kề, trả về danh sách RawLine đã tách tại ranh giới nội bộ. Verify
  trên ảnh thật: tách đúng line bị Hough fuse (661,355)→(838,355) thành 2
  đoạn tại x=777; KHÔNG tách nhầm đoạn kỹ thuật "1700" (dọc, không có ranh
  giới nội bộ nào).

- **8 test mới** trong `primitive_ir_lib/tests/test_tick_mark_detection.py`
  cho 2 hàm trên, dùng fixture tổng hợp mô phỏng đúng 2 lỗi học được từ ảnh
  thật (witness-line chạm trực tiếp dim-line; text rời rạc không được nhận
  nhầm; standoff gap nhỏ vẫn detect được; không tách nhầm khi không có ranh
  giới; không tách khi `image_bgr=None`; không tách ranh giới quá sát đầu
  mút). Tất cả pass độc lập (`pytest primitive_ir_lib/tests/test_tick_mark_detection.py`).

### Đang làm dở — CHƯA xong, có hồi quy chưa xử lý

- **File đang sửa: `primitive_ir_lib/line_merging.py`**. Đã thêm tham số
  `split_internal_tick_marks: bool = True` vào `merge_collinear_lines()` và
  gọi `split_raw_line_at_tick_marks()` cho từng `RawLine` đầu vào TRƯỚC bước
  union-find/gộp — nhưng việc wiring này **CHƯA hoàn tất và đang gây hồi
  quy**:

  ```
  pytest primitive_ir_lib/tests/ -q
  → 1 failed, 42 passed
  FAILED test_line_merging.py::test_tick_mark_blocks_merge_even_without_any_blocking_text
    assert len(merged) == 2   (mong đợi 2 line)
    → thực tế ra 4 line (['rawline-split-...'] x4)
  ```

  Nguyên nhân (chưa sửa, chỉ mới xác định qua log lỗi): test đó dựng 1 ảnh
  tổng hợp có nét chéo tick-mark thật ở giữa 1 line dài — nhưng vì
  `split_internal_tick_marks=True` mặc định BẬT và fixture của test đó có
  witness-line/nét dọc mà `_perpendicular_witness_at_point` cũng bắt được
  (không chỉ tick chéo 45° như test đó dự tính), line bị tách thành 4 mảnh
  thay vì gộp lại đúng 2 theo kỳ vọng ban đầu của test. Cần xem lại: (a)
  fixture của test cũ có vô tình chứa witness-line vuông góc không mong
  muốn, hay (b) `split_raw_line_at_tick_marks` đang chạy quá nhạy trên
  chính fixture đó, hay (c) thứ tự gọi Lớp 1 (chéo) / Lớp mới (vuông góc)
  trong `merge_collinear_lines` cần tách bạch rõ hơn thay vì cùng một cờ
  `split_internal_tick_marks`.

- **CHƯA chạy lại toàn bộ pipeline trên ảnh thật** sau khi wiring — tức là
  P1 CHƯA được xác nhận đầu-cuối là sửa đúng bug gốc (dim-chain "2760"+
  "1525" gộp nhầm) khi gọi qua `merge_collinear_lines()` đầy đủ (kèm
  `blocking_texts` thật, `cross_validate()`, v.v.) — mới chỉ verify hàm
  `split_raw_line_at_tick_marks()` đơn lẻ (không qua `merge_collinear_lines`).

- Docstring đầu `line_merging.py` (mô tả "Lớp 1 tick-mark", "Lớp 2
  text-anchor") CHƯA được cập nhật để nhắc tới bước split-nội-bộ mới này —
  hiện chỉ có docstring của riêng tham số `split_internal_tick_marks` là
  mới.

### Việc tiếp theo (theo thứ tự)

1. **Sửa hồi quy** ở `test_tick_mark_blocks_merge_even_without_any_blocking_text`
   trong `primitive_ir_lib/tests/test_line_merging.py` — debug xem fixture
   của test đó có vô tình khớp điều kiện witness-line vuông góc hay không,
   rồi quyết định: sửa fixture (nếu nó thật sự chứa cấu trúc vuông góc
   ngoài ý muốn) hay sửa ngưỡng/logic trong
   `_perpendicular_witness_at_point`/`find_internal_boundary_offsets`.
2. Sau khi hết hồi quy, chạy lại **toàn bộ** `merge_collinear_lines()`
   (không chỉ `split_raw_line_at_tick_marks()` đơn lẻ) trên ca thật
   "2760"/"1525" của ảnh `2026-07-18_101706.png` để xác nhận pipeline đầu
   cuối tách đúng, có dùng `blocking_texts` thật (OCR Tesseract) song song.
3. Cập nhật docstring đầu `line_merging.py` cho khớp thay đổi.
4. ~~Ghi lại benchmark 3 case (witness-line 1700 / dim-chain 2760-1525 /
   outer 5500) thành file report riêng~~ — **ĐÃ LÀM** (phiên docs/layer1-real-image-benchmark):
   báo cáo đầy đủ ở
   [`docs/benchmarks/layer1-tick-mark-real-image-benchmark.md`](docs/benchmarks/layer1-tick-mark-real-image-benchmark.md)
   (kết quả mong đợi, false-positive x=673 cần tránh, ngưỡng tham số dùng,
   và kịch bản tái lập test bằng ảnh thật + test tự động hoá offline).
5. P2 (chưa bắt đầu): mở rộng `detect_tick_mark_at_point` cho tick chéo 45°
   dùng `HoughLines` thay `HoughLinesP` để bắt witness-line ngắn tốt hơn —
   xuất phát từ 1 proof-of-concept trong phiên chat, chưa đưa vào code.
6. P3 (chưa bắt đầu): tăng `text_block_lateral_px` mặc định từ 15px lên
   25px trong `merge_collinear_lines()` — thay đổi nhỏ, rủi ro thấp, có
   thể làm độc lập bất kỳ lúc nào.
