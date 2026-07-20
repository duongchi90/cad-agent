# Báo cáo benchmark Lớp 1 — tick-mark / witness-line detection trên ảnh thật

> ## ĐÍNH CHÍNH 20/07/2026 — false-positive thật phát hiện thêm ở Ca A và Ca C
>
> Benchmark mở rộng ngày 20/07/2026 (chạy `find_internal_boundary_offsets()`
> trên các `RawLine` trích xuất **THẬT** bằng `extract_lines()` (Hough) trên
> chính ảnh `2026-07-18_101706.png`, thay vì toạ độ đầu-mút tự đo/tự dựng như
> phiên 19/07) phát hiện: kết luận "✅ đúng, không tạo ranh giới giả" của **Ca
> A** và **Ca C** ở mục 4 bên dưới **KHÔNG còn chính xác** với tham số mặc
> định cũ (`min_run_px=8`). Cả 2 ca đều bị tách nhầm do hatch chéo THOẢI (dốc
> nhẹ hơn tick-mark 45° chuẩn) nằm gần dim-line:
>
> | Ca | Line thật (Hough) | `min_run_px=8` (cũ) | `min_run_px=12` (mới, mặc định từ 20/07) | Nguyên nhân |
> |---|---|---|---|---|
> | A (1700) | `(934,249)→(934,98)` | **TÁCH SAI** tại offset≈78 (y≈171) | Không tách ✅ | Hatch chéo kính chắn gió (hình chiếu đứng) đi gần line |
> | B (2760/1525) | `(524,355)→(838,355)` | Tách đúng tại offset=252 (x≈776) | Tách đúng tại offset=252 (x≈776), không đổi | — (ranh giới thật, không bị ảnh hưởng) |
> | C (5500) | `(415,375)→(917,375)` | **TÁCH SAI** tại offset≈252 (x≈667) | Không tách ✅ | Hatch chéo hộp bình nhiên liệu nằm sát dim-line |
>
> **Đã fix**: nâng `min_run_px` mặc định từ 8 lên 12 trong cả 3 hàm
> (`_perpendicular_witness_at_point`, `find_internal_boundary_offsets`,
> `split_raw_line_at_internal_witness_lines`) tại
> `primitive_ir_lib/tick_mark_detection.py`. Xác nhận lại cả 3 ca với mặc
> định mới: A → `[]` ✅, B → `[252.0]` (x≈776) ✅ không đổi, C → `[]` ✅.
> Toàn bộ 46 test hiện có trước đó vẫn PASS (không hồi quy); đã thêm 2 test
> hồi quy mới tái hiện đúng cơ chế lỗi này bằng fixture tổng hợp (không cần
> ảnh thật) — xem `test_perpendicular_witness_regression_shallow_diagonal_drift_needs_min_run_px_12`
> và `test_find_internal_boundary_offsets_default_rejects_shallow_diagonal_hatch`
> trong `primitive_ir_lib/tests/test_tick_mark_detection.py`.
>
> **Đây vẫn là fix GIẢM RỦI RO, không phải fix hình học triệt để**: 1 hatch
> chéo khác trôi dạt chậm hơn nữa (chạm đủ ≥12 hàng liên tục đúng trục) vẫn
> có thể đánh lừa thuật toán. Xem mục 6 (đã cập nhật) và docstring
> `_perpendicular_witness_at_point` (mục "SỬA THÊM 20/07/2026") để biết chi
> tiết đầy đủ + số liệu.
>
> Nội dung mục 1-6 bên dưới **giữ nguyên như phiên 19/07/2026 gốc** (để bảo
> toàn lịch sử/audit trail); coi kết luận "Ca A/C đúng, không tạo ranh giới
> giả" trong các mục đó là **đã lỗi thời, đã được đính chính ở trên**.

---

- **Ngày benchmark**: 19/07/2026
- **Phiên làm việc**: bổ sung Lớp 1 tick-mark detection theo
  `PHUONG_AN_BO_SUNG_LOP1_TICK_MARK.md` ("Phương án tổng thể").
- **Ảnh thật dùng benchmark**: `2026-07-18_101706.png` — bản vẽ hồ sơ
  **"TP-TL-A001/07/26"** (do người dùng cung cấp, không commit vào repo).
- **Phạm vi**: Lớp 1 (`primitive_ir_lib/tick_mark_detection.py`), gồm
  `detect_tick_mark_at_point()` (nét chéo ~45°) và `split_raw_line_at_tick_marks()`
  / `find_internal_boundary_offsets()` / `_perpendicular_witness_at_point()`
  (witness-line vuông góc). **Không** benchmark Lớp 2 (text-anchor) hay
  Vision tier 3.
- **Lưu ý quan trọng**: file này mô tả **kết quả quan sát được và cách tái lập
  test**. Toạ độ pixel dưới đây lấy từ phiên benchmark 19/07/2026 trên ảnh thật
  nêu trên; chúng KHÔNG được lưu dưới dạng test tự nhiên hoá (regression test)
  trong repo vì ảnh thật chưa được commit. Để tái lập, dùng ảnh gốc và các
  toạ độ chỉ dẫn ở mục 5.

Bối cảnh chi tiết xem `HANDOFF.md` (mục "Bàn giao bổ sung — Lớp 1 tick-mark
detection, benchmark ảnh thật") và `PHUONG_AN_BO_SUNG_LOP1_TICK_MARK.md`.

---

## 1. Kết luận chính

Lớp 1 tick-mark detection (chéo ~45°) **KHÔNG gây gộp nhầm** trên ảnh thật —
nhưng đồng thời **KHÔNG cải thiện được gì** trên ca này. Lý do: bản vẽ
"TP-TL-A001/07/26" **không dùng tick-mark chéo 45°** làm ký hiệu ranh giới
giữa các đoạn dimension kế tiếp, mà dùng **witness-line thẳng đứng** (vuông góc
~90° với dim-line) cắt ngang tại điểm ranh giới. `detect_tick_mark_at_point()`
với dải góc mặc định `[25°, 65°]` vốn dò nét chéo 45° nên không bắt được kiểu
ký hiệu này.

Đó là lý do thêm hàm `split_raw_line_at_tick_marks()` (cùng các hàm phụ trợ),
dùng **column-projection** thay vì Hough góc chéo, để dò đúng witness-line
vuông góc **nằm giữa** 1 RawLine bị Hough fuse liền (không có pixel gap).
Hàm này đã verify đúng trên ranh giới thật của ảnh (xem mục 4, ca B), nhưng
**chưa được xác nhận đầu-cuối qua `merge_collinear_lines()` đầy đủ** (vẫn còn
hồi quy, xem `HANDOFF.md` mục "Đang làm dở").

3 ca benchmark (mô tả đầy đủ ở mục 4):

| Ca | Kích thước thật | Kết quả mong đợi | Lớp 1 (chéo) | `split_raw_line_at_tick_marks()` (vuông góc) |
|---|---|---|---|---|
| A | witness-line 1700 (dọc) | 1 segment duy nhất, KHÔNG có ranh giới nội bộ → không được tách | — (không liên quan) | KHÔNG tách ✅ (đúng) |
| B | dim-chain 2760 / 1525 (cùng 1 dim-line ngang) | 2 segment, ranh giới nội bộ tại x≈776 → phải tách tại đó | không bắt được witness-line dọc (đúng) | TÁCH đúng ✅ tại x≈777 |
| C | outer dimension 5500 | 1 segment, KHÔNG có ranh giới nội bộ → không được tách | — | KHÔNG tách ✅ (đúng) |

---

## 2. Mục tiêu benchmark

Xác nhận Lớp 1 (độc lập hoàn toàn với OCR) có:
1. **Không gây gộp nhầm** trên ảnh thật (an toàn, không làm pipeline xấu đi).
2. **Không tạo dương tính giả** tại các chỗ không có ranh giới thật.
3. **Có ích** ở chỗ **bắt đúng** ranh giới thật giữa các đoạn dimension kế tiếp
   trong 1 chuỗi — chỗ mà Lớp 2 (text-anchor) đã từng thất bại khi OCR sai/lệch.

Về (1) và (2): **đạt**. Về (3): `detect_tick_mark_at_point()` **không đạt** trên
bản vẽ này (vì bản vẽ dùng ký hiệu khác); `split_raw_line_at_tick_marks()` **đạt**
ở mức hàm đơn lẻ, nhưng **chưa khép kín** qua `merge_collinear_lines()` đầy đủ.

---

## 3. Môi trường / dữ liệu đầu vào

- **Ảnh**: `2026-07-18_101706.png` (BGR qua `cv2.imread`).
- **Bản vẽ**: "TP-TL-A001/07/26".
- **Tỷ lệ** đo được trên ảnh: ~**0.0917 px/mm** (xác minh bằng 2 kích thước
  độc lập của ca B: 2760 mm → 253 px, 1525 mm → 140 px; cả hai cho cùng scale).
- **Tham số Lớp 1** dùng khi benchmark (mặc định của `tick_mark_detection.py`):

  | Tham số | Giá trị | Ý nghĩa |
  |---|---|---|
  | `window_px` | 20 | bán kính cửa sổ crop quanh điểm mút (chéo) |
  | `diagonal_angle_min_deg` / `_max_deg` | 25 / 65 | dải góc "chéo" so với line chính |
  | `proximity_px` | 6 | đầu mút đoạn chéo phải nằm trong bán kính này quanh điểm đang kiểm tra |
  | `probe_window_px` | 20 | chiều dài quét dọc pháp tuyến (vuông góc) |
  | `col_half_px` | 3 | bề rộng dải cột quét vuông góc |
  | `dark_threshold` | 190 | pixel <190 được coi là "tối" |
  | `leading_gap_max_px` | 5 | hở đầu tối đa cho phép (standoff) |
  | `min_run_px` | 8 | chuỗi pixel tối liên tục tối thiểu để coi là witness-line |
  | `run_gap_tol_px` | 1 | hở nhỏ trong chuỗi vẫn cho phép (chịu nhiễu 1px) |
  | `step_px` (scan) | 2 | bước nhảy khi quét dọc line tìm ranh giới |
  | `cluster_tol_px` | 6 | các hit gần nhau được gộp thành 1 ranh giới |
  | `endpoint_margin_px` | 8 | bỏ qua vùng sát 2 đầu mút thật của line |

- **Không sửa code** trong `primitive_ir_lib/` cho benchmark này (chỉ gọi hàm
  đã có sẵn, đọc ảnh, ghi nhận kết quả).

---

## 4. Ba ca benchmark

### Ca A — witness-line 1700 (dọc, kỹ thuật, 1 đoạn)

- **Vị trí trên ảnh**: witness-line / dim-line **dọc** mang giá trị "1700".
- **Đặc điểm**: là 1 đoạn kỹ thuật liên tục, **không có ranh giới nội bộ** nào
  (không có witness-line khác cắt ngang giữa line).
- **Kết quả mong đợi**: `find_internal_boundary_offsets()` / `split_raw_line_at_tick_marks()`
  trả về **0 ranh giới** và **không tách** (giữ nguyên 1 RawLine).
- **Kết quả thực tế**: ✅ đúng — không tạo ranh giới giả, không tách nhầm.
- **Ý nghĩa**: kiểm tra **specificity** — Lớp mới (vuông góc) không được "quá
  nhạy" và tự ý bẻ 1 dim-line kỹ thuật bình thường thành nhiều đoạn.

### Ca B — dim-chain 2760 / 1525 (ranh giới nội bộ thật, 2 đoạn)

Đây là ca **cốt lõi**, mô tả đúng bug gốc mà Lớp 1 mới sinh ra để sửa.

- **Vị trí trên ảnh**: 2 kích thước **"2760"** và **"1525"** nằm chung trên 1
  dim-line **ngang**, liền nhau theo chuỗi dimension. Trên ảnh, Hough
  **tự fuse** đoạn dim-line này thành 1 RawLine liên tục **không có khoảng
  trống pixel** nào ở ranh giới giữa 2 đoạn — chính là lý do `merge_collinear_lines()`
  (chỉ kiểm tra ranh giới tại các khoảng trống giữa 2 segment khác nhau) **không
  thể** phát hiện ranh giới này bằng Lớp 1/2 của nó. Đây là ca phải dùng
  `split_raw_line_at_tick_marks()` **trước** bước union-find/gộp.
- **Ranh giới thật**: giữa "2760" và "1525", tại **x ≈ 776** trên ảnh.

  > **Đính chính quan trọng** (đã chốt trong phiên benchmark): trong phiên có
  > lúc nhận định ranh giới ở x ≈ 524 — **nhận định đó SAI**. x=524 thực ra là
  > **điểm bắt đầu của cả chuỗi "2760"** (đầu mút ngoài cùng của dim-line),
  > không phải ranh giới nội bộ. Ranh giới nội bộ thật là **x ≈ 776**.

- **Cách xác nhận x≈776 là ranh giới thật** (2 kiểm chứng độc lập):
  1. **Tỷ lệ px/mm nhất quán**:
     - "2760" → đo được ~253 px dọc theo dim-line → scale ≈ 0.0917 px/mm.
     - "1525" → đo được ~140 px → scale ≈ 0.0918 px/mm.
     - Hai giá trị scale khớp nhau → các toạ độ dùng để đo đúng là các ranh
       giới thật, không phải vị trí ngẫu nhiên.
  2. **Pixel thật của witness-line**: tại x≈776 có witness-line **liên tục**
     theo phương dọc (từ xa dẫn tới dim-line), chạm trực tiếp dim-line. Ví dụ
     quan sát được: witness-line liên tục từ **y=340 đến y=357**, chạm dim-line
     tại **y≈356**. Đây là dấu hiệu "cắt ngang" đúng kiểu witness-line vuông góc.

- **Kết quả mong đợi**:
  - `detect_tick_mark_at_point()` (chéo 45°) **không** báo ranh giới — vì ký
    hiệu thật là đường dọc, không phải nét chéo. → kỳ vọng False tại đây.
  - `_perpendicular_witness_at_point(x=776)` → True.
  - `find_internal_boundary_offsets()` → trả về 1 ranh giới gần x≈776.
  - `split_raw_line_at_tick_marks()` → tách RawLine fused (vd `(661, 355)→(838, 355)`)
    thành **2** RawLine, điểm cắt ≈ x=777.

- **Kết quả thực tế** (verify hàm đơn lẻ, không qua `merge_collinear_lines`):
  - ✅ `detect_tick_mark_at_point()` → không báo (đúng, không phải ca của nó).
  - ✅ `_perpendicular_witness_at_point(x=776)` → **True**.
  - ✅ `split_raw_line_at_tick_marks()` → **tách đúng thành 2** tại x≈777.

- **Dương tính giả cần tránh** (đã gặp và đã sửa trong phiên): tại **x≈673**
  trên ảnh có text/hatch rời rạc nằm trong cửa sổ probe nhưng **không liên tục**
  từ dim-line (có khoảng hở lớn giữa text và dim-line). Bản đầu tiên của
  `_perpendicular_witness_at_point()` dùng tiêu chí "chạm N hàng đầu + đủ tổng
  số hàng tối trong cửa sổ" thì **báo nhầm True tại x=673** — vì hàng k=1 (ngay
  đè dim-line) hầu như luôn tối (chính nét dim-line), và chỉ cần 1 vài pixel tối
  rời rạc nào đó trong cửa sổ là đủ đạt tổng số hàng tối. Bản hiện tại (đếm
  **chuỗi pixel tối liên tục** từ dim-line ra, có `leading_gap_max_px`/`run_gap_tol_px`)
  → **False tại x=673, True tại x=776**. Đây là **điểm tinh chỉnh cốt lõi** đã
  được bắt và sửa trong phiên (xem docstring `_perpendicular_witness_at_point`
  trong `primitive_ir_lib/tick_mark_detection.py`).

- **⚠️ CHƯA khép kín đầu-cuối**: mới verify hàm `split_raw_line_at_tick_marks()`
  đơn lẻ. Việc gọi nó qua `merge_collinear_lines()` đầy đủ (kèm `blocking_texts`
  thật từ OCR, `cross_validate()`, v.v.) **vẫn còn gây hồi quy** ở 1 test cũ
  (`test_tick_mark_blocks_merge_even_without_any_blocking_text` ra 4 line thay
  vì 2). Xem `HANDOFF.md` mục "Đang làm dở" để biết trạng thái chính xác.

### Ca C — outer dimension 5500 (1 đoạn, không ranh giới nội bộ)

- **Vị trí trên ảnh**: kích thước **"5500"** — kích thước ngoài (outer) bao trùm.
- **Đặc điểm**: 1 dim-line dài liên tục, **không có ranh giới nội bộ** (không
  có witness-line nào cắt ngang giữa line). Chỉ có tick-mark/witness-line ở 2
  đầu mút thật (đã nằm trong `endpoint_margin_px`, do cơ chế khác của
  `merge_collinear_lines` xử lý khi có pixel gap).
- **Kết quả mong đợi**: `find_internal_boundary_offsets()` → 0 ranh giới;
  `split_raw_line_at_tick_marks()` → giữ nguyên 1 RawLine.
- **Kết quả thực tế**: ✅ đúng — không tạo ranh giới giả, không tách.
- **Ý nghĩa**: kiểm tra thêm **specificity** trên 1 dim-line dài, không bị nhầm
  bởi các tick-mark ở 2 đầu mút (phải nằm ngoài `endpoint_margin_px`).

---

## 5. Cách tái lập (reproduce) test

Vì ảnh thật (`2026-07-18_101706.png`) **chưa commit** vào repo, đây là **kịch
bán tự động**: chuẩn bị ảnh, gọi đúng hàm Lớp 1 với đúng toạ độ, so sánh kết
quả với kỳ vọng ở mục 4.

### 5.1. Yêu cầu

- Python 3.8+ (do `typing.Literal` trong `primitive_ir_lib.models`).
- `pip install opencv-python numpy`.
- Ảnh gốc `2026-07-18_101706.png` đặt ở thư mục cha của repo (hoặc sửa
  `IMAGE_PATH` dưới đây).

### 5.2. Kịch bản tái lập 3 ca

Tạo file tạm (không commit) rồi chạy từ thư mục cha của `primitive_ir_lib/`:

```python
# reproduce_layer1_benchmark.py — KHÔNG commit, chỉ dùng để tái lập.
import cv2
from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.tick_mark_detection import (
    detect_tick_mark_at_point,
    find_internal_boundary_offsets,
    split_raw_line_at_tick_marks,
    _perpendicular_witness_at_point,
)

IMAGE_PATH = "../2026-07-18_101706.png"
img = cv2.imread(IMAGE_PATH)
assert img is not None, f"Không đọc được ảnh: {IMAGE_PATH}"
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

def rawline(p1, p2, id_="L"):
    return RawLine(
        id=id_, p1_px=p1, p2_px=p2, confidence=0.9,
        bbox_px=(min(p1[0], p2[0]), min(p1[1], p2[1]),
                 max(p1[0], p2[0]), max(p1[1], p2[1])),
    )

# --- Ca B là ca cốt lõi. Toạ độ bên dưới theo ảnh thật 2026-07-18_101706.png.
#     Nếu ảnh của bạn có độ phân giải khác, phải đo lại ranh giới (xem 5.3). ---

# Ranh giới thật giữa "2760" và "1525" trên ảnh: x ~= 776, dim-line ở y ~= 355-357.
BOUNDARY_X = 776
DIM_Y = 356
# Dim-line bị Hough fuse (khoảng minh hoạ; đo lại trên ảnh của bạn cho chính xác):
FUSED_P1 = (661, 355)
FUSED_P2 = (838, 355)
# Vị trí text rời rạc đã biết gây dương tính giả ở bản đầu:
FALSE_POS_X = 673

# 1) Lớp 1 chéo 45° KHÔNG bắt được witness-line dọc -> False tại ranh giới thật.
print("detect_tick_mark_at_point (chéo) tại x=776:",
      detect_tick_mark_at_point(img, (float(BOUNDARY_X), float(DIM_Y)), ref_angle=0.0))

# 2) Lớp mới (vuông góc): True tại ranh giới thật, False tại false-positive.
print("_perpendicular_witness_at_point tại x=776:",
      _perpendicular_witness_at_point(gray, float(BOUNDARY_X), float(DIM_Y), 0.0))
print("_perpendicular_witness_at_point tại x=673 (phải False):",
      _perpendicular_witness_at_point(gray, float(FALSE_POS_X), float(DIM_Y), 0.0))

# 3) Tách dim-line fused thành 2 tại ranh giới.
parts = split_raw_line_at_tick_marks(rawline(FUSED_P1, FUSED_P2, "fused"), img)
print("Số đoạn sau split (mong đợi 2):", len(parts))
if len(parts) == 2:
    cut_x = parts[0].p2_px[0]
    print(f"  điểm cắt x ~= {cut_x:.0f} (mong đợi ~={BOUNDARY_X})")

# --- Ca A (1700, dọc, 1 đoạn) và Ca C (5500, 1 đoạn): thay FUSED_P1/P2 bằng
#     toạ độ 2 đầu mút thật của các dim-line đó trên ảnh của bạn, kỳ vọng:
#       find_internal_boundary_offsets(...)  -> []
#       split_raw_line_at_tick_marks(...)    -> [line] (giữ nguyên 1 đoạn)
```

Kỳ vọng khi chạy (đối chiếu với mục 4):

```
detect_tick_mark_at_point (chéo) tại x=776: False
_perpendicular_witness_at_point tại x=776: True
_perpendicular_witness_at_point tại x=673 (phải False): False
Số đoạn sau split (mong đợi 2): 2
  điểm cắt x ~= 777 (mong đợi ~=776)
```

### 5.3. Nếu ảnh của bạn có độ phân giải khác

Toạ độ pixel (BOUNDARY_X, DIM_Y, FUSED_P1/P2, FALSE_POS_X) chỉ đúng cho ảnh
gốc `2026-07-18_101706.png`. Với ảnh khác, cần đo lại:

1. **Tìm ranh giới thật giữa 2 đoạn dimension kế tiếp** bằng cách dò witness-line
   dọc cắt dim-line ngang (mắt thường trên viewer ảnh, hoặc crop + threshold).
2. **Kiểm chứng bằng tỷ lệ px/mm** (như mục 4 ca B): đo pixel của 2 kích thước
   độc lập, tính scale riêng, nếu 2 scale khớp nhau → toạ độ ranh giới đúng.
3. Chạy lại kịch 5.2 với toạ độ mới.

### 5.4. Test tự động hoá (đã có trong repo, không cần ảnh thật)

Các test trong `primitive_ir_lib/tests/test_tick_mark_detection.py` dựng lại
đúng 2 lỗi học được từ ảnh thật bằng fixture tổng hợp (vẽ bằng `cv2`), nên
chạy được offline không cần ảnh gốc:

```bash
python -m pytest primitive_ir_lib/tests/test_tick_mark_detection.py -v
```

Các test có liên quan trực tiếp đến kết luận ở mục 4:

| Test | Mô phỏng lại |
|---|---|
| `test_finds_internal_boundary_touching_dim_line` | Ca B: witness-line chạm dim-line, 1 ranh giới |
| `test_split_raw_line_at_tick_marks_splits_at_boundary` | Ca B: tách đúng thành 2 |
| `test_perpendicular_witness_tolerates_small_standoff_gap` | Ca B: witness-line có standoff vẫn bắt được |
| `test_does_not_confuse_nearby_scattered_text_with_witness_line` | Ca B: false-positive x=673 → không nhận nhầm |
| `test_split_returns_original_line_when_no_internal_boundary` | Ca A/C: không có ranh giới → không tách |
| `test_split_returns_original_line_when_image_bgr_is_none` | Tương thích ngược: không ảnh → giữ nguyên |
| `test_split_ignores_boundary_too_close_to_endpoint` | Ca C: tick ở đầu mút thật không phải ranh giới nội bộ |

---

## 6. Giới hạn / rủi ro đã biết (trung thực)

- **Chưa khép kín đầu-cuối**: `split_raw_line_at_tick_marks()` mới verify đơn
  lẻ; gọi qua `merge_collinear_lines()` đầy đủ **vẫn còn hồi quy** (1 test cũ).
  Chi tiết: `HANDOFF.md` mục "Đang làm dở".
- **Ngưỡng hiệu chỉnh thủ công**: `leading_gap_max_px=5`, `min_run_px=8`
  (LƯU Ý: đã nâng lên **12** từ 20/07/2026 — xem đính chính đầu file),
  `run_gap_tol_px=1` được chọn dựa trên đúng 2 điểm của ảnh
  "TP-TL-A001/07/26" (x=776 True, x=673 False). **Chưa quét rộng** trên nhiều
  ảnh scan khác để xác nhận ngưỡng này tổng quát. Bản thân `min_run_px=8`
  còn lọt thêm 2 false-positive khác (Ca A, Ca C) như đính chính 20/07/2026
  đã ghi ở đầu file — `min_run_px=12` giảm rủi ro nhưng KHÔNG loại trừ hoàn
  toàn khả năng còn ca thứ 3 chưa phát hiện.
- **Ảnh thật chưa commit**: toạ độ trong file này không thể tái lập chính xác
  nếu không có ảnh gốc. Khi commit ảnh, nên kèm hash (vd sha256) để kiểm tra
  nguyên vẹn.
- **Tick-mark chéo 45° chưa benchmark trên ảnh thật dùng chéo thật**: bản vẽ
  "TP-TL-A001/07/26" dùng witness-line vuông góc, nên `detect_tick_mark_at_point()`
  chỉ mới được kiểm chứng dưới dạng "không báo nhầm" — chưa kiểm chứng "báo
  đúng" trên ảnh có tick chéo thật. Cần thêm ảnh thật dùng tick chéo 45° để
  xác nhận cơ chế cũ còn đúng khi kết hợp 2 lớp.
- **Line xiên chưa benchmark kỹ**: mới test kỹ dim-line ngang/dọc. Line xiên
  dùng phép quay toạ độ chung nhưng chưa benchmark trên ảnh thật.
- **Phân biệt "1 nét chéo tình cờ" vs "mũi tên thật"** (2 nét đối xứng hội tụ)
  vẫn CHƯA triển khai — vẫn còn rủi ro dương tính giả trên ảnh có hatch chéo
  dày đặc gần witness-line. Có sẵn `min_segments=2` để tăng độ chắc chắn nếu cần.
