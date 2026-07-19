# primitive_ir_lib

Code Phase 1 của dự án CAD Agent (xem `CAD-Agent-Kien-Truc-v1_3.md` mục 10):
sinh **Primitive IR** đúng `primitive_ir.schema.json` từ ảnh scan/PDF, gồm 3
việc đã liệt ở mục 10.5:

1. Build `primitives[]` từ output Canny+Hough (OpenCV) — `geometry_extraction.py`
2. Build `primitives[]` từ Tesseract (tier 1) + Vision pluggable (tier 3) — `text_extraction.py`
3. Hàm `cross_validate()` đối chiếu text ⇄ geometry — `cross_validation.py`

**[Cập nhật]** Đã bổ sung tier 2 (bảng nhiều cột) — `table_extraction.py`,
tách ô theo lưới (dùng lại `RawLine` đã có, không chạy lại Hough riêng) rồi
OCR từng ô, thay vì đọc nguyên khối. Demo (`demo_pipeline.py`) có bước 4b
minh hoạ, đọc đúng 6/6 ô của bảng thông số tổng hợp mà không bị xáo trộn
cột nhãn/số liệu — đúng vấn đề đã ghi nhận ở mục 9.2 tài liệu tổng hợp.

**[v1.2 + OpenCV 5 fix]** `geometry_extraction.py` đã sửa tương thích cả
OpenCV 4 (HoughLinesP shape `(N,1,4)`) và OpenCV 5 (shape `(N,4)`).

## Cài đặt

```bash
pip install opencv-python numpy pytesseract pillow
# + cài binary tesseract-ocr của hệ điều hành:
#   Linux:   apt-get install tesseract-ocr tesseract-ocr-vie
#   Windows: choco install tesseract  hoặc tải từ github.com/UB-Mannheim/tesseract/wiki
#   macOS:   brew install tesseract tesseract-lang
```

## Cấu trúc module

| File | Vai trò |
|---|---|
| `models.py` | Dataclass khớp 1-1 `primitive_ir.schema.json`. Mọi module khác chỉ dùng qua đây, không tự build dict. |
| `geometry_extraction.py` | Canny+Hough (OpenCV) → `RawLine`/`RawCircle` ở **tọa độ pixel**. |
| `text_extraction.py` | `extract_text_tesseract()` (tier 1) + `extract_text_vision()` (tier 3, nhận `vision_reader` callable) → `RawText` ở tọa độ pixel + `classify_semantic_role()` rule-based. |
| `table_extraction.py` | **[MỚI]** Tier 2: `extract_table_cells()` — nhận diện lưới từ `RawLine` có sẵn, tách ô, đọc từng ô độc lập → `RawText` với `semantic_role=table_cell`. |
| `calibration.py` | Ước lượng `Calibration` (pixel→mm) từ 1 cặp (text kích thước, line gần nhất). |
| `cross_validation.py` | `cross_validate()` — so khớp text kích thước với geometry đo được, gắn `confirmed`/`conflict`/`unverified`. KHÔNG tự sửa dữ liệu khi lệch. |
| `assemble.py` | Ghép Raw* + Calibration → `PrimitiveIRDocument` hoàn chỉnh (tọa độ CAD). |
| `validator.py` | Kiểm tra nhẹ theo ràng buộc schema (không cần lib `jsonschema`). |
| `io_utils.py` | Lưu/đọc JSON. |
| `vision_client.py` | **[MỚI]** Nối `vision_reader`/`cell_reader` với Claude Vision API thật (`make_vision_reader()`), cộng `make_hybrid_cell_reader()` — Tesseract trước, chỉ gọi Vision khi Tesseract thất bại/confidence thấp. Cần `pip install anthropic` + `ANTHROPIC_API_KEY` trong env. |
| `demo_pipeline.py` | Chạy thử toàn bộ trên ảnh test tổng hợp (tier 1 + 2 + 3). |

## Chạy demo

```bash
# từ thư mục cha của primitive_ir_lib/
python -m primitive_ir_lib.demo_pipeline
# hoặc dùng Claude Vision API thật thay vì mock_vision_reader():
export ANTHROPIC_API_KEY=sk-ant-...
pip install anthropic --break-system-packages
python -m primitive_ir_lib.demo_pipeline --real-vision
```

In log từng bước + lưu `demo_output/synthetic_test_drawing.png` và
`demo_output/primitive_ir_demo_output.json`.

**Vì sao demo dùng ảnh tổng hợp**: phiên làm việc tạo package này không có
ảnh scan thật đính kèm. Ảnh test mô phỏng đúng 3 case đã benchmark thật
ở mục 9.2/9.4 (số kích thước "1700" xoay dọc cạnh view, title block dạng mã
'TP-TL-A001/07/26', bảng thông số 2x3 ô). Khi có ảnh scan thật, thay
`make_synthetic_drawing()` bằng ảnh thật và nối `mock_vision_reader()` với
API Claude Vision thật (code mẫu đã viết sẵn dạng comment trong hàm đó).

## Chạy test

```bash
python -m primitive_ir_lib.tests.test_basic
# hoặc nếu có pytest: python -m pytest primitive_ir_lib/tests/ -v
```

21 test (11 gốc + 6 tier-2 + 4 vision_client):
- classify_semantic_role (3)
- calibration + pixel_to_cad (2)
- cross_validate confirmed/conflict/unverified (3)
- table detect_grid / build_cells / extract_table_cells (6)
- validator pass/fail (2)
- vision_client: hybrid cell_reader fallback logic (4, xem
  `tests/test_vision_client.py` — test bằng vision_reader GIẢ, không cần
  mạng/API key; bản thân lệnh gọi API thật không unit-test được offline)

```bash
python -m primitive_ir_lib.tests.test_vision_client
```

## [MỚI] Đã nối Vision API thật — `vision_client.py`

Cả 2 việc còn ghi ở README cũ đã làm:

- `make_vision_reader()` — `vision_reader` thật gọi Claude Vision API
  (model mặc định `claude-sonnet-4-6`), có retry + upscale ảnh crop quá nhỏ
  + không raise khi lỗi (trả `""`, để downstream xử lý như text không đọc
  được thay vì sập cả pipeline).
- `make_hybrid_cell_reader()` — cho tier-2 (bảng): thử Tesseract từng ô
  trước (rẻ), CHỈ gọi Vision khi Tesseract rỗng hoặc confidence dưới
  ngưỡng (`tesseract_min_confidence`, mặc định 60%).

Dùng qua `demo_pipeline.py --real-vision` (xem trên) hoặc trực tiếp:

```python
from primitive_ir_lib.vision_client import make_vision_reader, make_hybrid_cell_reader
from primitive_ir_lib.text_extraction import extract_text_vision
from primitive_ir_lib.table_extraction import extract_table_cells

reader = make_vision_reader()  # cần ANTHROPIC_API_KEY trong env
raw_texts = extract_text_vision(image, crop_boxes=[...], vision_reader=reader)

cell_reader = make_hybrid_cell_reader(vision_reader=reader)
cells, raw_texts_tier2 = extract_table_cells(image, lines, table_roi, cell_reader=cell_reader)
```

**Lưu ý chi phí/tốc độ**: `make_hybrid_cell_reader` gọi Vision cho TỪNG ô
thất bại (1 API call/ô), không batch — chấp nhận được cho hồ sơ 1-vài
trang/lần như quy mô đăng kiểm thật, nhưng nên cache theo `bbox_px` nếu
chạy lại nhiều lần trên cùng 1 ảnh.

## Việc CHƯA làm (không nằm trong lần này)

- Pattern Recognition (Phase 2) — đọc `primitives[]` sinh ra từ đây, KHÔNG nằm trong scope Phase 1.
