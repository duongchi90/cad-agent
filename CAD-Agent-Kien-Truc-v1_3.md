# CAD Agent — Scan/PDF → AutoCAD LT: Tổng hợp kiến trúc (v1.2)

> Tài liệu tổng hợp toàn bộ quá trình phân tích, dùng để tiếp tục thảo luận/triển khai ở phiên làm việc mới mà không mất context.
> **v1.1**: cập nhật sau khi benchmark thực tế Phase 0 trên 4 ảnh scan thật (xem mục 9).
> **v1.2**: đóng câu hỏi #2 (entity handle mapping) — đã test thật trên AutoCAD LT thật của người dùng qua MCP, kết quả khớp 100%. Thay đổi mới nhất đánh dấu **[v1.2]**.
> **v1.3**: bắt đầu Phase 1 — chốt schema chính thức cho Primitive IR (JSON Schema draft-07) + file ví dụ thực tế. Thay đổi mới nhất đánh dấu **[v1.3]**, xem mục 10.

## 1. Mục tiêu dự án

Đưa ảnh **PDF scan** (không phải PDF vector) → AI tự vẽ lại thành bản vẽ **AutoCAD LT** thật, vừa vẽ vừa tự kiểm tra và tự sửa cho đến khi khớp với bản gốc.

**[MỚI] Domain đã xác nhận**: KHÔNG phải P&ID/ngành nước. Ảnh benchmark thực tế là hồ sơ **thiết kế cải tạo ô tô tải** (kết cấu khung xương thùng xe, lắp đặt ghế học viên, thành trước/sau, lắp đặt thiết bị giám sát hành trình DAT) theo mẫu THACO — đúng domain công việc đăng kiểm/nghiệm thu cải tạo của người dùng. → **`pid_*` Semantic API có sẵn trong `puran-water/autocad-mcp` sẽ KHÔNG dùng được**, phải tự viết Semantic API riêng cho khung xương/tôn thùng xe cải tạo (xem mục 4).

## 2. Kiến trúc đã chốt (v1.1)

```
PDF/Scan
   │
   ▼
Preprocessing (OpenCV: deskew, denoise, binarize)
   │
   ▼
Geometry Extraction (Image2CAD / OpenCV Canny+Hough — deterministic, ĐÃ benchmark tốt)
   │
   ├──────────────────────────────────────────────┐
   ▼                                                ▼
Primitive IR hình học                    [MỚI] Text/Label Extraction (tách nhánh)
(line/circle/arc + tọa độ, KHÔNG          ├─ Tesseract: title block / mã bản vẽ sạch
 dùng Vision để đo)                        └─ Vision (VLM đọc trực tiếp crop): ghi chú dài,
   │                                          số kích thước xoay, nhãn ô bảng
   │                                                │
   │◄───────── cross-validate (số đọc bởi Vision đối chiếu ─┘
   │            với độ dài witness-line đo bởi OpenCV)
   ▼
Primitive IR (JSON: line/circle/arc/text + confidence + nguồn trích xuất)
   │
   ▼
Pattern Recognition + Constraint Detection
   │
   ▼
Constraint Solving (SolveSpace / python-solvespace)
   │
   ▼
Semantic IR
   │
   ▼
DXF Builder (ezdxf) — build 1 lần, không vẽ từng entity qua MCP
   │
   ▼
Reviewer #1 — Headless (IR ⇄ DXF, không cần AutoCAD)
   │           → chỉ bắt lỗi DỊCH THUẬT (Builder sai), KHÔNG bắt lỗi nhận thức
   ▼
Repair #1 (headless, ezdxf)
   │
   ▼
AutoCAD MCP: drawing_open (mở DXF vào AutoCAD LT thật)
   │
   ▼
Reviewer #2 — Visual + Zoom (Screenshot AutoCAD thật ⇄ ảnh scan gốc)
   │           → bắt lỗi NHẬN THỨC (Pattern Recognition hiểu sai)
   ▼
Repair #2 (entity_erase + create qua MCP, dùng entity_id đã map)
   │
   ▼
Final DWG
```

## 3. Vai trò các repo đã kiểm chứng bằng code thật (không chỉ README)

| Repo | Vai trò thực tế | Ghi chú quan trọng |
|---|---|---|
| `puran-water/autocad-mcp` | Executor — thực thi AutoCAD LT | 2 backend: `file_ipc` (cần Windows+AutoCAD LT thật, có undo/zoom) và `ezdxf` (headless, không undo/zoom). Có sẵn `pid_insert_valve/instrument/pump/tank...` nhưng **[MỚI] KHÔNG áp dụng được** — domain thực tế là khung xương/thùng xe cải tạo, không phải P&ID. Phải tự viết Semantic API riêng (vd. `frame_insert_beam`, `panel_insert`, `bracket_insert`...). **[v1.2] Đã kết nối và test thật** qua Claude Desktop + AutoCAD LT của người dùng: schema xác nhận đúng README (`drawing`/`entity`/`block`/`pid`/`view`), và **entity handle giữ nguyên 100%** qua `ezdxf` build → `drawing_open` (xem mục 9.4). Lưu ý vận hành: MCP server chạy trên máy Windows người dùng, không chung filesystem với môi trường xử lý ảnh — mọi file cần AutoCAD mở phải được đưa sang máy đó trước. |
| `adityaintwala/Image2CAD` | Geometry Extraction | Dùng `ezdxf` (trùng lib với MCP backend). Kỹ thuật hay: `DimensionalLinesFeature.py` suy luận dimension-line bằng khoảng cách tới arrowhead (hình học thuần, không AI). **[MỚI] Đã benchmark bằng OpenCV Canny+Hough thay thế trên 4 ảnh thật — kết quả khả quan** (xem mục 9), chưa chạy chính Image2CAD nhưng hướng tiếp cận hình học thuần được xác nhận khả thi. OCR Tesseract thuần **[MỚI] xác nhận cần thay/bổ sung** cho các trường hợp text phức tạp — xem mục 4 và 9. |
| `jeremylongshou/cad-ai-agent` | Chỉ tham khảo **schema** | Không có tool `create_*` nào (grep xác nhận) — chỉ sửa DXF có sẵn (Move/Delete/EditText/AddBlock), không tạo hình học mới. Đáng lấy: schema `EditPlan/EditAction` (confidence, evidence, risk_level, validation_status) → chuyển thành `DrawPlan/DrawAction` cho hệ của bạn. |
| `earthtojake/text-to-cad` | Chỉ tham khảo **format viết Skill** | Domain khác hẳn (sinh CAD 3D/STEP từ NL). Không có code dùng được. Học cách viết SKILL.md: khi nào dùng / input / output / cách validate. |
| `puran-water/pid-digitization-skill` | Không dùng được cho use case này | Chỉ trích xuất tag/metadata → YAML, không vẽ hình học. Raster PDF "not implemented" theo chính tác giả. Đáng giữ lại: kỹ thuật "dual-VLM cross-check" và số liệu hallucination 40-55%. **[MỚI] Làm rõ**: hallucination này xảy ra khi VLM tự **đo/ước lượng tọa độ**, KHÔNG áp dụng cho việc VLM **đọc lại chữ in sẵn** — hai việc khác nhau, xem mục 7 và 9. |
| `python-solvespace` (SolveSpace) | Constraint Solving | Solver hình học thật (parallel/perpendicular/tangent/equal-length...). Tách Constraint Graph thành 2 việc: **Detection** (phải tự viết) + **Solving** (dùng thư viện này, không viết). |
| `puran-water/autocad-drafting` | Companion skill của autocad-mcp | **Chưa xem nội dung** — cần đọc trước khi viết Skill 2 của riêng bạn. Độ ưu tiên giảm vì domain không còn là P&ID nên phần lớn nội dung có thể không áp dụng được. |

**Đã tìm kỹ nhưng KHÔNG tìm được**: agent mã nguồn mở nào làm trọn vẹn "scan → vẽ AutoCAD → tự review → tự sửa". Đây là khoảng trống thật.

⚠️ Lưu ý an toàn: một số repo GitHub xuất hiện khi tìm "AutoCAD + AI" là **crack/keygen giả mạo** — không tải/chạy các repo dạng này.

## 4. Phần bắt buộc phải tự viết (không có sẵn ở đâu)

| Module | Độ khó tương đối | Ghi chú |
|---|---|---|
| Pattern Recognition (primitive → semantic: khung/thanh/bản lề/ốc vít...) | **Cao nhất** | Không có thư viện/model production-ready cho domain khung xương cải tạo ô tô. |
| Constraint Detection | Cao | Ghép với SolveSpace để solve, phần detect tự viết. |
| **[MỚI] Text/Label Extraction (tách khỏi Geometry Extraction)** | **Trung bình — đã benchmark, có hướng giải quyết rõ** | 3 tier theo độ khó, xem mục 9: (1) Tesseract đủ dùng cho title block/mã bản vẽ sạch; (2) Vision đọc trực tiếp cho ghi chú dài + số kích thước xoay — đã test chính xác gần 100%; (3) bảng nhiều cột cần thêm bước tách ô theo lưới (dùng kết quả line-detection) trước khi đọc, không đọc nguyên khối. |
| Reviewer #1 (IR ⇄ DXF) | Trung bình | Deterministic, so sánh số liệu — không dùng VLM. |
| Reviewer #2 (Screenshot ⇄ scan gốc) | Cao | KHÔNG tin thẳng VLM để chấm điểm hình học — cần cơ chế so sánh số liệu + VLM chỉ là lớp phụ về ngữ nghĩa. |
| Repair (#1 và #2) | Trung bình | #1 dùng entity xóa/vẽ lại qua ezdxf; #2 dùng `entity_erase` + `create_*` qua MCP. |
| Entity Mapping (IR ⇄ entity_id CAD) | **[v1.2] Thấp — đã test xong, an toàn** | Handle giữ nguyên 100% qua `ezdxf` build → AutoCAD `drawing_open` (test thật trên AutoCAD LT, xem mục 9.4). Có thể dùng handle làm khóa target trực tiếp cho Repair #2, không cần lớp fallback theo layer/tọa độ. |
| Semantic API cho domain khung xương/thùng xe cải tạo | **[MỚI] Trung bình-Cao** | Domain đã xác nhận không phải P&ID → phải viết mới hoàn toàn, không tận dụng được `pid_*`. |

## 5. Câu hỏi/giả định — cập nhật trạng thái

1. ~~Image2CAD có đọc tốt ảnh scan thật của bạn không?~~ **[MỚI] Trả lời một phần**: chưa chạy chính Image2CAD, nhưng đã benchmark hướng tiếp cận hình học thuần (Canny+Hough) trên 4 ảnh thật → **line/geometry extraction khả thi tốt** ngay cả với bản vẽ nhiều view + bảng dữ liệu dày đặc. **[v1.2]** Với entity handle mapping nay đã xác nhận ổn định (câu #2), rủi ro lớn nhất còn lại của toàn dự án là **text extraction chất lượng cao + Pattern Recognition** (mục 4), không còn là geometry hay entity mapping.
2. ~~Entity handle có giữ nguyên sau khi `ezdxf` build DXF rồi `drawing_open` vào AutoCAD LT thật không?~~ **[v1.2] Đã trả lời: CÓ, giữ nguyên 100%.** Test thật trên AutoCAD LT của người dùng (không phải giả lập): build file DXF bằng `ezdxf` với 3 entity (handle `2F`, `30`, `31`) → `drawing_open` file đó qua MCP thật → `entity:list` trả về đúng 3 handle gốc, khớp tuyệt đối. Rủi ro kiến trúc lớn nhất của dự án coi như đã đóng — xem chi tiết mục 9.4.
3. ~~Domain bản vẽ có đúng là P&ID không?~~ **[MỚI] Đã trả lời: KHÔNG.** Domain là kết cấu cải tạo ô tô tải (xem mục 1).
4. ~~Loại nhiễu cụ thể trong ảnh scan~~ **[MỚI] Đã trả lời**: ảnh không phải scan flatbed mà nhiều khả năng là ảnh chụp/export từ bản vẽ gốc, độ phân giải cố định ~1600×900 (đây là bản nét nhất người dùng có — không kỳ vọng cải thiện thêm bằng cách xin ảnh khác). Nhiễu chính không phải mờ/nghiêng mà là **giới hạn độ phân giải với chữ nhỏ và text xoay** — xem mục 9 để biết cách né vấn đề này bằng đổi công cụ đọc thay vì đổi ảnh.

## 6. Roadmap đề xuất

- **Phase 0 [v1.2: GẦN NHƯ XONG]**: Benchmark line extraction (OpenCV Canny+Hough) trên 4 ảnh scan thật — ✅ xong, kết quả tốt. Benchmark OCR/text extraction trên cùng 4 ảnh — ✅ xong, xác định rõ chiến lược 3 tier (mục 9). Test entity handle mapping trên AutoCAD LT thật — ✅ **[v1.2]** xong, khớp 100% (mục 9.4). **CÒN THIẾU DUY NHẤT**: chạy thử chính Image2CAD (hiện mới test OpenCV thuần thay thế); đọc repo `autocad-drafting` (độ ưu tiên thấp, domain đã đổi khỏi P&ID).
- **Phase 1 (~1 tuần) [v1.3: SCHEMA ĐÃ CHỐT]**: Thiết kế chuẩn Primitive IR (JSON), có trường phân biệt nguồn trích xuất (`geometry_opencv` vs `text_tesseract` vs `text_vision`) và `confidence` riêng cho từng nguồn, cộng trường `handle` (đã xác nhận an toàn để dùng trực tiếp). Xem mục 10.
- **Phase 2**: Pattern Recognition + Constraint Detection cho domain khung xương cải tạo ô tô (thời gian chưa ước lượng được).
- **Phase 3**: Headless Builder (ezdxf) + Reviewer #1 headless.
- **Phase 4**: Tích hợp AutoCAD MCP thật (file_ipc) — Reviewer #2 (zoom, screenshot), Repair #2.
- **Phase 5**: Agent hoá phần ambiguous/confidence thấp bằng LLM.

## 7. Nguyên tắc thiết kế đã thống nhất

- Không để Vision/LLM đo tọa độ chính xác — chỉ dùng cho phần ngữ nghĩa/mơ hồ.
- **[MỚI] Làm rõ ranh giới "đo tọa độ" vs "đọc chữ"**: Vision KHÔNG đáng tin khi phải tự ước lượng khoảng cách/vị trí bằng mắt (đây là nguồn hallucination 40-55% đã ghi nhận ở mục 3). Nhưng Vision khá đáng tin khi chỉ **đọc lại một chuỗi ký tự đã in rõ trên giấy** (kể cả chữ nhỏ, xoay dọc) — đã kiểm chứng thực tế ở mục 9, chính xác gần như tuyệt đối trên các case Tesseract thất bại hoàn toàn. Quy tắc áp dụng: dùng Vision để lấy **giá trị** con số/nhãn, dùng OpenCV để xác nhận **vị trí/độ dài hình học** tương ứng — hai nguồn đối chiếu chéo, không nguồn nào quyết một mình.
- DXF Builder dựng hàng loạt bằng script Python (ezdxf), MCP chỉ dùng để sửa lỗi cục bộ.
- Mọi entity tạo ra phải lưu `entity_id`/`handle` để Repair có thể target chính xác.
- Reviewer nên có tiêu chí đo được (số liệu, ngưỡng sai số), không chấm điểm kiểu "nhìn giống".
- Ưu tiên rule-based/deterministic; AI chỉ xử lý phần confidence thấp/ký hiệu lạ/text phức tạp.

## 8. Việc cần làm ngay (action item)

☑ ~~Gửi 3-5 ảnh/trang PDF scan thật để benchmark~~ — đã gửi 4 ảnh, đã benchmark (mục 9)
☑ ~~Xác nhận domain bản vẽ~~ — đã xác nhận: khung xương/thùng xe cải tạo, không phải P&ID
☑ **[v1.2]** ~~Test entity handle mapping (ezdxf → AutoCAD LT `drawing_open` → `entity_list`)~~ — đã test thật trên AutoCAD LT của người dùng, khớp 100% (mục 9.4)
☑ **[v1.3]** ~~Thiết kế Primitive IR schema có phân nhánh nguồn trích xuất text (Tesseract/Vision)~~ — đã chốt JSON Schema draft-07 chính thức + file ví dụ (mục 10)
☐ Đọc/upload nội dung repo `puran-water/autocad-drafting` (độ ưu tiên giảm do domain đổi)
☐ Viết prototype bước "tách ô bảng theo lưới trước khi đọc" cho case bảng nhiều cột (mục 9, mục 4)
☐ **[v1.3]** Viết code build Primitive IR thật từ output OpenCV (thay vì tay gõ như file ví dụ) — nối kết quả benchmark mục 9.1 vào đúng schema mục 10
☐ **[v1.3]** Viết hàm `cross_validate()`: input 1 text primitive (dimension) + danh sách geometry primitive ứng viên → output object `CrossValidation` (mục 10.2)

## 9. [MỚI] Phase 0 — Kết quả benchmark thực tế (4 ảnh scan thật)

Đã test trên: 1 bản vẽ khung thùng xe đơn giản (4 view + yêu cầu kỹ thuật) và 3 trang hồ sơ THACO K165-CS/TK2 (ghế học viên, thành trước/sau, lắp đặt thiết bị DAT — có bảng thông số kỹ thuật dày đặc).

**9.1. Geometry extraction (Canny + Hough, chưa dùng Image2CAD thật)**
- Ổn định qua cả 4 ảnh, kể cả ảnh phức tạp nhiều view + bảng: 158–496 line phát hiện tùy độ phức tạp trang.
- Overlay trực quan xác nhận bắt đúng khung ngoài, đường viền panel, đường kích thước.
- Hatching dạng chấm bi (không phải gạch chéo) ít gây nhiễu line hơn dự kiến.
- **Kết luận: không phải điểm nghẽn của dự án.**

**9.2. Text/OCR — kết quả chia theo 3 tier độ khó**

| Loại nội dung | Tesseract (baseline) | Vision đọc trực tiếp | Kết luận |
|---|---|---|---|
| Mã bản vẽ / title block sạch (vd. `TP-TL-A001/07/26`, `00 04 000`) | **Tốt ngay cả không tiền xử lý** | Không cần | Dùng Tesseract, rẻ và đủ dùng |
| Bảng thông số nhiều cột (specs DAT) | Cột số liệu: khá tốt sau crop+upscale+Otsu. Cột nhãn hàng: **bị xáo trộn** | Chưa test | Cần tách ô theo lưới trước khi OCR, không đọc nguyên khối |
| Đoạn ghi chú dài, chữ nhỏ (GHI CHÚ/YÊU CẦU KỸ THUẬT) | **Thất bại nặng**, sai cả câu dù đã crop+upscale+Otsu | **Đọc đúng gần như tuyệt đối**, kể cả dấu câu | Chuyển hẳn sang Vision cho loại nội dung này |
| Số kích thước xoay dọc (vd. "1700" cạnh view) | **Thất bại hoàn toàn** (rỗng), dù đã crop+xoay+upscale | **Đọc đúng ngay**, không cần xoay ảnh trước | Chuyển hẳn sang Vision, bỏ bước xoay ảnh thủ công |

**9.3. Giới hạn đã xác nhận**
- Độ phân giải ảnh nguồn cố định ~1600×900 (đây là bản nét nhất hiện có) — **không đổi thêm được**, nên chiến lược là đổi công cụ đọc (Vision) thay vì đổi ảnh đầu vào.
- Chưa test: chính Image2CAD (mới test OpenCV thuần thay thế), độ chính xác Vision trên số lượng lớn hơn 4 ảnh (rủi ro: 4 ảnh có thể chưa đại diện hết các loại nhiễu sẽ gặp trong thực tế vận hành).

**9.4. [v1.2] Entity handle mapping — test thật trên AutoCAD LT của người dùng qua MCP**

Kết nối được `autocad-mcp` thật (không phải giả lập) qua Claude Desktop trên máy người dùng. Quy trình test:

1. Build file DXF bằng `ezdxf` (headless, trong sandbox) với 3 entity: 2 line + 1 circle, ghi nhận handle gốc: `2F`, `30`, `31`.
2. Bonus phát hiện phụ: cho AutoCAD LT (thật) tự tạo 3 entity tương tự bằng `entity:create_line`/`create_circle` trên bản vẽ rỗng → AutoCAD tự cấp **đúng cùng handle** `2F`, `30`, `31`. Cho thấy AutoCAD và `ezdxf` dùng chung quy ước handle-seed mặc định khi bắt đầu từ bản vẽ rỗng/template chuẩn (layer chỉ có `0` và `Defpoints`).
3. Test chính thức: người dùng tải file DXF về máy Windows (`C:\Users\duong\Downloads\handle_test.dxf`), gọi `drawing:open` đúng path đó vào AutoCAD LT thật, sau đó `entity:list`.
4. **Kết quả: khớp tuyệt đối 3/3** — `2F`, `30`, `31` giữ nguyên hoàn toàn sau khi mở file build sẵn từ `ezdxf` vào AutoCAD LT thật.

**Kết luận: an toàn để dùng `handle` làm khóa map trực tiếp giữa Primitive IR và entity CAD thật**, không cần cơ chế fallback match theo layer/tọa độ như lo ngại ban đầu ở v1.0. Đây là rủi ro kiến trúc lớn nhất của toàn dự án — nay đã đóng, đủ điều kiện bắt đầu Phase 1.

**Lưu ý vận hành đã rút ra**: MCP server (`autocad-mcp`) chạy trên máy Windows của người dùng, không chung filesystem với môi trường xử lý ảnh/OCR/geometry (chạy trong sandbox riêng). Mọi file DXF cần AutoCAD mở phải tồn tại vật lý trên máy Windows — không thể truyền path trực tiếp từ sandbox. Cần tính đến bước "đưa file sang máy người dùng" (download thủ công hoặc cơ chế đồng bộ) như một bước rõ ràng trong pipeline thật, không phải chi tiết vặt.

## 10. [MỚI v1.3] Phase 1 — Primitive IR JSON Schema chính thức

Đã chốt schema (JSON Schema draft-07) cho tầng dữ liệu nằm giữa Geometry/Text Extraction và Pattern Recognition (xem vị trí trong sơ đồ mục 2). Đây là "hợp đồng dữ liệu" mà mọi module sau này (Pattern Recognition, Constraint Detection, DXF Builder, cả 2 Reviewer) đều đọc/ghi vào, nên cố định sớm để tránh phải đập đi xây lại khi Phase 2 bắt đầu.

File đính kèm:
- `primitive_ir.schema.json` — schema chính thức, có `description` tiếng Việt giải thích lý do từng trường (không phải chỉ khai kiểu dữ liệu suông).
- `primitive_ir_example.json` — 1 bộ dữ liệu ví dụ dựng tay theo đúng case đã benchmark ở mục 9: 3 entity hình học dùng lại handle test `2F`/`30`/`31` từ mục 9.4, cộng 1 text kích thước "1700" xoay 90° (case Vision thắng Tesseract ở mục 9.2) và 1 text title block (case Tesseract đủ dùng).

**10.1. Cấu trúc tổng quan**

```
PrimitiveIRDocument
├── schema_version
├── source_document      (tên file, trang, kích thước ảnh px, hash)
├── calibration          (quy đổi pixel -> mm: bắt buộc, xem 10.3)
├── primitives[]         (line/circle/arc/text — CHƯA phân loại ngữ nghĩa)
│     ├── id, type, source, confidence, layer, handle
│     ├── geometry | text_data   (tùy type)
│     ├── trace           (bbox_px + tool + timestamp — để debug ngược về ảnh gốc)
│     └── validation      (status theo Reviewer #1/#2)
└── cross_validations[]   (đối chiếu text ⇄ geometry, xem 10.2)
```

Quyết định thiết kế quan trọng: **`primitives` KHÔNG phân biệt "line thuộc khung xương" hay "line là witness-line kích thước"** — đó là việc của Pattern Recognition (Phase 2), Primitive IR chỉ chở dữ liệu thô + nguồn + độ tin cậy. Nếu nhét phân loại ngữ nghĩa vào đây, mọi lỗi Pattern Recognition sẽ lẫn vào tầng lẽ ra phải deterministic, làm Reviewer #1 mất khả năng bắt lỗi "dịch thuật" tách bạch khỏi lỗi "nhận thức" (đúng nguyên tắc đã chốt ở mục 2).

**10.2. Cross-validation — thực thi nguyên tắc mục 7 bằng dữ liệu, không chỉ bằng lời văn**

Mục 7 đã thống nhất "dùng Vision để lấy giá trị, dùng OpenCV để xác nhận vị trí/độ dài". Bảng `cross_validations` là chỗ nguyên tắc đó trở thành so sánh số cụ thể:

```json
{
  "text_value": 1700,
  "geometry_measured_length": 1699.98,
  "delta_percent": 0.0012,
  "match_threshold_percent": 3,
  "status": "confirmed"
}
```

`status = "conflict"` (vượt ngưỡng 3%) không được tự động chọn nguồn nào thắng — phải đẩy sang Reviewer, đúng nguyên tắc "không nguồn nào quyết một mình". Ngưỡng 3% là giá trị mặc định đề xuất, nên tinh chỉnh lại sau khi chạy Phase 1 trên nhiều ảnh hơn 4 ảnh benchmark hiện có (rủi ro còn mở ở mục 9.3).

**10.3. Vì sao bắt buộc phải có `calibration`**

Toạ độ trong `primitives` là đơn vị CAD (mm), không phải pixel — nhưng `bbox_px` trong `trace` lại là pixel. Không có `calibration` thì không thể quy đổi qua lại, và `cross_validations` (so `text_value` mm với `geometry_measured_length` mm) sẽ vô nghĩa. Cách đo khuyến nghị: `known_dimension_reference` — dùng chính 1 kích thước đã ghi rõ trên bản vẽ (như case "1700" ở ví dụ) làm mốc, thay vì suy từ DPI/tỷ lệ khai trong title block (có thể sai nếu ảnh đã bị crop/resize khi scan).

**10.4. Trường `handle` để `null` có chủ đích**

Tại thời điểm Geometry/Text Extraction chạy, chưa có file DXF nên chưa có handle. Field vẫn có mặt từ đầu (không thêm sau) để pipeline downstream (DXF Builder, Repair #2) dùng chung 1 schema xuyên suốt, chỉ cần field này chuyển từ `null` sang giá trị thật sau bước `ezdxf` build — không cần bản schema thứ 2 cho "sau khi build".

**10.5. Việc còn lại của Phase 1 (chưa làm, xem mục 8)**

Schema mới là hợp đồng dữ liệu — còn thiếu code thật để: (a) build `primitives[]` từ output Canny+Hough thay vì gõ tay, (b) build `primitives[]` từ output Tesseract/Vision kèm gán `semantic_role` tự động, (c) hàm `cross_validate()` tự tìm geometry ứng viên gần nhất cho mỗi text có `semantic_role: dimension_value`. Ba việc này nên làm trước khi bắt đầu Phase 2 (Pattern Recognition), vì Phase 2 sẽ đọc trực tiếp `primitives[]` do 3 hàm này sinh ra.

**10.6. [MỚI] Đã làm xong (a)/(b)/(c) + tier-2 (bảng) + Vision API thật**

Cả 3 việc ở mục 10.5 đã có code thật, kiểm chứng bằng test + demo chạy trên OpenCV/Tesseract thật (không phải mock): `geometry_extraction.py`, `text_extraction.py`, `cross_validation.py`. Đã bổ sung thêm ngoài kế hoạch ban đầu: `table_extraction.py` (tier-2, tách ô bảng theo lưới trước khi OCR — xem README riêng của `primitive_ir_lib`) và `vision_client.py` (nối `vision_reader`/`cell_reader` với Claude Vision API thật, cộng chiến lược hybrid Tesseract-trước-Vision-sau cho từng ô bảng). 21/21 test pass, demo + 2 script `verify_tier2.py`/`verify_full.py` chạy sạch trên ảnh tổng hợp. Phase 1 coi như hoàn chỉnh về code (còn thiếu duy nhất: benchmark `vision_client.py` với ảnh scan thật + API key thật — sandbox làm việc hiện tại không có mạng ra `api.anthropic.com` kèm key, xem `primitive_ir_lib/README.md`).

## 11. [MỚI] Phase 2 — Pattern Recognition + Constraint Detection: schema + code bước đầu

Bắt đầu Phase 2 theo đúng phương pháp đã dùng ở Phase 1 (mục 10): **chốt schema trước, viết code sau** — tránh tình trạng phải đập đi xây lại khi domain rule thay đổi. File đính kèm: `semantic_ir.schema.json` (JSON Schema draft-07, có mô tả tiếng Việt từng field, cùng phong cách `primitive_ir.schema.json`).

**11.1. Semantic IR chỉ THAM CHIẾU Primitive IR, không sao chép**

`SemanticIRDocument` gồm `parts[]` (linh kiện ngữ nghĩa: thanh khung, lỗ bắt vít...) và `constraints[]` (quan hệ hình học: song song/vuông góc/bằng nhau/trùng điểm đầu/thẳng hàng). Cả 2 chỉ giữ `primitive_ids` trỏ ngược vào 1 `PrimitiveIRDocument` đã có — không nhúng lại geometry/text. Lý do giữ nguyên nguyên tắc mục 10.1: Primitive IR phải ở deterministic, mọi suy luận/lỗi nhận thức nằm ở tầng Semantic IR để Reviewer #1 (headless, so số) và Reviewer #2 (visual, bắt lỗi nhận thức) vẫn tách bạch được.

**11.2. Pattern Recognition bước đầu — CỐ Ý giới hạn phạm vi**

`pattern_recognition.py` (package mới `semantic_ir_lib/`) chỉ suy `part_type` từ hình học **1 primitive đơn lẻ**: line phân loại ngang/dọc/xiên theo góc so với trục X (`thanh_ngang`/`thanh_doc`/`thanh_xien`), circle phân loại theo bán kính (`lo_bat_vit` nếu nhỏ hơn ngưỡng, ngược lại `duong_vien_tron`). KHÔNG suy linh kiện ghép nhiều primitive (bản lề, giá đỡ, mối hàn...) — việc đó cần nhận dạng hình dạng phức hợp hoặc Vision hỗ trợ (trường `source: vision_assisted` đã có chỗ trong schema nhưng CHƯA triển khai), để tránh đoán bừa đúng nguyên tắc mục 7. Ngưỡng góc/bán kính dùng ở đây là **giá trị đề xuất ban đầu, chưa benchmark trên ảnh thật** (khác Phase 1 vốn đã benchmark ngưỡng 3% ở mục 9) — cần tinh chỉnh khi có ảnh scan thật domain khung xương cải tạo.

**11.3. Constraint Detection — tách Detection khỏi Solving đúng phân công mục 3**

`constraint_detection.py` so từng cặp line, phát hiện 5 quan hệ deterministic (`parallel`, `perpendicular`, `equal_length`, `coincident_endpoint`, `collinear`) bằng công thức hình học thuần (góc, khoảng cách điểm-đường thẳng), KHÔNG dùng SolveSpace ở bước này — đây mới là bước "Detection", "Solving" (dùng `python-solvespace`) để lại cho bước sau đọc `constraints[]` làm input. Test trên dữ liệu tổng hợp cho 6 case (mỗi loại quan hệ + case không có quan hệ + case reject sai type) đều đúng; chạy thử trên chính output demo Phase 1 (43 primitives, ảnh tổng hợp) ra 35 parts + 229 constraints — số constraint cao vì ảnh tổng hợp có nhiều line song song/vuông góc trùng lặp (khung nhiều thanh cùng hướng), là hành vi ĐÚNG kỳ vọng (không lọc trùng ở bước Detection), nhưng cho thấy rõ cần bước lọc/rút gọn trước khi đưa vào solver thật trên ảnh nhiều line hơn.

**11.4. Việc còn lại của Phase 2 (đã làm 3/5, xem mục 11.5 và 11.6)**

- ~~Ghép nhiều primitive thành 1 part phức hợp (bản lề, giá đỡ, mối hàn)~~ —
  **đã làm, xem 11.6**. Dùng rule hình dạng thuần dựa trên constraint đã
  detect (KHÔNG dùng Vision-assisted; trường `source: vision_assisted` vẫn
  còn chỗ trong schema cho tương lai nếu rule hình học không đủ).
- Constraint line-circle/circle-circle (tangent, concentric) — bước đầu chỉ có line-line, vẫn còn thiếu.
- ~~Lọc/rút gọn `constraints[]` trước khi đưa vào SolveSpace~~ — **đã làm, xem 11.5**.
- Benchmark ngưỡng góc/bán kính/confidence (mục 11.2, và `min_confidence` mặc định của pruning) **cùng các ngưỡng compound mới** (`bolt_hole_search_radius_mm`, `parallel_gap_max_mm`, `coincident_distance_mm` — xem 11.6) trên ảnh scan thật — vẫn còn thiếu. `coincident_endpoint`/`gia_do` đã xác nhận hoạt động đúng trên demo (5.0mm, xem 11.6), nhưng `ban_le`/`khung_chu_nhat` và ngưỡng 5.0mm nói chung mới benchmark trên 1 ảnh tổng hợp — vẫn cần benchmark thật trên ảnh scan domain khung xe.
- ~~Tích hợp `python-solvespace` thật (Constraint Solving)~~ — **đã làm, xem 11.5**.
- Xuất `solved_primitives` sang DXF Builder (ezdxf) — bước kế tiếp trong pipeline theo mục 2, đã làm ở Phase 3 (mục 12).

**11.5. [MỚI] Constraint Pruning + Constraint Solving thật — đã làm xong**

Hai việc còn lại quan trọng nhất của mục 11.4 (lọc constraint dư thừa +
tích hợp solver thật) nay đã có code + test, đứng giữa Constraint Detection
và bước xuất DXF trong sơ đồ pipeline mục 2.

`constraint_pruning.py` (`prune_constraints()`) giải quyết đúng vấn đề đã
nêu ở 11.3 (229 constraint cho 20 line): (1) bỏ constraint có confidence
dưới ngưỡng (`min_confidence`, mặc định 0.6); (2) khử trùng lặp tuyệt đối
cùng type + cùng cặp primitive; (3) khử dư thừa bắc cầu cho 3 quan hệ có
tính bắc cầu thật sự (`parallel`, `equal_length`, `collinear`) bằng
Union-Find — mỗi nhóm N line cùng quan hệ chỉ còn N-1 constraint (spanning
tree), `coincident_endpoint` không bắc cầu nên không áp dụng bước này;
(4) khử dư thừa `perpendicular` THEO CẶP NHÓM song song — nếu bước (3) đã
gộp nhiều line vào 1 nhóm song song, giữa 2 nhóm chỉ cần đúng 1 constraint
perpendicular làm chứng, không cần constraint riêng cho mọi cặp line thuộc
2 nhóm đó.

`constraint_solving.py` (`solve_constraints()`) tích hợp `python-solvespace`
THẬT (không mock — thư viện tính toán cục bộ, cài/test offline được sau khi
build 1 lần, khác `vision_client.py` phải mock vì cần API key mạng ngoài).
Khởi tạo mọi điểm tại đúng toạ độ đo được (initial guess), KHÔNG dùng
`sys.dragged()` để ghim điểm — đã test thật và xác nhận ghim tất cả điểm
làm hệ INCONSISTENT ngay khi có 1 constraint chưa thoả mãn hoàn toàn. Cũng
xác nhận Newton-Raphson của solvespace nhạy với THỨ TỰ constraint được thêm
vào cho initial guess đo từ ảnh scan (không phải do hệ mâu thuẫn thật) —
module tự thử nhiều thứ tự (ưu tiên constraint "cục bộ" như perpendicular/
coincident_endpoint trước constraint "lan toả theo nhóm" như parallel/
equal_length/collinear) trước khi báo `didnt_converge`.

Nguyên nhân THẬT đã gặp khi nối 2 module này chạy trên chính dữ liệu Phase 1
thật (`semantic_ir_lib/demo_pipeline.py`, không phải dữ liệu tổng hợp riêng):
9 primitive Phase 1 sinh 17 constraint qua Detection — trong đó 4 line nhóm
ngang × 2 line nhóm dọc sinh 8 constraint `perpendicular` (mọi cặp), nhưng
mỗi cặp đo từ ảnh scan có sai số góc khác nhau (0.63° ở 1 line) nên đưa cả
8 vào solver thật báo `INCONSISTENT`. Sau `prune_constraints()` (17 → 7
constraint, giữ đúng 1 `perpendicular` đại diện), `solve_constraints()` ra
`okay`. Test: `semantic_ir_lib/tests/test_constraint_pruning.py` (9 test —
8 test thuần logic + 1 test tích hợp prune→solve tái hiện chính xác tình
huống trên) và `semantic_ir_lib/tests/test_constraint_solving.py` (7 test
thật với solvespace cho 5 loại constraint + 2 case biên). Cả 2 file test
tự SKIP phần cần solvespace nếu chưa cài package (không fail sandbox không
mạng).

**11.6. [MỚI] Pattern Compound — ghép nhiều primitive thành 1 linh kiện phức hợp — đã làm xong**

Việc còn lại đầu tiên của mục 11.4 (ghép compound) nay đã có code + test,
package mới `semantic_ir_lib/pattern_compound.py`, đứng phía trên
`pattern_recognition.py` (single-primitive parts) nhưng KHÔNG thay thế nó —
1 primitive vừa có single-part riêng, vừa có thể thuộc 1 compound part
(Reviewer #2, Phase 4, cần cả 2 góc nhìn: lỗi dịch thuật cấp primitive lẫn
lỗi nhận thức cấp linh kiện).

Nguyên tắc thiết kế: (1) không đoán bừa — chỉ tạo compound khi luật hình
học rõ ràng thoả mãn, thiếu 1 điều kiện thì bỏ qua, không ép gán; (2) tái
dùng `constraints[]` đã có từ `constraint_detection.py` làm input chính,
KHÔNG đo lại hình học — module chỉ xác minh điều kiện tổ hợp, nếu ngưỡng
detect đổi thì compound tự theo kịp (đúng nguyên tắc "1 nguồn sự thật" đã
áp dụng ở 11.3/11.5); (3) confidence compound = trung bình có trọng số
confidence các constraint thành phần × hệ số khớp hình học, chỉ để xếp
hạng ưu tiên review chứ không phải xác suất thống kê thật.

4 loại compound (`build_compound_parts()`, entry point):

- **`khung_chu_nhat`** (khung chữ nhật kín): tìm 2 cặp `parallel` sao cho
  4 line có `perpendicular` giữa 2 nhóm và `coincident_endpoint` khép kín
  ở ≥3/4 góc (cho phép hở nhẹ do ảnh scan không khép kín hoàn hảo).
- **`gia_do`** (giá đỡ góc vuông, L-bracket): 2 line có cả `perpendicular`
  và `coincident_endpoint` tại 1 đầu chung — compound đơn giản nhất.
- **`ban_le`** (bản lề): 2 line gần song song (gap ≤ `parallel_gap_max_mm`,
  mặc định 50mm — bản lề thật có 2 lá kim loại cách nhau vài mm nên KHÔNG
  yêu cầu `coincident_endpoint` như 2 loại trên) + mỗi line có 1 circle nhỏ
  riêng gần endpoint (trong bán kính `bolt_hole_search_radius_mm`, mặc định
  30mm — mỗi circle chỉ được gán cho thanh gần nhất, loại các case cách đều
  2 thanh vì không đủ bằng chứng gắn kết).
- **`diem_noi`** (điểm hàn/nút gia cố nhiều thanh hội tụ): cluster endpoint
  các line theo khoảng cách (`coincident_distance_mm`, mặc định 5.0mm kể từ
  bản sửa ngưỡng dưới đây — trước là 2.0mm, đồng bộ ngưỡng mặc định của
  `constraint_detection`) bằng Union-Find, giữ cluster có ≥3 line endpoint
  (2 line hội tụ tại 1 điểm đã là `gia_do`, để tránh trùng loại) và ≥50%
  cặp line trong cluster có `coincident_endpoint` constraint thật.

Chống trùng: các compound ứng viên được xếp theo số primitive giảm dần rồi
confidence giảm dần, chọn tham lam (greedy) sao cho 1 primitive không bị
gán vào nhiều compound — vd 4 line tạo `khung_chu_nhat` thì KHÔNG bị tách
thành 4 `gia_do` riêng lẻ.

Wired vào `assemble.py` (`build_semantic_document(..., enable_compound_parts=True)`
mặc định, có thể tắt để so sánh/debug). Test: `semantic_ir_lib/tests/test_pattern_compound.py`
— 17 test (14 gốc + 3 hồi quy, xem bản sửa ngưỡng ngay dưới), PASS độc lập,
thuần logic (không cần package optional nào).

**Bản sửa ngưỡng `coincident_endpoint` (2.0mm → 5.0mm) — đã làm, demo pipeline
giờ ra được compound thật:**

Đúng như hạn chế đã ghi nhận trước đó, `python3 -m semantic_ir_lib.demo_pipeline`
từng KHÔNG tạo ra compound part nào dù dữ liệu thô có 1 góc L rõ ràng.
Nguyên nhân THẬT (xác nhận bằng đo trực tiếp, không đoán): ảnh gốc vẽ góc L
khớp pixel-chính-xác (`primitive_ir_lib/demo_pipeline.py`,
`draw.line([(150,50),(150,550)])` nối `draw.line([(150,550),(750,550)])`,
chung điểm), nhưng sau Canny+Hough+merge (nét vẽ rộng 3px bị tách thành 2
line gần song song mỗi cạnh, cách nhau ~10mm = 3px × scale ~3.4mm/px), 4 tổ
hợp endpoint gần góc đo được khoảng cách 3.43mm / 12.38mm / 14.16mm /
18.49mm — tất cả đều LỚN HƠN `distance_tolerance_mm` cũ (2.0mm) dùng chung
cho `coincident_endpoint`, nên `gia_do`/`khung_chu_nhat` không bao giờ có
đủ điều kiện `coincident_endpoint` để trigger, bất kể ngưỡng riêng của
`pattern_compound.py` là gì — bug nằm ở `constraint_detection.py`, không
phải `pattern_compound.py`.

Đã sửa `_DEFAULT_DISTANCE_TOL_MM` trong `constraint_detection.py` từ 2.0mm
lên 5.0mm (và đồng bộ `constraint_distance_tolerance_mm` mặc định trong
`assemble.py`) — đủ dư so với 3.43mm đã đo (margin ~45%), đồng thời vẫn AN
TOÀN dưới ~10mm (khoảng cách 2 line trùng lặp do Hough tách đôi 1 nét vẽ),
tránh `collinear` (dùng chung tolerance này) nhận nhầm 2 cạnh song song của
cùng 1 nét vẽ thành "cùng 1 đường thẳng". Đã rà toàn bộ test cũ trước khi
sửa — mọi case dùng khoảng cách đúng 0mm (chạm thật) hoặc ≥50mm (cố ý xa),
không có case biên 2–10mm nào bị ảnh hưởng.

Verify: `python3 -m semantic_ir_lib.demo_pipeline` giờ phát hiện
`coincident_endpoint` giữa `rawline-3d7f162f`/`rawline-206f4c51`
(`endpoint_distance_mm: 3.434`) và tạo ra `gia_do` thật (confidence 0.829)
cho đúng cặp line đại diện góc L. Thêm 3 test hồi quy
(`test_coincident_endpoint_tolerates_hough_corner_noise`,
`test_coincident_endpoint_still_rejects_clearly_unrelated_gap` trong
`semantic_ir_lib/tests/test_semantic_ir.py`;
`test_gia_do_with_hough_corner_noise` trong `test_pattern_compound.py`) để
khoá lại hành vi này — chống ai đó vô tình thu hẹp ngưỡng về 2.0mm cũ mà
không biết sẽ tái phát đúng bug này.

**Hạn chế thật còn lại**: giá trị 5.0mm vẫn là ĐỀ XUẤT dựa trên 1 ảnh tổng
hợp, CHƯA benchmark trên ảnh scan thật domain khung xe (mục 11.4) —
`ban_le` (`bolt_hole_search_radius_mm`, `parallel_gap_max_mm`) và
`khung_chu_nhat` trên dữ liệu thật vẫn chưa được kiểm chứng riêng, chỉ mới
`gia_do` trên đúng 1 case demo.

## 12. [MỚI] Phase 3 — DXF Builder + Reviewer #1 headless + Repair #1: code đầy đủ

Bắt đầu Phase 3 theo đúng vị trí trong sơ đồ pipeline mục 2 — đứng ngay sau
Constraint Solving, trước Reviewer #1. Package mới `dxf_builder_lib/`.

**12.1. `build_dxf()` — DXF Builder thật bằng `ezdxf`**

Nhận `PrimitiveIRDocument` (Phase 1) làm nguồn hình học/text chính; nếu có
`solved_primitives` (kết quả `constraint_solving.solve_constraints()`, Phase
2) thì GHI ĐÈ toạ độ line bằng toạ độ đã "làm sạch" thay vì toạ độ đo thô —
đúng thứ tự Constraint Solving → DXF Builder đã chốt ở mục 2. Nếu có
`SemanticIRDocument` (Phase 2) thì suy layer DXF theo `part_type`
(`thanh_ngang` → layer `THANH_NGANG`, màu đỏ; tương tự cho `thanh_doc`,
`thanh_xien`, `lo_bat_vit`, `duong_vien_tron`; primitive không có part hoặc
`part_type=unclassified` → layer `UNCLASSIFIED`; text → layer riêng
`TEXT`) — màu khác nhau theo layer để Reviewer #2 (visual, Phase 4) dễ phân
biệt nhóm linh kiện khi zoom.

Mỗi entity build xong, `handle` CAD thật do `ezdxf` cấp được ghi NGƯỢC LẠI
lên chính `Primitive.handle` gốc — đúng ghi chú đã có sẵn trong
`primitive_ir.schema.json` từ Phase 1 (field `handle`: null cho tới khi DXF
Builder build xong, dùng chung 1 schema xuyên suốt, không cần bản schema
thứ 2 cho "sau khi build"). Đây chính là field mà Repair #2 (Phase 4) sẽ
dùng làm khóa target trực tiếp, đã xác nhận an toàn 100% qua test
`drawing_open` AutoCAD LT thật ở mục 9.4.

Primitive thiếu geometry/text_data (dữ liệu hỏng từ tầng trên) chỉ bị BỎ QUA
(`skipped_primitive_ids`) chứ không làm crash cả file — đúng nguyên tắc mục
7 (lỗi cục bộ nên lộ ra để review, không chặn cả pipeline).

**12.2. `review_dxf()` — Reviewer #1 headless (IR ⇄ DXF)**

Đúng vai trò đã chốt ở mục 2: "chỉ bắt lỗi DỊCH THUẬT (Builder sai), KHÔNG
bắt lỗi nhận thức" (lỗi nhận thức — Pattern Recognition hiểu sai bản vẽ — là
việc của Reviewer #2 visual+zoom, Phase 4, so với ảnh scan gốc chứ không so
với IR). Cách làm: đọc lại CHÍNH file `.dxf` vừa build bằng `ezdxf.readfile()`
(mô phỏng đúng bước `drawing_open` AutoCAD LT sẽ làm ở Phase 4 — nếu
round-trip qua `ezdxf` đã sai thì qua AutoCAD LT thật chắc chắn cũng sai),
tra theo `handle`, so khớp tuyệt đối (dung sai dấu phẩy động ~1e-6) với
`written_geometry_by_primitive_id` mà `build_dxf()` trả về.

Điểm thiết kế quan trọng: reviewer so với `written_geometry_by_primitive_id`
(đúng những gì Builder ĐÃ GHI, đã áp solved override nếu có) — KHÔNG so lại
với toạ độ thô trong `primitive_doc` gốc, vì nếu so với toạ độ thô sẽ ra
dương tính giả cho mọi line đã bị Constraint Solving dịch chuyển hợp lệ.
`written_geometry_by_primitive_id` đóng vai trò "nguồn sự thật" tách bạch
giữa 2 module, đúng nguyên tắc tách trách nhiệm đã áp dụng xuyên suốt dự án
(Detection tách khỏi Solving ở mục 11.3, Pruning tách khỏi Solving ở mục
11.5).

**12.3. Test + hạn chế sandbox hiện tại**

`dxf_builder_lib/tests/test_builder.py` (5 test) và `test_reviewer.py` (5
test): mỗi file có đúng 1 test LUÔN chạy được (xác nhận `ImportError` với
thông báo `pip install ezdxf` rõ ràng khi chưa cài `ezdxf`), 4 test còn lại
cần `ezdxf` thật (build file thật rồi đọc lại/so khớp, hoặc cố tình "phá"
file build đúng theo đúng kiểu lỗi dịch thuật thật có thể xảy ra — handle
sai, toạ độ bị sửa sau build, layer ghi nhận sai) — tự SKIP nếu chưa cài,
cùng quy ước `test_constraint_solving.py` đã dùng cho `python-solvespace`.

**Hạn chế THẬT của sandbox hiện tại**: không có mạng ra ngoài nên KHÔNG cài
được `ezdxf` (cũng như `python-solvespace` ở Phase 2) — 8/10 test của Phase
3 hiện tự SKIP, chưa benchmark thật. Code dựa trên API `ezdxf` ổn định đã
biết rõ (`ezdxf.new()`, `modelspace()`, `add_line/add_circle/add_arc/add_text`,
`entity.dxf.handle`, `ezdxf.readfile()`, `entitydb`) nhưng CHƯA chạy thật
lần nào trong phiên làm việc này — cần benchmark thật ngay khi có môi trường
có mạng/đã cài `ezdxf`, trước khi coi Phase 3 bước đầu là "đã kiểm chứng"
(khác Phase 1/2 vốn đã chạy thật 100% test qua OpenCV/Tesseract/solvespace
khi có sẵn).

## 12. [MỚI] Phase 3 — DXF Builder + Reviewer #1 headless + Repair #1

**12.4. Việc còn lại của Phase 3 (đã làm 1/4, xem mục 12.5)**

- Benchmark thật `build_dxf()`/`review_dxf()`/`repair_dxf()` với `ezdxf` cài đặt — hạn chế sandbox không có mạng, các test tự SKIP.
- ~~Repair #1 (headless, `ezdxf`)~~ — **đã làm, xem 12.5**.
- Semantic API cho domain khung xương/thùng xe cải tạo (`frame_insert_beam`,
  `panel_insert`, `bracket_insert`...) — hiện `build_dxf()` chỉ vẽ hình học
  thô (line/circle/arc/text), chưa có khái niệm "linh kiện" ở tầng DXF, cần
  cho Phase 4 (AutoCAD MCP, đã xác nhận domain không phải P&ID nên không
  dùng được `pid_*` có sẵn — xem mục 4).
- Constraint/vẽ cho `arc` — `constraint_detection.py`/`constraint_solving.py`
  (Phase 2) chưa hỗ trợ quan hệ cho arc, nên arc hiện được `build_dxf()` vẽ
  nguyên trạng từ Primitive IR, không qua Constraint Solving.

**12.5. [MỚI] Repair #1 headless — đã làm xong**

`repair.py` (`repair_dxf()`) nhận `mismatches` từ `ReviewResult.mismatches`
của `review_dxf()`, xoá entity bị lỗi theo `handle` (đã xác nhận handle giữ
nguyên 100% qua ezdxf round-trip, mục 9.4), rồi vẽ lại đúng từ
`BuildResult.written_geometry_by_primitive_id` — đây là nguồn sự thật (những
gì Builder ĐÃ DỰ ĐỊNH ghi), không tra lại Primitive IR gốc (tránh đọc sai
toạ độ thô khi entity đã được áp solved override từ Constraint Solving).

Ghi đè vào đúng file cũ (không tạo file mới), cập nhật
`handle_by_primitive_id` trong `BuildResult` về handle mới do ezdxf cấp (vì
entity mới = handle mới). Caller nên chạy lại `review_dxf()` sau để xác nhận
hết lỗi — `repair_dxf()` KHÔNG tự review lại (tách trách nhiệm, cùng nguyên
tắc pruning tách khỏi solving, review tách khỏi build).

`demo_pipeline.py` (Phase 3) đã được cập nhật để chạy vòng lặp đầy đủ:
`build_dxf()` → `review_dxf()` → nếu có lỗi: `repair_dxf()` → `review_dxf()`
lần 2 để xác nhận. Test: `dxf_builder_lib/tests/test_repair.py` (5 test —
1 luôn chạy được (ImportError), 4 cần ezdxf: mismatches rỗng không làm gì;
sửa toạ độ LINE lệch; sửa layer sai; sửa nhiều entity độc lập — tất cả xác
nhận bằng `review_dxf()` lần 2 pass sau repair).

