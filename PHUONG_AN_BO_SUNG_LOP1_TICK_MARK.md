# Bổ sung Lớp 1 (tick-mark/arrowhead detection) — theo "Phương án tổng thể"

Tài liệu này ghi lại phần đã triển khai thêm sau `phương án sửa chữa.md`
(18/07/2026), theo đúng đề xuất trong `New_Text_Document.txt` ("Phương án
tổng thể — thứ tự ưu tiên theo mức độ rủi ro thực tế"), Lớp 1: dò
tick-mark/arrowhead, độc lập hoàn toàn với OCR.

## 1. Đã làm

| Việc | File | Trạng thái |
|---|---|---|
| Module mới dò tick-mark/arrowhead trên ảnh gốc (Canny + HoughLinesP cửa sổ nhỏ quanh mỗi đầu mút, lọc theo góc chéo ~45°) | `primitive_ir_lib/tick_mark_detection.py` | Đã viết, có test |
| Tích hợp vào `merge_collinear_lines()`: tick-mark (Lớp 1) là tín hiệu chặn gộp CHÍNH, text-anchor (Lớp 2, đã có từ trước) lùi thành dự phòng — kết hợp bằng OR (bất kỳ lớp nào báo ranh giới thật thì không gộp) | `primitive_ir_lib/line_merging.py` | Đã sửa, tương thích ngược (image_bgr=None → chỉ dùng Lớp 2 như cũ) |
| Truyền `image_bgr` qua `cross_validate()` để tầng gọi bật được Lớp 1 | `primitive_ir_lib/cross_validation.py`, `demo_pipeline.py` | Đã sửa |
| Test tick-mark detection độc lập (ảnh tổng hợp vẽ bằng cv2: có/không có nét chéo, nét chéo ở xa, `image_bgr=None`) | `primitive_ir_lib/tests/test_tick_mark_detection.py` | 5/5 PASS |
| Test tích hợp: tick-mark chặn gộp dù KHÔNG có text neo nào (mô phỏng đúng tình huống text-anchor một mình thất bại); không truyền ảnh thì rơi về hành vi gap_tol cũ; gãy khúc kỹ thuật không có tick-mark vẫn gộp bình thường | `primitive_ir_lib/tests/test_line_merging.py` | 3 test mới, PASS |
| Toàn bộ test cũ của `primitive_ir_lib` (36 test) | — | PASS, không hồi quy |

## 2. Cách dùng

```python
from primitive_ir_lib.cross_validation import cross_validate

cvs = cross_validate(
    raw_texts, raw_lines, calibration,
    image_bgr=image,  # ảnh gốc BGR — bật tick-mark detection (Lớp 1)
)
```

Nếu không truyền `image_bgr` (hoặc `use_tick_mark_detection=False` khi gọi
trực tiếp `merge_collinear_lines()`), hệ thống rơi về đúng hành vi bản trước
(chỉ dùng text-anchor, Lớp 2) — không phá vỡ pipeline hiện tại.

## 3. Giới hạn còn lại (trung thực, CHƯA giải quyết hết)

- **Chưa benchmark trên ảnh scan thật** — mới tự-test bằng fixture tổng hợp
  vẽ trực tiếp bằng `cv2.line()`. Cần chạy lại trên đúng ảnh
  "TP-TL-A001/07/26" đã gây lỗi trong báo cáo gốc trước khi chốt.
- **Chưa phân biệt "1 nét chéo tình cờ" với "mũi tên thật" (2 nét chéo đối
  xứng hội tụ)** — hiện tại 1 đoạn chéo hợp lệ trong cửa sổ là đủ để báo có
  tick-mark (ưu tiên recall, tránh gộp nhầm). Trên ảnh có hatch chéo dày đặc
  gần witness-line, cái giá phải trả là tăng rủi ro dương tính giả (không
  gộp một số chỗ đáng lẽ nên gộp) — an toàn hơn nhưng có thể tạo nhiều
  witness-line rời rạc hơn cần Reviewer xử lý. Có tham số `min_segments=2`
  sẵn trong `detect_tick_mark_at_point()` để tăng độ chắc chắn khi cần, đánh
  đổi lấy recall thấp hơn.
- **Vision API tier 3** (xác nhận thủ công khi cả tick-mark lẫn text-anchor
  đều không kết luận được) — vẫn CHƯA triển khai, để lại cho vòng sau.
- **Benchmark diện rộng bộ tham số Hough (Lớp 2 của phương án tổng thể)**
  và **đóng vòng an toàn unverified/conflict khi cả 2 tín hiệu đều mơ hồ**
  (Lớp 3) — ngoài phạm vi thay đổi lần này, vẫn cần làm.
