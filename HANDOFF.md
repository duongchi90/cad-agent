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
  KHÔNG cải thiện được gì — vì bản vẽ "TP-TL-A001/07/26" dùng witness-line
  DỌC (~90° với dim-line), không phải tick-mark chéo 45°. Chi tiết 3 case
  test (witness-line 1700, dim-chain 2760/1525, outer dim-line 5500) nằm
  trong lịch sử chat, chưa được ghi thành file riêng — **cần chép lại vào
  một file benchmark report nếu muốn giữ lại lâu dài** (xem "Việc tiếp
  theo" bên dưới, mục 4).

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

### Hồi quy đã sửa (19/07/2026, nhánh `fix/tick-mark-witness-line-regression`)

- **Nguyên nhân xác nhận bằng debug trực tiếp (không chỉ đoán từ log)**:
  `_perpendicular_witness_at_point()` (dùng bởi `find_internal_boundary_offsets`/
  `split_raw_line_at_tick_marks`, được gọi TRƯỚC union-find trong
  `merge_collinear_lines` khi `split_internal_tick_marks=True`) chỉ hỏi "có
  pixel tối trong cửa sổ ±col_half_px hay không" ở từng hàng quét dọc theo
  pháp tuyến — KHÔNG lọc theo góc. Khi 1 tick-mark CHÉO ~45° (tín hiệu của
  Lớp 1, `detect_tick_mark_at_point`) nằm gần điểm đang quét, nó vẫn tạo ra
  1 chuỗi pixel tối liên tục hợp lệ theo tiêu chí cũ (chỉ khác là vị trí cột
  "trôi dạt" dần qua từng hàng — đặc trưng hình học của 1 đường 45°) — bị
  nhận nhầm thành witness-line vuông góc, khiến line trong test bị tách
  thành 4 đoạn thay vì gộp đúng 2. Đã dựng lại chính xác bằng script debug
  in ra offset cột (`j`) từng hàng, thấy rõ dãy `[2.5, 2.0, 1.5, 1.0, 0.0,
  -1.0, -1.5, ...]` — trôi dạt tuyến tính đúng kiểu 45°, khác hẳn 1
  witness-line vuông góc thật (offset gần như đứng yên 1 chỗ suốt chuỗi).

- **Đã sửa**: `_perpendicular_witness_at_point()` giờ theo dõi biên độ
  (min/max) offset cột TÍCH LUỸ của cả chuỗi đã chấp nhận — 1 hàng tối mới
  chỉ được tính vào chuỗi nếu không làm biên độ đó vượt `max_offset_drift_px`
  (mặc định 2px). Cố ý dùng biên độ CỘNG DỒN thay vì so từng hàng với 1 mốc
  neo cố định: chỉ so-với-neo-cố-định vẫn lọt 1 ca thứ 2 (tick-mark nằm sâu
  hơn trong line, không sát đầu mút) vì offset của nó dao động "qua lại"
  quanh neo=0 (suy biến do độ dày dim-line lấp đầy cửa sổ ở hàng đầu) mà
  từng bước riêng lẻ vẫn trong ngưỡng — phát hiện được nhờ viết thêm test
  false-positive thứ 2 trước khi chốt fix.

- **Đổi tên cho rõ nghĩa** (theo đúng gợi ý mục (c) ở bản cũ của mục này):
  `split_internal_tick_marks` (cờ của `merge_collinear_lines`) →
  `split_internal_witness_lines`; `split_raw_line_at_tick_marks()` →
  `split_raw_line_at_internal_witness_lines()`. Từ nay "tick_mark" CHỈ dùng
  cho tín hiệu chéo 45° của Lớp 1 (`detect_tick_mark_at_point`,
  `use_tick_mark_detection`, `tick_mark_window_px`, `tick_mark_proximity_px`
  — không đổi, vẫn dùng cho khoảng TRỐNG giữa 2 segment), "witness_line" CHỈ
  dùng cho bước tách nội bộ vuông góc mới. Không đổi tên
  `_perpendicular_witness_at_point`/`find_internal_boundary_offsets` (đã đủ
  rõ nghĩa từ trước).

- **Kết quả sau sửa**:

  ```
  pytest primitive_ir_lib/tests/ -q
  → 46 passed (43 cũ + 3 test mới: 1 false-positive tick-mark-gần-đầu-mút,
    1 true-positive đối chứng, 1 false-positive tick-mark-nằm-sâu-trong-line)
  ```

  Không sửa assertion nào của test cũ để ép pass — chỉ sửa thuật toán dò +
  đổi tên. `test_does_not_merge_across_dimension_chain_boundary` (ca thật
  dim-chain 2760/1525, dùng text-anchor Lớp 2) vẫn PASS nguyên vẹn, xác
  nhận chức năng tách boundary thật không bị ảnh hưởng.

- **CHƯA làm** (giữ nguyên từ trước, vẫn còn nợ): CHƯA chạy lại toàn bộ
  `merge_collinear_lines()` (kèm `blocking_texts` thật từ OCR Tesseract,
  `cross_validate()`) trên đúng ảnh `2026-07-18_101706.png` để xác nhận
  pipeline đầu-cuối tách đúng ranh giới "2760"/"1525" thật — mới xác nhận
  hết hồi quy trên fixture tổng hợp. Đây vẫn là việc ưu tiên #1 tiếp theo.

### Việc tiếp theo (theo thứ tự)

1. Chạy lại **toàn bộ** `merge_collinear_lines()` (không chỉ
   `split_raw_line_at_internal_witness_lines()` đơn lẻ) trên ca thật
   "2760"/"1525" của ảnh `2026-07-18_101706.png` để xác nhận pipeline đầu
   cuối tách đúng, có dùng `blocking_texts` thật (OCR Tesseract) song song.
2. Ghi lại benchmark 3 case (witness-line 1700 / dim-chain 2760-1525 /
   outer 5500) thành file report riêng (kiểu
   `PHUONG_AN_BO_SUNG_LOP1_TICK_MARK.md`) — hiện chỉ tồn tại trong lịch sử
   hội thoại, chưa có trong repo.
3. P2 (chưa bắt đầu): mở rộng `detect_tick_mark_at_point` cho tick chéo 45°
   dùng `HoughLines` thay `HoughLinesP` để bắt witness-line ngắn tốt hơn —
   xuất phát từ 1 proof-of-concept trong phiên chat, chưa đưa vào code.
4. P3 (chưa bắt đầu): tăng `text_block_lateral_px` mặc định từ 15px lên
   25px trong `merge_collinear_lines()` — thay đổi nhỏ, rủi ro thấp, có
   thể làm độc lập bất kỳ lúc nào.
5. `max_offset_drift_px=2` (mới, mục sửa hồi quy ở trên) mới hiệu chỉnh
   thủ công trên fixture tổng hợp — CHƯA benchmark trên ảnh scan thật có
   witness-line hơi nghiêng (không hoàn toàn vuông góc do ảnh bị xoay/méo
   nhẹ khi scan); nếu sau này thấy witness-line thật bị bỏ sót, đây là nơi
   cần xem lại đầu tiên.
