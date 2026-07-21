> [!IMPORTANT]
> **Historical record.** Current architecture is maintained in
> `docs/ARCHITECTURE.md`; current verified status and operating gates are in
> `docs/STATUS.md` and `docs/QUALITY.md`. Preserve the material below as dated
> implementation evidence, not as the source of current project truth.

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

Round-trip kiểm tra `INSERT` component trong Reviewer #1 đã được áp dụng vào
mã nguồn (19/07/2026, nhánh `feature/reviewer-insert-roundtrip`, xem mục
"Bàn giao bổ sung — Reviewer #1 INSERT round-trip" ở cuối file) — trước đó
các lần thử chỉ nằm ngoài mã nguồn, nay `builder.py`/`reviewer.py` đã có.

Phase 5 đã có 64 unit test, demo end-to-end và CLI `python -m agent_lib.run`.
CLI/demo tự cấu hình UTF-8 để chạy được trong PowerShell Windows dùng code page cũ.

Phase 4 đã được tích hợp với Phase 5. Chạy `python -m unittest discover -s
mcp_integration_lib/tests -v` để kiểm tra Reviewer #2/Repair #2; muốn nối
AutoCAD MCP thật, cung cấp callback runtime cho `LiveMCPClient`.

### Bổ sung Phase 4 — File IPC AutoCAD thật (20/07/2026)

`FileIPCLiveMCPClient` giờ có thể dùng AutoCAD File IPC trực tiếp, bao gồm
trường hợp mở DXF mới làm mất AutoLISP dispatcher theo document. Khi cung cấp
`raw_lisp_trigger` và `bootstrap_lisp_path`, client mở document qua AutoCAD
COM rồi tự nạp lại `mcp_dispatch.lsp` trong document mới. DXF Builder cũng
ghi `$INSUNITS=4` (mm), tránh AutoCAD tự scale sai đơn vị.

Smoke test opt-in kiểm chứng trên AutoCAD thật toàn bộ chuỗi `build_dxf` →
review → cố tình thay sai geometry → Repair #2 → review:

```powershell
$env:CAD_AGENT_FILE_IPC='1'
$env:CAD_AGENT_AUTOCAD_HWND='395092' # thay bằng hwnd AutoCAD đang chạy
$env:CAD_AGENT_AUTOCAD_LISP_PATH='C:/.../mcp_dispatch.lsp'
python -m unittest mcp_integration_lib.tests.test_file_ipc_e2e -v
```

Test này chỉ chạy khi đặt `CAD_AGENT_FILE_IPC=1`; AutoCAD sẽ giữ DXF smoke
đang active nên file tạm dưới `C:/temp` được để hệ điều hành dọn sau.

## Kiểm tra môi trường

Các test khi chạy bằng Python mặc định 3.7 dừng ở lỗi `typing.Literal` trong `primitive_ir_lib.models` (Literal thuộc Python 3.8+). Dùng Python 3.8+ (khuyến nghị 3.10+) và cài dependencies trước khi chạy.

```powershell
python -m pip install ezdxf
python -m unittest discover -s dxf_builder_lib\tests -v
```

Chạy lệnh từ thư mục `cad_agent` để các package Phase 1–5 cùng nằm trên import path.

## Việc nên làm tiếp

1. ~~Mở rộng Reviewer #1 để round-trip kiểm tra `INSERT` component: handle,
   block name, layer, insert point, x/y/z scale, rotation và ATTRIB.~~ ĐÃ
   LÀM (19/07/2026, nhánh `feature/reviewer-insert-roundtrip`) — xem mục
   "Bàn giao bổ sung — Reviewer #1 INSERT round-trip" ở cuối file.
2. ~~Thêm Repair #1 cho component INSERT hoặc tách rõ phần này sang Repair #2
   MCP.~~ ĐÃ LÀM (19/07/2026, nhánh `feature/repair-insert-component`) —
   xem mục "Bàn giao bổ sung — Repair #1 cho INSERT component" ở cuối file.
3. Phase 4: tích hợp AutoCAD MCP (file_ipc), Reviewer #2 visual/zoom và Repair #2 theo handle.
4. Duy trì ranh giới: Reviewer #1 chỉ kiểm tra chuyển đổi IR → DXF; lỗi nhận thức/pattern phải do Reviewer #2 đánh giá với ảnh gốc.
5. ~~Benchmark `auto_estimate_calibration()` trên ảnh scan thật~~ MỘT PHẦN
   ĐÃ LÀM (21/07/2026) — xem
   [`docs/benchmarks/calibration-auto-estimate-real-image-benchmark.md`](docs/benchmarks/calibration-auto-estimate-real-image-benchmark.md).
   Benchmark trên ảnh thật thứ 2 ("TP-GC-A018/07/26") **xác nhận đúng** nghi
   ngờ: `find_nearest_line` chọn nhầm line khi bản vẽ có nhiều kích thước
   sát nhau/nhiều view — ca cụ thể text "1970" bị gán nhầm 1 line dài 337px
   (cách tâm text 16px) thay vì line đúng dài 428px (cách tâm text 46px,
   nhưng mới là line chạm đúng 2 mũi tên), khiến scale suy ra sai lệch
   **~60%** so với scale đo độc lập từ dim-line tổng "11790" trên cùng ảnh.

   **[Cập nhật 21/07/2026, tiếp]** Đã implement hướng sửa #1 (lọc theo
   hướng): `find_nearest_line()` giờ có tham số `angle_tolerance_deg`
   (mặc định 20°), CHỈ lọc line theo hướng khi `text.rotation_deg != 0`
   (text bị xoay chủ ý — case "số kích thước xoay dọc"). Cố ý KHÔNG lọc khi
   `rotation_deg == 0` (mặc định, mọi text qua `extract_text_tesseract()`
   hiện nay) vì text đọc ngang vẫn thường đo cạnh dọc — test có sẵn
   `test_find_nearest_line_respects_max_distance` xác nhận điều này. Đã
   thêm 6 test mới (`primitive_ir_lib/tests/test_calibration.py`, file mới
   — trước đây `calibration.py` chưa có test riêng, chỉ có
   `test_calibration_registry.py`). **Đã tự chạy lại benchmark thật để xác
   nhận trung thực**: fix này **KHÔNG** sửa được ca "1970" đã benchmark —
   text đó có `rotation_deg=0.0` nên không kích hoạt lọc, và dù có kích
   hoạt thì 2 line cạnh tranh (337px sai / 428px đúng) đều cùng hướng ngang
   nên lọc hướng không phân biệt được. Cần hướng #2 (ưu tiên line chạm 2
   đầu mũi tên) hoặc #3 (kiểm tra đồng thuận nhiều ứng viên) — **chưa
   implement**. Xem mục 8-9 báo cáo benchmark để biết chi tiết đầy đủ.

   **[Cập nhật 21/07/2026, tiếp nữa] Đã implement hướng sửa #2 (ưu tiên
   line chạm mũi tên)**: `find_nearest_line()`/`auto_estimate_calibration()`
   có thêm tham số tuỳ chọn `image_bgr` (mặc định `None`, không phá hành
   vi cũ). Khi có truyền `image_bgr`, trong số các line còn lại sau lọc
   khoảng cách + lọc hướng, hàm đếm mỗi line chạm bao nhiêu đầu mút (0/1/2)
   bằng ký hiệu tick-mark/mũi tên — tái dùng thẳng
   `detect_tick_mark_at_point()` đã có sẵn trong `tick_mark_detection.py`
   (Lớp 1), **không cần code phát hiện mũi tên mới** như mục 6 báo cáo
   benchmark từng ghi nhầm là "cần thêm, chưa có". Ưu tiên line chạm nhiều
   đầu hơn; chỉ tie-break bằng khoảng cách khi số đầu chạm bằng nhau.

   Đã thêm 4 test mới trong `test_calibration.py` (tổng 10 test, 6 cũ +4
   mới), gồm 1 test tái hiện ĐÚNG tỷ lệ ca lỗi thật "1970" bằng ảnh tổng
   hợp (line cắt cụt gần tâm text hơn nhưng chỉ chạm 1/2 đầu mũi tên vs
   line đầy đủ xa hơn nhưng chạm cả 2) — xác nhận hướng #2 chọn đúng line
   trong ca này. **Giới hạn trung thực**: mới test bằng ảnh tổng hợp
   (cv2.line vẽ tay), **CHƯA chạy lại benchmark bằng đúng ảnh thật
   "TP-GC-A018/07/26"** (ảnh gốc không commit) để xác nhận hướng #2 sửa
   được đúng ca "1970" trên ảnh thật — cần ai đó có lại ảnh gốc (cùng
   sha256 đã ghi trong báo cáo benchmark) chạy lại
   `auto_estimate_calibration(..., image_bgr=img)` để đóng vòng lặp này.

   **[Cập nhật 21/07/2026, tiếp nữa nữa] Đã implement hướng sửa #3 (kiểm
   tra đồng thuận đa ứng viên)**: `auto_estimate_calibration()` có thêm 3
   tham số tuỳ chọn `require_consensus`, `consensus_tolerance_pct`
   (mặc định 10%), `min_consensus_candidates` (mặc định 2). Khi
   `require_consensus=True`, hàm thu thập MỌI cặp (text dimension_value,
   line) hợp lệ trong ảnh (không dừng ở cặp đầu tiên), tính scale trung vị,
   chỉ trả về `Calibration` khi đủ ứng viên đồng thuận (lệch median
   `<= consensus_tolerance_pct`) — nếu không đủ đồng thuận, **từ chối, trả
   `None`** thay vì đoán liều, đúng khuyến nghị #3 gốc. Nếu chỉ có 1 ứng
   viên (không đủ để so đồng thuận), vẫn trả về nhưng `reference_note` ghi
   rõ "CHƯA xác minh đồng thuận".

   **Phát hiện quan trọng khi cài đặt (tự kiểm chứng, không chỉ suy
   luận)**: dự định ban đầu để `require_consensus=True` làm MẶC ĐỊNH (đúng
   tinh thần "an toàn hơn tiện lợi" của khuyến nghị #3) — nhưng khi tự chạy
   thử `python3 -m primitive_ir_lib.demo_pipeline` với default đó, pipeline
   **crash ngay** (`RuntimeError: Không tự động ước lượng được calibration`)
   vì 3 `dimension_value` trong fixture demo (4200/1900/2100) cho 3 scale
   KHÔNG đồng thuận — lộ ra rằng bật mặc định sẽ phá vỡ mọi call site hiện
   có (`demo_pipeline.py`, `run_image.py`, `verify_full.py`) mà chưa ai cập
   nhật để xử lý `None`. Đã **đổi lại default về `require_consensus=False`**
   (giữ hành vi cũ, nhất quán với cách #1/#2 đã làm — opt-in tường minh),
   xác nhận demo pipeline chạy lại bình thường (exit 0) sau khi đổi.
   Người dùng muốn bật lớp an toàn này cho code mới/production cần tự
   truyền `require_consensus=True`.

   Đã thêm 5 test mới trong `test_calibration.py` (tổng 15 test): đồng
   thuận đa số bỏ qua outlier, từ chối khi 2 ứng viên lệch nhau quá xa,
   1 ứng viên duy nhất vẫn trả về kèm cảnh báo, và 2 test xác nhận cả
   default lẫn `require_consensus=False` tường minh đều giữ đúng hành vi
   cũ (dùng ứng viên đầu tiên, kể cả khi nó là outlier). Toàn bộ 17 test
   `test_basic.py` + 4 `test_vision_client.py` vẫn PASS.

   **Giới hạn trung thực còn lại**: cơ chế đồng thuận mới test bằng dữ
   liệu tổng hợp (nhiều cặp text/line dựng tay), **CHƯA chạy
   `require_consensus=True` trên đúng ảnh thật "TP-GC-A018/07/26"** để xem
   trong 7 `dimension_value` tìm được ở ca đó, sau khi thêm cả #1+#2+#3 thì
   có bao nhiêu ứng viên thực sự đồng thuận và calibration cuối cùng có ra
   đúng ≈3.658mm/px hay không — vẫn cần ảnh gốc (sha256 đã ghi ở báo cáo
   benchmark) để đóng vòng lặp cho cả 3 hướng sửa cùng lúc.

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
1. Chạy lại **toàn bộ** `merge_collinear_lines()` (không chỉ
   `split_raw_line_at_internal_witness_lines()` đơn lẻ) trên ca thật
   "2760"/"1525" của ảnh `2026-07-18_101706.png` để xác nhận pipeline đầu
   cuối tách đúng, có dùng `blocking_texts` thật (OCR Tesseract) song song.
   VẪN CHƯA LÀM — đây vẫn là việc ưu tiên #1.
2. ~~Cập nhật docstring đầu `line_merging.py` cho khớp thay đổi.~~ **ĐÃ
   LÀM** (mục "Hồi quy đã sửa" ở trên, nhánh
   `fix/tick-mark-witness-line-regression`) — docstring đầu file giờ mô tả
   đầy đủ 2 lớp tín hiệu + bước tách nội bộ + quy ước đặt tên
   tick_mark/witness_line.
3. ~~Ghi lại benchmark 3 case (witness-line 1700 / dim-chain 2760-1525 /
   outer 5500) thành file report riêng~~ — **ĐÃ LÀM** (phiên
   docs/layer1-real-image-benchmark, merge từ `origin/main`): báo cáo đầy đủ
   ở [`docs/benchmarks/layer1-tick-mark-real-image-benchmark.md`](docs/benchmarks/layer1-tick-mark-real-image-benchmark.md)
   (kết quả mong đợi, false-positive x=673 cần tránh, ngưỡng tham số dùng,
   và kịch bản tái lập test bằng ảnh thật + test tự động hoá offline).
4. P2 (chưa bắt đầu): mở rộng `detect_tick_mark_at_point` cho tick chéo 45°
   dùng `HoughLines` thay `HoughLinesP` để bắt witness-line ngắn tốt hơn —
   xuất phát từ 1 proof-of-concept trong phiên chat, chưa đưa vào code.
5. ~~P3: tăng `text_block_lateral_px` mặc định từ 15px lên 25px trong
   `merge_collinear_lines()`.~~ **ĐÃ LÀM** (19/07/2026, nhánh
   `chore/text-block-lateral-px-25`) — nới biên an toàn cho sai số định vị
   tâm bbox text của OCR, theo nguyên tắc bảo thủ của Lớp 2. CHƯA benchmark
   trên ảnh thật để xác nhận 25px là đủ/không quá rộng (xem docstring tham
   số `text_block_lateral_px` trong `line_merging.py`).
6. `max_offset_drift_px=2` (mới, mục sửa hồi quy ở trên) mới hiệu chỉnh
   thủ công trên fixture tổng hợp — CHƯA benchmark trên ảnh scan thật có
   witness-line hơi nghiêng (không hoàn toàn vuông góc do ảnh bị xoay/méo
   nhẹ khi scan); nếu sau này thấy witness-line thật bị bỏ sót, đây là nơi
   cần xem lại đầu tiên. Có thể đối chiếu thêm với
   `docs/benchmarks/layer1-tick-mark-real-image-benchmark.md` (mục 3) khi
   làm việc #1 ở trên.

---

## Bàn giao bổ sung — Reviewer #1: round-trip kiểm tra INSERT component (19/07/2026)

Áp dụng patch `0001-reviewer-insert-roundtrip.patch` trên nhánh
`feature/reviewer-insert-roundtrip` (từ `main`), đúng việc #1 ở mục "Việc
nên làm tiếp" phía trên (trước đó đã thử trong phiên chat nhưng chưa đưa
vào mã nguồn — xem log cũ của mục đó).

### Đã làm

- **`dxf_builder_lib/builder.py`**: `BuildResult.written_component_by_part_id`
  — đọc lại TRỰC TIẾP từ entity INSERT vừa tạo (block name, layer, insert
  point x/y/z, x/y/z scale, rotation, ATTRIB) ngay lúc build, trước khi lưu
  file — cùng nguyên tắc với `written_geometry_by_primitive_id` đã có cho
  primitive thô. Đây là "nguồn sự thật" cho Reviewer #1 đối chiếu ngược sau
  khi đọc lại file DXF.
- **`dxf_builder_lib/reviewer.py`**: `review_dxf()` giờ round-trip cả entity
  INSERT theo `handle`, so khớp: handle, block name, layer, insert point
  (x/y/z), xscale/yscale/zscale, rotation, và từng ATTRIB (tag/text). Lỗi
  gom vào `ReviewResult.component_mismatches` — dùng dataclass
  `ComponentMismatch` (part_id/field/expected/actual/message) thay vì chuỗi
  tự do, để dễ lọc/debug theo part_id hoặc field cụ thể. Thêm
  `ReviewResult.format_report()` in báo cáo gộp theo part_id. Hợp đồng cũ
  (`mismatches: List[str]`, `checked_count`, `passed`) giữ nguyên, không đổi
  — component_checked_count/component_mismatches là field mới, không phá
  code cũ đang dùng ReviewResult.
- **`dxf_builder_lib/tests/test_reviewer.py`**: 12 test mới — 1 happy path +
  1 loại lỗi cho mỗi trường (handle, written_component thiếu, block name,
  layer, insert point, xscale, rotation, ATTRIB sai giá trị, ATTRIB thiếu) +
  1 test xác nhận `build_components=False` (mặc định) không có gì để kiểm +
  1 test xác nhận report có cấu trúc (không phải chuỗi tự do). Tự SKIP rõ
  ràng (không fail) khi chưa cài `ezdxf`, đúng quy ước sẵn có trong file.

Không sửa `primitive_ir_lib/`. Không làm Repair #1 cho INSERT (để lại theo
mục "việc nên làm tiếp" #2 phía trên).

### Đã verify

```
python3 -m dxf_builder_lib.tests.test_reviewer
→ 17/17 test PASS (5 test cũ + 12 test mới, 1 SKIP đổi thành chạy thật vì
  đã cài ezdxf trong môi trường verify)

python3 -m dxf_builder_lib.tests.test_builder            → 5/5 PASS
python3 -m dxf_builder_lib.tests.test_repair              → 5/5 PASS (không đổi)
python3 -m dxf_builder_lib.tests.test_semantic_components → 11/11 PASS (không đổi)
python3 -m unittest discover -s mcp_integration_lib/tests -v → 4/4 PASS (không đổi)
python3 -m unittest discover -s agent_lib/tests -v            → 64/64 PASS (không đổi)
```

Patch áp bằng `git apply --check` sạch (không cần fuzz/offset), commit giữ
nguyên message gốc của patch qua `git am`.

### Giới hạn trung thực (chưa giải quyết)

- Repair #1 cho INSERT (sửa lại entity theo `written_component_by_part_id`
  khi Reviewer #1 báo mismatch) CHƯA làm — patch này chỉ dừng ở phát hiện
  lỗi (Reviewer), không tự sửa. Xem "việc nên làm tiếp" #2.
- Nhánh `feature/reviewer-insert-roundtrip` và
  `fix/tick-mark-witness-line-regression` được phát triển độc lập (không
  đụng chung file mã nguồn nào, chỉ cùng thêm mục vào cuối `HANDOFF.md`) —
  đã merge cả 2 vào `main` (19/07/2026, `--no-ff`, giữ nguyên lịch sử từng
  nhánh); mục này (trước khi merge) từng ghi "2 nhánh độc lập, cần merge
  riêng" — nay đã merge nên không còn đúng, sửa lại để tránh gây hiểu nhầm
  cho người đọc sau.
- Chưa test round-trip INSERT trên component nào ngoài "beam" (dùng trong
  fixture `_build_beam_component`) — bracket/panel/hinge/node khác có thể
  có ATTRIB hoặc field riêng chưa được test tới.

---

## Bàn giao bổ sung — Repair #1 cho INSERT component (19/07/2026)

Làm việc #2 ở mục "Việc nên làm tiếp" phía trên, trên nhánh
`feature/repair-insert-component` (từ `main`, sau khi đã merge cả fix
tick-mark và Reviewer #1 INSERT round-trip).

### Đã làm

- **`dxf_builder_lib/repair.py`**: thêm `ComponentRepairResult` (dataclass,
  tách riêng khỏi `RepairResult` — field `part_id` thay vì `primitive_id`,
  đúng tinh thần `ComponentMismatch` tách khỏi `mismatches` ở reviewer.py)
  và `repair_insert_components(build_result, component_mismatches)`. CÙNG
  chiến lược xoá-theo-handle-rồi-vẽ-lại với `repair_dxf()` (primitive thô),
  nhưng:
  - Nguồn sự thật là `written_component_by_part_id` (không phải
    `written_geometry_by_primitive_id`).
  - Input là `List[ComponentMismatch]` có sẵn `part_id` (không cần trích từ
    chuỗi tự do như `_primitive_id_from_mismatch()`).
  - Vẽ lại bằng `msp.add_blockref()` + `blockref.add_auto_attribs()` — vì
    MỌI component type (frame_beam/bracket/panel/panel_rect/bracket_L/
    hinge/node) đều dùng chung cơ chế blockref+attrib này, hàm này generic
    cho tất cả, KHÔNG cần nhánh theo `component_type_by_part_id` (khác
    `repair_dxf()`, phải nhánh theo geom_type vì line/circle/arc/text mỗi
    loại 1 hàm `add_*` khác nhau).
  - Có 2 điểm bỏ qua an toàn (skip, không crash): thiếu handle/written_component
    trong BuildResult (bug builder.py), và block definition bị thiếu trong
    file DXF khi cần vẽ lại (bất thường, nằm ngoài phạm vi Repair #1 — repair
    này không tự định nghĩa lại block).
- **`dxf_builder_lib/tests/test_repair.py`**: thêm 5 test — rỗng không làm
  gì, sửa block_name sai, sửa xscale+rotation cùng lúc (xác nhận chỉ
  repair 1 lần dù 2 field lỗi), thiếu 1 ATTRIB, và 2 part độc lập bị lỗi
  khác kiểu nhau (xác nhận không lẫn dữ liệu giữa 2 part — b1 dài 500mm và
  b2 dài 300mm phải giữ đúng xscale riêng sau repair).

Không sửa `reviewer.py`/`builder.py`/`primitive_ir_lib/`.

### Đã verify

```
python3 -m dxf_builder_lib.tests.test_repair    → 10/10 PASS (5 cũ + 5 mới)
python3 -m dxf_builder_lib.tests.test_builder              → 5/5 PASS (không đổi)
python3 -m dxf_builder_lib.tests.test_reviewer              → 17/17 PASS (không đổi)
python3 -m dxf_builder_lib.tests.test_semantic_components   → 11/11 PASS (không đổi)
python3 -m pytest primitive_ir_lib/tests/ -q                 → 46/46 PASS (không đổi)
python3 -m unittest discover -s mcp_integration_lib/tests    → 4/4 PASS (không đổi)
python3 -m unittest discover -s agent_lib/tests               → 64/64 PASS (không đổi)
```

Vòng lặp `build → tamper (giả lập lỗi thật) → review (phát hiện) →
repair_insert_components → review (xác nhận hết lỗi)` chạy đúng cho từng
loại lỗi test — không sửa assertion nào để ép pass.

### Giới hạn trung thực (chưa giải quyết)

- Chỉ test trên component "frame_beam" (dùng fixture `_build_beam_component`
  có sẵn từ test_reviewer.py) — bracket/panel/panel_rect/bracket_L/hinge/
  node chưa có test repair riêng, dù về lý thuyết cùng cơ chế blockref+attrib
  generic nên NÊN hoạt động đúng (không có nhánh riêng theo component_type
  trong code repair).
- Nhánh `chore/text-block-lateral-px-25` (P3, bump text_block_lateral_px
  15px->25px) làm song song với nhánh này. **[Cập nhật 21/07/2026]** Đã xác
  nhận merge vào `main`: `primitive_ir_lib/line_merging.py` hiện có
  `text_block_lateral_px: float = 25.0`.
- Case "block definition bị thiếu khi cần repair" (nhánh bỏ qua an toàn
  trong `repair_insert_components()`) chưa có test riêng — khó dựng fixture
  thật cho case này (phải xoá block definition khỏi file DXF theo cách hợp
  lệ, chưa thử với ezdxf API).

---

## 2026-07-20 — Main/master integration verified

Nhánh `integration/main-master` (commit `1e960bb`) lấy `main` làm nền,
khôi phục các benchmark/vision-preflight độc lập từ `master`, và sửa hồi quy
compound pattern: cặp primitive `g1`/`g2` được nhận diện là `gia_do` trong
`test_integration_via_assemble`.

### Môi trường test đã xác minh

- Dùng `.venv-py311` với Python 3.11.9 vì `python-solvespace` build thành
  công ở môi trường này; giữ Python 3.12 hệ thống không thay đổi.
- Khi chạy OCR tests, thêm `C:\Program Files\Tesseract-OCR` vào `PATH` cho
  tiến trình test.
- Lệnh đầy đủ:

  ```powershell
  $env:PATH = 'C:\Program Files\Tesseract-OCR;' + $env:PATH
  .\.venv-py311\Scripts\python.exe -m pytest primitive_ir_lib/tests semantic_ir_lib/tests dxf_builder_lib/tests mcp_integration_lib/tests agent_lib/tests -q
  ```

- Kết quả: **220 passed, 3 warnings**. Ba warning là cảnh báo có chủ ý khi
  OCR Tesseract quét fixture không có ROI, không phải test failure.

### Trạng thái nhánh

`main` là tổ tiên trực tiếp của `integration/main-master`, nên promotion sang
`main` phải dùng fast-forward. Không merge trực tiếp lịch sử độc lập của
`master`; giữ `master` và các feature/fix branch để dọn trong một thay đổi
riêng sau khi `main` ổn định.

**[Cập nhật 21/07/2026]** Lịch sử các nhánh trên đã được gộp (squash) thành
1 commit khi đẩy lên GitHub (`duongchi90/cad-agent`) — `git branch -a` trên
remote hiện chỉ còn `main`, không còn `master`/`integration/main-master`/các
nhánh `feature-`/`fix-`/`chore-` liệt kê trong file này. Mọi ghi chú "chưa
merge"/"nhánh độc lập" ở các mục phía trên chỉ còn giá trị lịch sử (giải
thích quyết định/diễn biến từng phiên làm việc) — code hiện tại trên `main`
đã bao gồm toàn bộ các thay đổi đó.

---

## 2026-07-21 — PDF batch regression and mixed-scale review metadata

### Đã hoàn thành

- Đồng bộ `main` với GitHub, sau đó chạy pipeline Primitive IR trên 5 PDF scan
  (39 trang). Batch hoàn chỉnh ban đầu tạo 39 IR JSON; output benchmark được
  giữ ngoài Git.
- Sửa hồi quy `ZeroDivisionError` trong `cross_validate()` khi OCR đọc `00`/
  `000` thành dimension `0`: trả `unverified`, không chia cho 0. Có regression
  test riêng.
- Thêm `view_calibration.py`: parse nhãn tỷ lệ OCR (`TL 1:n`, `Tỷ lệ 1:n`,
  `Tile 1:n`), quy đổi `mm_per_px = n * 25.4 / dpi`, và ghi candidate kèm
  provenance vào manifest PDF.
- Candidate quét toàn bộ trang, không giới hạn title block. Heuristic gom line
  thành cụm geometry và chỉ gán nhãn khi có một cụm gần nhất không mơ hồ.
  Evidence dimension/geometry được ghi khi tìm được cặp trong cùng vùng.
- `run_image` ghi review sidecar theo yêu cầu của `run_pdf`; output Primitive
  IR/schema gốc không thay đổi. Candidate luôn `needs_verification`.

### Xác minh

```
$env:PATH='C:\Program Files\Tesseract-OCR;'+$env:PATH
.\.venv-py311\Scripts\python.exe -m pytest primitive_ir_lib/tests -q
→ 89 passed, 3 warnings ROI có chủ ý
```

### Giới hạn còn lại

- Region association là heuristic bảo thủ; chưa tạo child IR/DXF từ candidate.
- OCR có thể không đọc nhãn tỷ lệ hoặc đọc thiếu chữ số; không có candidate
  thì không suy đoán scale.
- Một batch rerun có feature mới đã được người dùng yêu cầu tạm dừng; artifact
  dở dang nằm trong `output/` và không phải kết quả benchmark chính thức.

---

## 2026-07-20 — File IPC Live MCP adapter

`mcp_integration_lib.mcp_client.FileIPCLiveMCPClient` kết nối trực tiếp
AutoCAD File IPC qua `C:/temp`, giữ `FakeMCPClient` cho unit test và giữ
`LiveMCPClient` callback-based không đổi. Adapter hỗ trợ open/list/get/erase
và tạo line/circle/arc/text cho Phase 4 primitive review/repair.

Live smoke test: bật `CAD_AGENT_FILE_IPC=1` và đặt
`CAD_AGENT_AUTOCAD_HWND` bằng frame handle AutoCAD; trigger tự tìm child
`MDIClient` trước khi gửi `(c:mcp-dispatch)`. Smoke test chỉ đọc entity list
và đã PASS trên AutoCAD thật.
