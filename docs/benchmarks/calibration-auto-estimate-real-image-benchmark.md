# Báo cáo benchmark `auto_estimate_calibration()` trên ảnh thật

- **Ngày benchmark**: 21/07/2026
- **Lý do**: mục "Việc nên làm tiếp" #5 trong `HANDOFF.md` (thêm 21/07/2026) —
  `auto_estimate_calibration()` (`primitive_ir_lib/calibration.py`) trước đây
  chỉ có unit test trên fixture tổng hợp, chưa qua benchmark trên ảnh scan
  thật như các bước khác của Phase 1 (xem `docs/benchmarks/`). Đây là
  benchmark đầu tiên cho hàm này.
- **Ảnh thật dùng benchmark**: trang 1 (tờ 01/09, "TỔNG THỂ XE SAU CẢI TẠO")
  của hồ sơ **"TP-GC-A018/07/26"** (bản vẽ ISUZU FVM34W lắp cẩu, do người
  dùng cung cấp qua PDF, render lại thành PNG 300 DPI, 4961×3509px, KHÔNG
  commit vào repo — xem `.gitignore`). sha256 của PNG đã render:
  `dd7fd9e931c1d326526809a7e860a5d2a83fc7e24621352e015507604aa340d3`.
- **Phạm vi**: `auto_estimate_calibration()` + `find_nearest_line()` chạy
  trên `RawLine`/`RawText` trích xuất **THẬT** (không mock) từ
  `extract_raw_geometry(preset="real_scan_tuned_v1")` +
  `detect_text_candidate_rois()` + `extract_text_tesseract(lang="vie+eng")`.
  Đây là bản vẽ **khác** với "TP-TL-A001/07/26" đã dùng ở benchmark Lớp 1
  (`layer1-tick-mark-real-image-benchmark.md`) — cố ý dùng ảnh thứ 2 để mở
  rộng độ đa dạng, đúng như giới hạn đã ghi nhận ở báo cáo trước ("chưa quét
  rộng trên nhiều ảnh scan khác").

---

## 1. Kết luận chính

**Xác nhận đúng nghi ngờ đã ghi trong docstring `find_nearest_line()`**:
trên ảnh thật nhiều-view/nhiều-kích-thước-gần-nhau, `auto_estimate_calibration()`
chọn **sai** cặp (text, line) làm mốc calibration, cho ra scale sai lệch
**~60%** so với scale ước lượng độc lập từ 1 kích thước tổng khác trên cùng
ảnh.

- Text **dimension_value** đầu tiên tìm được (theo thứ tự quét ROI trên→dưới,
  trái→phải) là `"1970"` (chiều rộng vệt bánh trước, trong view "Theo A"),
  bbox tâm ≈ (4344, 1346).
- `find_nearest_line()` chọn `rawline-7933e59f`: (4174,1362)→(4511,1362),
  dài **337px**, cách tâm text **≈16.1px**.
- Nhưng đường dim-line **thật** của "1970" (xác nhận bằng mắt: 2 mũi tên ở
  x≈4172 và x≈4600, xem mục 3) tương ứng `rawline-1db389b2`:
  (4172,1365)→(4600,1365), dài **428px**, cách tâm text xa hơn: **≈46.1px**.
- Vì `find_nearest_line()` chỉ so khoảng cách tâm bbox (không kiểm tra line
  có thực sự chạm 2 đầu mũi tên/khớp `rotation_deg` của text hay không), nó
  chọn nhầm đường **337px bị Hough cắt cụt** (dừng trước khi chạm mũi tên
  phải — khả năng do hatch/nét vẽ dày ở view "Theo A" làm gãy đoạn) thay vì
  đường **428px đúng**.
- Calibration sai kết quả: `scale=5.8457 mm/px` (dùng line 337px sai) —
  trong khi scale ước lượng độc lập từ dim-line tổng "11790" (đo trực tiếp
  bằng column-scan, không qua Hough, xem mục 4) là **≈3.658 mm/px**. Chênh
  lệch **~60%**.

---

## 2. Mục tiêu benchmark

Kiểm tra 3 tiêu chí cho `auto_estimate_calibration()` trên ảnh thật:

1. Có tìm được ít nhất 1 cặp (text dimension_value, line) hay không.
2. Cặp tìm được có phải **đúng** cặp (text đo line nào thì phải khớp line đó)
   hay không.
3. Scale suy ra có **khớp** với scale ước lượng độc lập (đo tay/đo bằng
   phương pháp khác trên cùng ảnh) trong sai số chấp nhận được hay không.

Kết quả: (1) đạt — hàm chạy không crash, trả về 1 `Calibration` object hợp
lệ về mặt kiểu dữ liệu. (2) và (3) **không đạt** — xem mục 1.

---

## 3. Chi tiết ca benchmark — text "1970"

### Dữ liệu đầu vào (trích xuất thật, không mock)

```
extract_raw_geometry(img, preset="real_scan_tuned_v1") -> 1707 RawLine, 40 RawCircle
detect_text_candidate_rois(img)                        -> 219 ROI ứng viên
extract_text_tesseract(img, roi_boxes=rois, lang="vie+eng", min_confidence=30)
                                                         -> 203 RawText, 7 dimension_value
```

7 `dimension_value` tìm được (sắp theo thứ tự quét, đúng thứ tự
`auto_estimate_calibration()` duyệt qua):

| content | conf | bbox_px |
|---|---|---|
| `1970` | 0.96 | (4312, 1333, 4376, 1359) |
| `3230` | 0.96 | (3209, 1365, 3279, 1390) |
| `11790` | 0.96 | (2031, 1431, 2113, 1455) |
| `2180` | 0.96 | (4307, 2723, 4379, 2748) |
| `09` | 0.96 | (4729, 3311, 4760, 3333) — nhiễu (số tờ "Số tờ : 09", không phải kích thước) |
| `20` | 0.71 | (1641, 1365, 1690, 1397) — nhiễu (mảnh vỡ OCR) |
| `141` | 0.42 | (2584, 1365, 2626, 1397) — nhiễu (mảnh vỡ OCR) |

`"1970"` có y nhỏ nhất trong nhóm hợp lệ → được `auto_estimate_calibration()`
xử lý **đầu tiên** (đúng theo cách `detect_text_candidate_rois()` sắp ROI
top-to-bottom) và trả kết quả ngay khi tìm được 1 line trong bán kính
`max_distance_px=150` mặc định — không có cơ chế so sánh nhiều ứng viên để
chọn cái tốt nhất.

### Line được chọn (SAI) và line đúng (xác minh bằng mắt)

| | id | p1_px | p2_px | length_px | khoảng cách tới tâm text "1970" |
|---|---|---|---|---|---|
| **Bị chọn (sai)** | `rawline-7933e59f` | (4174, 1362) | (4511, 1362) | 337.0 | 16.1px |
| **Đúng** (xác nhận bằng mắt — 2 mũi tên) | `rawline-1db389b2` | (4172, 1365) | (4600, 1365) | 428.0 | 46.1px |

Xác nhận trực quan: crop ảnh gốc quanh (4130–4260, 1330–1400) cho thấy mũi
tên trái tại x≈4172–4174 (khớp cả 2 line — điểm đầu đúng); crop quanh
(4520–4650, 1330–1400) cho thấy mũi tên phải tại x≈4600 — chỉ `rawline-1db389b2`
chạm tới đó, `rawline-7933e59f` dừng sớm ở x=4511 (thiếu ~89px, tức thiếu cả
đoạn từ thân số "1970" tới mũi tên phải).

**Nguyên nhân gốc**: `find_nearest_line()` chỉ dùng khoảng cách Euclid giữa 2
tâm bbox, không kiểm tra (a) line có thực sự kéo dài quanh vị trí text theo
đúng hướng ngang mà `rotation_deg` của text gợi ý hay không, (b) có ứng viên
nào khác dài hơn/khớp hơn về mặt hình học (chạm mũi tên) hay không. Đây
đúng là giới hạn đã tự ghi nhận trong docstring hàm (`primitive_ir_lib/calibration.py`
mục "heuristic đơn giản... với bảng nhiều cột/nhiều kích thước sát nhau cần
heuristic tinh hơn").

---

## 4. Xác minh độc lập bằng dim-line tổng "11790"

Để có 1 điểm đối chiếu không phụ thuộc `find_nearest_line()`/Hough, đo trực
tiếp bằng column-scan trên ảnh gốc (không qua bước trích xuất RawLine):

```python
row = img_gray[1458:1463, 400:3750].min(axis=0)   # quét dải mỏng quanh dim-line tổng, y~1460
dark_cols = np.where(row < 150)[0]
# first dark col abs x = 463, last dark col abs x = 3686 -> span = 3223px
```

- Kích thước tổng ghi trên bản vẽ: **11790 mm** (đúng bằng tổng chuỗi
  1440+5820+1300+3230 ghi phía trên cùng dim-line này — tự đối chiếu được).
- Span đo bằng column-scan: **3223 px** (từ mũi tên trái x≈463 tới mũi tên
  phải x≈3686).
- **Scale độc lập**: `11790 / 3223 ≈ 3.658 mm/px`.

So với scale mà `auto_estimate_calibration()` trả về (**5.8457 mm/px**, từ
line 337px sai) — **chênh lệch ≈ +60%**. Nếu dùng scale sai này để quy đổi
toạ độ sang DXF, mọi kích thước trong bản vẽ output sẽ bị phóng to sai lệch
~60% — đủ nghiêm trọng để **không được** dùng calibration suy đoán này cho
DXF sản xuất mà không xác minh (đúng nguyên tắc `needs_verification` đã có
sẵn trong `calibration_registry.py` — xem mục 6).

**Lưu ý về sai số đo tay**: nếu dùng scale độc lập 3.658mm/px để dự đoán độ
dài pixel của chính "1970" (dùng line **đúng** 428px): `428 × 3.658 ≈
1565mm`, lệch so với giá trị thật 1970mm khoảng 20%. Điều này cho thấy
**ngay cả line "đúng" xác định bằng mắt (chạm đúng 2 mũi tên) cũng có thể
không hoàn toàn khớp scale toàn cục** — khả năng do khu vực view "Theo A"
(nhiều hatch/chi tiết lưới tản nhiệt, bánh xe) làm nhiễu vị trí pixel chính
xác của mũi tên khi Hough dựng lại line, hoặc do sai số đọc tay khi xác định
biên mũi tên trên ảnh nén JPEG/anti-alias. **Không kết luận quá mức** từ 1
cặp đối chiếu — cần thêm case để xác nhận scale "chuẩn" thực sự của ảnh này.

---

## 5. Cách tái lập (reproduce)

Vì ảnh gốc không commit (dữ liệu khách hàng nhạy cảm — có tên/chữ ký/con
dấu công ty), đây là kịch bản để tái lập trên **ảnh khác** hoặc khi có lại
ảnh gốc cùng sha256 nêu ở đầu file:

```python
import cv2
from primitive_ir_lib.geometry_extraction import extract_raw_geometry
from primitive_ir_lib.text_extraction import detect_text_candidate_rois, extract_text_tesseract
from primitive_ir_lib.calibration import auto_estimate_calibration, find_nearest_line

IMAGE_PATH = "TP-GC-A018-page1.png"  # render 300 DPI từ PDF gốc
img = cv2.imread(IMAGE_PATH)

geom = extract_raw_geometry(img, preset="real_scan_tuned_v1")
rois = detect_text_candidate_rois(img)
texts = extract_text_tesseract(img, roi_boxes=rois, lang="vie+eng", min_confidence=30)

cal = auto_estimate_calibration(texts, geom.lines, image_height_px=img.shape[0])
print(cal)
# Kỳ vọng (nếu chưa fix find_nearest_line): scale ~5.85 mm/px, method="known_dimension_reference",
# reference_note nhắc tới text '1970' và 1 line ~337px.
```

Đối chiếu độc lập bằng column-scan trên dim-line tổng "11790" (mục 4) để có
scale tham chiếu không phụ thuộc `find_nearest_line()`.

---

## 6. Khuyến nghị / hướng sửa (chưa implement — nằm ngoài phạm vi benchmark này)

Benchmark này **chỉ đo và ghi nhận hiện trạng**, không sửa code. Vài hướng
khả dĩ để cải thiện `find_nearest_line()`, dựa trên đúng bằng chứng ở mục 3:

1. **Lọc theo hướng**: chỉ xét line có hướng gần với `rotation_deg` của text
   (dung sai vài độ) trước khi so khoảng cách — loại được các line không
   cùng trục với con số kích thước.
2. **Ưu tiên line "chạm 2 đầu"**: trong các ứng viên cùng hướng, ưu tiên line
   dài hơn / có 2 đầu mút trùng vị trí ký hiệu mũi tên (cần phát hiện mũi
   tên riêng — hiện chưa có trong `primitive_ir_lib`).
3. **Không tự tin nhận 1 kết quả duy nhất**: hiện hàm dừng ngay khi tìm được
   1 cặp hợp lệ đầu tiên; có thể đổi thành thu thập **nhiều** ứng viên
   (nhiều text dimension_value khác nhau, mỗi text 1 scale) rồi so sánh xem
   các scale có **đồng thuận** (trong dung sai vài %) hay không — nếu lệch
   nhiều như ca này (60%), coi là dấu hiệu không đáng tin và từ chối trả kết
   quả (giữ đúng tinh thần "rule-based/deterministic trước" đã thống nhất).

Điều quan trọng: **cơ chế an toàn hiện có (`needs_verification` trong
`calibration_registry.py`) đã đúng hướng** — kết quả `auto_estimate_calibration()`
KHÔNG được `get_verified_scale()` chấp nhận cho tới khi người dùng tự xác
minh. Benchmark này xác nhận cơ chế chặn đó là **cần thiết**, không phải
thừa — ca thật đầu tiên đã cho thấy suy đoán tự động có thể sai tới 60%.

---

## 8. Cập nhật 21/07/2026 — đã implement hướng sửa #1 (lọc theo hướng)

Đã thêm lọc theo hướng vào `find_nearest_line()` (`primitive_ir_lib/calibration.py`,
tham số mới `angle_tolerance_deg`, mặc định 20°): khi `text.rotation_deg != 0`
(text bị xoay chủ ý — case "số kích thước xoay dọc cạnh view"), chỉ xét các
line có hướng lệch tối đa `angle_tolerance_deg` so với `rotation_deg`; nếu
không có line nào khớp hướng, trả về `None` thay vì miễn cưỡng chọn line
gần nhất bất kể hướng.

**Phát hiện quan trọng khi cài đặt** (đã tự kiểm chứng bằng test hiện có
trước khi code, không đoán): `rotation_deg == 0.0` (mặc định — mọi text từ
`extract_text_tesseract()` hiện tại luôn trả 0.0 vì chưa detect xoay) **không**
hàm ý line liên quan phải ngang. Trong bản vẽ thật, chữ số kích thước
thường giữ ngang để dễ đọc dù đo cạnh dọc — đúng như
`test_find_nearest_line_respects_max_distance` (đã có sẵn trong
`test_basic.py` từ trước) ghép 1 text ngang với 1 line dọc và mong đợi tìm
đúng. Vì vậy lọc theo hướng **chỉ áp dụng khi `rotation_deg != 0`**, không
áp dụng cho trường hợp mặc định.

**Hệ quả trung thực — đã tự chạy lại benchmark để xác nhận, không chỉ suy
luận**: chạy lại `auto_estimate_calibration()` với đúng dữ liệu đã trích
xuất ở mục 3 (đã cache lại, không extract lần 2) cho kết quả **giống hệt**
trước khi thêm fix — vẫn chọn `rawline-7933e59f` (337px, sai), vẫn
`scale=5.8457 mm/px`. Lý do: text "1970" trong ca benchmark này đọc qua
`extract_text_tesseract()` nên `rotation_deg=0.0` — không kích hoạt lọc
hướng, và ngay cả nếu có kích hoạt, **cả 2 line ứng viên** (337px sai và
428px đúng) đều **cùng hướng ngang** (dy=0 với cả hai), nên lọc hướng cũng
không phân biệt được 2 line này.

**Kết luận**: hướng sửa #1 là 1 cải thiện **an toàn và đúng đắn** cho đúng
trường hợp nó nhắm tới (text bị xoay — đã có 6 test mới trong
`primitive_ir_lib/tests/test_calibration.py` xác nhận, gồm 1 test tái hiện
chính xác kiểu lỗi mà nó sửa: 1 line gần tâm text hơn nhưng sai hướng bị
loại đúng để chọn line xa hơn nhưng đúng hướng). Nhưng **KHÔNG sửa được ca
thật đã benchmark ở mục 1-4** vì ca đó là 2 line cạnh tranh **cùng hướng**
(cả hai ngang) — vấn đề nằm ở việc phân biệt line nào chạm đúng 2 đầu mũi
tên, không phải hướng. Cần hướng #2 (ưu tiên line chạm 2 đầu mũi tên) hoặc
#3 (kiểm tra đồng thuận nhiều ứng viên) để sửa ca này — vẫn CHƯA implement.



## 9. Giới hạn trung thực (chưa giải quyết)

- Chỉ benchmark 1 ảnh, 1 case lỗi cụ thể (text "1970" bị gán nhầm line).
  Chưa quét toàn bộ 7 dimension_value tìm được để xem còn case đúng/sai nào
  khác (vd "3230", "2180" — chưa kiểm chứng bằng mắt).
  Chưa thử image thứ 2/3 để xác nhận tỉ lệ lỗi tổng quát.
- Scale "độc lập" ở mục 4 (3.658 mm/px) tự nó cũng chỉ đo bằng 1 dim-line,
  chưa cross-validate bằng ≥2 kích thước độc lập như cách báo cáo Lớp 1 đã
  làm trên ảnh "TP-TL-A001/07/26" (ở đó 2760mm và 1525mm cho cùng 1 scale,
  củng cố độ tin cậy). Chênh lệch 20% ghi nhận ở mục 4 (khi áp scale độc lập
  ngược lại cho "1970") cho thấy cần thêm 1-2 điểm đối chiếu nữa trước khi
  coi 3.658 mm/px là "sự thật nền" chắc chắn cho ảnh này.
- Chưa test trường hợp `max_distance_px` khác mặc định (150px) — tăng/giảm
  ngưỡng này có thể đổi kết quả (vd giảm ngưỡng đủ nhỏ có thể loại được line
  337px sai vì... thực ra không loại được, nó vẫn trong ngưỡng ở 16px).
- **[Cập nhật 21/07/2026]** Hướng sửa #1 (lọc theo hướng, mục 8) đã
  implement + test (6 test mới, `test_calibration.py`) — nhưng **không** sửa
  được ca thật đã benchmark (2 line cạnh tranh cùng hướng ngang). Hướng #2
  (ưu tiên line chạm 2 đầu mũi tên — cần thêm cơ chế phát hiện mũi tên, hiện
  chưa có trong `primitive_ir_lib`) và #3 (kiểm tra đồng thuận nhiều ứng
  viên trước khi trả kết quả) vẫn **chưa implement**.
- Ảnh gốc là bản vẽ CÓ chữ ký/con dấu công ty thật — không commit vào repo,
  chỉ giữ cục bộ + ghi sha256 để tham chiếu.

---

## 10. Cập nhật 21/07/2026 — đã implement hướng sửa #2 (ưu tiên line chạm mũi tên)

**Sửa lại 1 điểm ghi sai ở mục 6/9**: mục 6 từng ghi hướng #2 "cần thêm cơ
chế phát hiện mũi tên, hiện chưa có trong `primitive_ir_lib`" — điều này
**không đúng**. `tick_mark_detection.py` (Lớp 1, benchmark trước đó trên
ảnh "TP-TL-A001/07/26") đã có sẵn `detect_tick_mark_at_point()` — dò ký
hiệu chéo ~45° (tick-mark/mũi tên) sát 1 điểm mút, độc lập với OCR, nhận
`image_bgr=None` thì luôn trả `False` (rơi về fallback an toàn). Hàm này
tái dùng được thẳng cho bài toán "line nào chạm mũi tên" mà không cần viết
detector mới.

**Đã implement**: `find_nearest_line()` và `auto_estimate_calibration()`
(`primitive_ir_lib/calibration.py`) có thêm tham số tuỳ chọn `image_bgr`
(mặc định `None`, KHÔNG phá hành vi cũ khi không truyền). Khi có
`image_bgr`: trong số các line còn lại sau lọc khoảng cách (`max_distance_px`)
+ lọc hướng (#1), đếm mỗi line chạm bao nhiêu đầu mút (0/1/2) bằng
`detect_tick_mark_at_point()`, ưu tiên line chạm nhiều đầu hơn; chỉ
tie-break bằng khoảng cách tâm bbox khi số đầu chạm bằng nhau.

**Test**: 4 test mới trong `primitive_ir_lib/tests/test_calibration.py`
(tổng 10 test), dùng ảnh tổng hợp vẽ bằng `cv2.line` (cùng kỹ thuật với
`test_tick_mark_detection.py`), gồm:
- 1 test tái hiện ĐÚNG tỷ lệ ca lỗi thật "1970": line cắt cụt gần tâm text
  hơn (10px) nhưng chỉ chạm 1/2 đầu mũi tên, vs line đầy đủ xa hơn (30px)
  nhưng chạm cả 2 đầu — xác nhận hướng #2 chọn đúng line đầy đủ.
- 1 test xác nhận khi KHÔNG truyền `image_bgr`, hành vi cũ (chọn nhầm line
  gần hơn) vẫn y nguyên — #2 không tự ý "sửa hộ" khi thiếu ảnh gốc.
- 1 test ảnh trắng trơn không có ký hiệu nào (mô phỏng ảnh scan mờ) — rơi
  về tie-break khoảng cách, không crash, không thiên vị.
- 1 test tie-break khi cả 2 line đều chạm đủ 2 đầu — chọn line gần hơn,
  giống hành vi gốc.

Toàn bộ 17 test `test_basic.py` + 4 test `test_vision_client.py` cũ vẫn
PASS sau khi thêm — không có hồi quy. Tất cả call site hiện có
(`demo_pipeline.py`, `run_image.py`, `cross_validation.py`,
`verify_full.py`) gọi `find_nearest_line`/`auto_estimate_calibration` với
chữ ký cũ, không truyền `image_bgr` → tự động dùng `None` → giữ nguyên
hành vi trước đây (chưa bật hướng #2), không có gì gãy.

**GIỚI HẠN TRUNG THỰC — chưa đóng vòng lặp trên ảnh thật**: benchmark trên
đây mới xác nhận hướng #2 hoạt động đúng trên **ảnh tổng hợp** mô phỏng
đúng hình học của ca lỗi (khoảng cách, việc cắt cụt, vị trí mũi tên). Vẫn
**CHƯA chạy lại** `auto_estimate_calibration(raw_texts, raw_lines, ...,
image_bgr=img_that_da_dung_o_muc_3)` trên **chính ảnh thật**
"TP-GC-A018/07/26" (sha256 `dd7fd9e931c1d326526809a7e860a5d2a83fc7e24621352e015507604aa340d3`)
để xác nhận `detect_tick_mark_at_point()` thực sự dò được ký hiệu mũi tên
thật ở x≈4172 và x≈4600 (chứ không phải tick-mark chéo 45° tổng hợp) — ảnh
gốc scan thật có thể có nhiễu JPEG/anti-alias làm mũi tên không tạo đủ nét
chéo rõ trong cửa sổ 20px mặc định, hoặc mũi tên có hình dạng tam giác đặc
(filled) thay vì 2 nét chéo hở, khiến Canny+Hough không bắt được đúng dải
góc 25°-65°. **Không nên coi hướng #2 đã "sửa xong" ca "1970" cho tới khi
chạy lại đúng ảnh gốc và xác nhận `auto_estimate_calibration()` trả về
scale ≈3.658mm/px** (khớp scale độc lập ở mục 4) thay vì 5.8457mm/px sai
như trước.

---

## 11. Cập nhật 21/07/2026 — đã implement hướng sửa #3 (đồng thuận đa ứng viên)

**Đã implement**: `auto_estimate_calibration()` thêm 3 tham số tuỳ chọn:
`require_consensus` (bật/tắt cơ chế), `consensus_tolerance_pct` (mặc định
10%), `min_consensus_candidates` (mặc định 2). Khi bật, hàm quét **toàn
bộ** `raw_texts` thay vì dừng ở text `dimension_value` đầu tiên tìm được
line — thu thập mọi cặp (text, line) hợp lệ, mỗi cặp cho 1 scale suy ra,
tính scale trung vị, chỉ chấp nhận kết quả khi đủ số ứng viên (`>=
min_consensus_candidates`) nằm trong dung sai `consensus_tolerance_pct` so
với trung vị. Không đủ đồng thuận → trả `None` (từ chối) thay vì đoán liều
— đúng nguyên văn khuyến nghị #3 ở mục 6 ("coi là dấu hiệu không đáng tin
và từ chối trả kết quả"). Chỉ có 1 ứng viên (không đủ dữ liệu so sánh) →
vẫn trả về nhưng gắn cờ rõ trong `reference_note`.

**Phát hiện quan trọng — tự phát hiện qua chạy thử, không chỉ suy luận**:
dự định ban đầu đặt `require_consensus=True` làm **mặc định** (đúng tinh
thần "an toàn hơn" của khuyến nghị gốc). Nhưng khi chạy thử
`python3 -m primitive_ir_lib.demo_pipeline` với default đó, pipeline
**crash ngay lập tức** — 3 `dimension_value` trong fixture demo
("4200"/"1900"/"2100") cho 3 scale không đồng thuận với nhau (khớp với
chính output cross-validation đã in ra từ trước: delta% 90.4/42.4/81.5% —
tự nó đã là bằng chứng các cặp text/line này vốn không nhất quán). Điều
này lộ ra: bật `require_consensus=True` làm mặc định sẽ phá vỡ MỌI call
site hiện có (`demo_pipeline.py`, `run_image.py`, `verify_full.py`) chưa
được cập nhật để xử lý kết quả `None`. Đã sửa lại: default
**`require_consensus=False`** (giữ nguyên hành vi cũ), nhất quán với cách
#1 và #2 đã làm (cả hai đều opt-in qua tham số, không đổi hành vi mặc
định) — xác nhận `demo_pipeline` chạy lại bình thường (exit code 0) sau
khi đổi.

**Test**: 5 test mới trong `test_calibration.py` (tổng 15 test):
- Đồng thuận đa số bỏ qua 1 outlier rõ rệt (2 ứng viên scale=2.0 mm/px,
  1 ứng viên scale=30.0 mm/px) → chọn đúng scale đồng thuận.
- 2 ứng viên lệch nhau quá xa (2.0 vs 30.0), không đạt đồng thuận tối
  thiểu → trả `None`.
- Chỉ 1 ứng viên → vẫn trả về, `reference_note` có "CHƯA xác minh đồng
  thuận".
- Default (không truyền `require_consensus`) VÀ `require_consensus=False`
  tường minh đều giữ đúng hành vi cũ — dùng ứng viên đầu tiên bất kể có là
  outlier hay không.

Toàn bộ 17 test `test_basic.py` + 4 `test_vision_client.py` cũ vẫn PASS —
không hồi quy.

**GIỚI HẠN TRUNG THỰC — cả 3 hướng sửa vẫn chưa được xác nhận cùng lúc
trên ảnh thật**: benchmark trên đây (mục 3-4), hướng #2 (mục 10), và hướng
#3 (mục này) đều mới verify bằng dữ liệu/ảnh **tổng hợp**. Chưa có lần
chạy nào dùng `auto_estimate_calibration(raw_texts, raw_lines,
image_height_px, image_bgr=img, require_consensus=True)` — tức bật ĐỦ cả
3 hướng sửa cùng lúc — trên chính ảnh thật "TP-GC-A018/07/26" (sha256
`dd7fd9e931c1d326526809a7e860a5d2a83fc7e24621352e015507604aa340d3`) để
xem: (a) trong 7 `dimension_value` đã tìm được, có bao nhiêu ứng viên
match được line qua `find_nearest_line`; (b) trong số đó có bao nhiêu thực
sự đồng thuận; (c) scale cuối cùng có khớp ≈3.658mm/px (đối chiếu độc lập
ở mục 4) hay không, hay `require_consensus=True` lại từ chối trả kết quả
vì đa số 7 ứng viên vốn dĩ nhiễu/không đồng thuận trên ảnh thật này. Đây
là việc cần làm tiếp để đóng vòng lặp — cần ai đó có lại ảnh gốc cùng
sha256 trên.
