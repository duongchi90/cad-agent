"""
demo_pipeline.py — Chạy end-to-end: tạo ảnh test tổng hợp -> geometry
extraction -> text extraction (tesseract + vision + tier2 bảng lưới) ->
calibration -> cross-validation -> PrimitiveIRDocument -> validate -> lưu
JSON.

VÌ SAO DÙNG ẢNH TỔNG HỢP THAY VÌ ẢNH SCAN THẬT: phiên làm việc này không có
ảnh scan thật đính kèm. Ảnh test dựng tay mô phỏng đúng 3 case đã benchmark ở
mục 9.2/9.4 (số kích thước "1700" xoay dọc cạnh view, title block dạng mã
'TP-TL-A001/07/26', bảng thông số 2x3 ô) để chứng minh code chạy đúng logic,
KHÔNG phải để chứng minh lại độ chính xác OCR/Vision trên ảnh scan thật (việc
đó cần ảnh thật).

CHỖ CẦN THAY BẰNG API THẬT: hàm `mock_vision_reader()` bên dưới đứng thay
cho lệnh gọi Claude Vision API thật. Ở dự án thật, thay hàm này bằng 1 lệnh
gọi Anthropic API gửi ảnh crop (base64) + prompt "đọc chính xác chuỗi ký tự
trong ảnh này, không diễn giải" — xem đoạn code mẫu (đã comment) trong hàm.
"""

from __future__ import annotations

import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .assemble import build_document
from .calibration import auto_estimate_calibration
from .cross_validation import cross_validate
from .geometry_extraction import extract_raw_geometry
from .io_utils import save_document
from .table_extraction import extract_table_cells
from .text_extraction import extract_text_tesseract, extract_text_vision
from .validator import validate_document

IMG_W, IMG_H = 900, 700

# Vùng bảng thông số 2 hàng x 3 cột (tier 2), đặt ở góc trên-phải, tách biệt
# khung/lỗ bu-lông (x<=750,y<=550) và title block (y>=640) để không đè nhau.
TABLE_ROI = (560, 40, 880, 160)


def make_synthetic_drawing() -> np.ndarray:
    """Dựng ảnh mô phỏng: 1 khung chữ nhật (2 line), 1 lỗ bu-lông (circle),
    1 số kích thước '1700' xoay dọc cạnh view (case tier 3 — mục 9.2),
    1 mã bản vẽ title block (case tier 1 — mục 9.2), 1 bảng thông số 2x3 ô
    (case tier 2 — mục 4/9.2, "cần tách ô theo lưới trước khi OCR")."""
    img = Image.new("RGB", (IMG_W, IMG_H), "white")
    draw = ImageDraw.Draw(img)

    # Khung: 1 line dọc (đại diện cạnh view, dài 500px <-> sẽ gán = 1700mm)
    #        1 line ngang (đại diện đáy khung)
    draw.line([(150, 50), (150, 550)], fill="black", width=3)
    draw.line([(150, 550), (750, 550)], fill="black", width=3)
    # Lỗ bu-lông
    draw.ellipse([(430, 280), (470, 320)], outline="black", width=3)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        font_cell = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except OSError:
        font = ImageFont.load_default()
        font_small = font
        font_cell = font

    # Số kích thước "1700" — vẽ ngang trên layer riêng rồi xoay 90 độ,
    # dán cạnh line dọc (mô phỏng đúng case "số kích thước xoay dọc" mục 9.2)
    txt_layer = Image.new("RGBA", (120, 40), (255, 255, 255, 0))
    ImageDraw.Draw(txt_layer).text((0, 0), "1700", fill="black", font=font)
    txt_rot = txt_layer.rotate(90, expand=True)
    img.paste(txt_rot, (95, 250), txt_rot)

    # Title block: mã bản vẽ sạch (tier 1)
    draw.text((580, 640), "TP-TL-A001/07/26", fill="black", font=font_small)

    # Bảng thông số 2x3 (tier 2): lưới kẻ + nội dung ô sát cạnh nhau — cố ý
    # đặt số/nhãn ở khoảng cách hẹp để tái hiện đúng nguy cơ "xáo trộn khi
    # đọc nguyên khối" đã ghi nhận ở mục 9.2, buộc phải tách ô mới đọc đúng.
    x0, y0, x1, y1 = TABLE_ROI
    xs = [x0, x0 + (x1 - x0) / 3, x0 + 2 * (x1 - x0) / 3, x1]
    ys = [y0, (y0 + y1) / 2, y1]
    for y in ys:
        draw.line([(x0, y), (x1, y)], fill="black", width=2)
    for x in xs:
        draw.line([(x, y0), (x, y1)], fill="black", width=2)
    cell_values = [["DAI", "RONG", "CAO"], ["4200", "1900", "2100"]]
    for row in range(2):
        for col in range(3):
            cx = xs[col] + 8
            cy = ys[row] + 8
            draw.text((cx, cy), cell_values[row][col], fill="black", font=font_cell)

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def mock_vision_reader(crop_bgr: np.ndarray) -> str:
    """ĐỨNG THAY cho lệnh gọi Claude Vision API thật.

    Code thật (KHÔNG chạy được trong sandbox này vì không có mạng/API key)
    sẽ tương tự:

        import base64, requests
        _, buf = cv2.imencode(".png", crop_bgr)
        b64 = base64.b64encode(buf).decode()
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=50,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64",
                        "media_type": "image/png", "data": b64}},
                    {"type": "text", "text": (
                        "Đọc CHÍNH XÁC chuỗi ký tự trong ảnh này (có thể là "
                        "số kích thước xoay hoặc chữ nhỏ). Chỉ trả về đúng "
                        "chuỗi đọc được, không giải thích, không thêm chữ."
                    )},
                ],
            }],
        )
        return response.content[0].text.strip()

    Ở demo này, để test offline, ta chỉ OCR bằng Tesseract trên ảnh ĐÃ XOAY
    LẠI cho thẳng — mô phỏng việc 1 con người/VLM đọc đúng, KHÔNG dùng để
    chứng minh độ chính xác Vision thật (việc đó cần benchmark trên ảnh scan
    thật + API thật, đã làm ở mục 9.2 của tài liệu tổng hợp).
    """
    import pytesseract

    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    # thử cả 4 góc xoay, chọn kết quả DÀI NHẤT (không phải kết quả không-rỗng
    # đầu tiên — 1 góc sai vẫn có thể đọc ra 1 ký tự rác thay vì rỗng thật sự)
    candidates = []
    for angle in (0, 90, 180, 270):
        rotated = np.rot90(gray, k=angle // 90)
        text = pytesseract.image_to_string(rotated, config="--psm 7 -c tessedit_char_whitelist=0123456789").strip()
        if text:
            candidates.append(text)
    return max(candidates, key=len) if candidates else ""


def run_demo(output_dir="/home/claude/demo_output", use_real_vision=False) -> dict:
    """use_real_vision=True: nối vision_reader/cell_reader thật (vision_client.py)
    thay cho mock_vision_reader() — cần `pip install anthropic` + biến môi
    trường ANTHROPIC_API_KEY. Nếu thiếu 1 trong 2 điều kiện đó, tự động log
    cảnh báo và rơi về mock (không làm sập demo)."""
    os.makedirs(output_dir, exist_ok=True)

    vision_reader = mock_vision_reader
    tier2_cell_reader = None  # None -> extract_table_cells tự dùng Tesseract mặc định
    if use_real_vision:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("[vision] --real-vision được yêu cầu nhưng thiếu ANTHROPIC_API_KEY "
                  "trong env -> dùng lại mock_vision_reader()")
        else:
            try:
                from .vision_client import make_vision_reader, make_hybrid_cell_reader
                vision_reader = make_vision_reader()
                tier2_cell_reader = make_hybrid_cell_reader(vision_reader=vision_reader)
                print("[vision] dùng Claude Vision API thật (vision_client.py)")
            except ImportError as exc:
                print(f"[vision] {exc} -> dùng lại mock_vision_reader()")

    # 1) Ảnh test tổng hợp
    image = make_synthetic_drawing()
    cv2.imwrite(os.path.join(output_dir, "synthetic_test_drawing.png"), image)

    # 2) Geometry extraction (Canny + Hough) — pixel space
    raw_geom = extract_raw_geometry(image, hough_threshold=50, min_line_length=80, max_line_gap=5)
    print(f"[geometry] tìm được {len(raw_geom.lines)} line, {len(raw_geom.circles)} circle")

    # 3) Text extraction — tier 1 (Tesseract) trên vùng title block
    title_block_roi = [(500, 610, 900, 680)]
    raw_texts_tier1 = extract_text_tesseract(image, roi_boxes=title_block_roi)
    print(f"[text-tier1/tesseract] đọc được: {[t.content for t in raw_texts_tier1]}")

    # 3b) Thử Tesseract trực tiếp trên vùng số kích thước xoay — để TỰ KIỂM
    #     CHỨNG lại đúng hiện tượng đã ghi nhận ở mục 9.2 (Tesseract thất bại
    #     với text xoay), KHÔNG phải bước cần thiết trong pipeline thật.
    rotated_dim_roi = (90, 245, 220, 400)
    tesseract_on_rotated = extract_text_tesseract(image, roi_boxes=[rotated_dim_roi])
    print(f"[kiểm chứng mục 9.2] Tesseract đọc trực tiếp text xoay -> "
          f"{[t.content for t in tesseract_on_rotated] or '(THẤT BẠI - rỗng, đúng như benchmark thật)'}")

    # 4) Text extraction — tier 3 (Vision) cho số kích thước xoay
    raw_texts_tier3 = extract_text_vision(
        image,
        crop_boxes=[rotated_dim_roi],
        rotations_deg=[90.0],
        vision_reader=vision_reader,
    )
    print(f"[text-tier3/vision] đọc được: {[(t.content, t.semantic_role) for t in raw_texts_tier3]}")

    # 4b) Text extraction — tier 2 (tách ô theo lưới) cho bảng thông số.
    #     KHÔNG chạy lại Hough riêng: dùng lại raw_geom.lines đã có ở bước 2.
    table_cells, raw_texts_tier2 = extract_table_cells(
        image, raw_geom.lines, TABLE_ROI, cell_reader=tier2_cell_reader,
    )
    print(f"[text-tier2/table-grid] lưới phát hiện {len(table_cells)} ô, "
          f"đọc được: {[(t.content, t.semantic_role) for t in raw_texts_tier2]}")

    raw_texts = raw_texts_tier1 + raw_texts_tier3 + raw_texts_tier2

    # 5) Calibration — tự động tìm 1 cặp (text dimension, line gần nhất)
    calibration = auto_estimate_calibration(raw_texts, raw_geom.lines, image_height_px=IMG_H)
    if calibration is None:
        raise RuntimeError("Không tự động ước lượng được calibration — cần method='manual_override'")
    print(f"[calibration] {calibration.reference_note}")

    # 6) Cross-validation (đúng nguyên tắc mục 7)
    #    Truyền image_bgr để merge_collinear_lines() bên trong dùng được
    #    tick-mark/arrowhead detection (Lớp 1, ưu tiên hơn text-anchor) khi
    #    gộp witness-line gãy khúc — xem line_merging.py / tick_mark_detection.py.
    cvs = cross_validate(raw_texts, raw_geom.lines, calibration, threshold_percent=3.0, image_bgr=image)
    for cv in cvs:
        print(f"[cross-validate] text={cv.text_value} measured={cv.geometry_measured_length} "
              f"delta%={cv.delta_percent} status={cv.status}")

    # 7) Assemble PrimitiveIRDocument đầy đủ
    doc = build_document(
        file_name="synthetic_test_drawing.png",
        page_index=0,
        image_width_px=IMG_W,
        image_height_px=IMG_H,
        calibration=calibration,
        raw_lines=raw_geom.lines,
        raw_circles=raw_geom.circles,
        raw_texts=raw_texts,
    )
    doc.cross_validations = cvs

    # 8) Validate nhẹ theo schema (xem validator.py)
    doc_dict = doc.to_dict()
    errors = validate_document(doc_dict)
    if errors:
        print("[validate] LỖI SCHEMA:")
        for e in errors:
            print("   -", e)
    else:
        print("[validate] OK — document khớp các ràng buộc chính của primitive_ir.schema.json")

    # 9) Lưu JSON
    out_path = os.path.join(output_dir, "primitive_ir_demo_output.json")
    save_document(doc, out_path)
    print(f"[save] đã lưu {out_path} ({len(doc.primitives)} primitives, {len(doc.cross_validations)} cross_validations)")

    return doc_dict


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--real-vision", action="store_true",
        help="Dùng Claude Vision API thật (cần `pip install anthropic` + "
             "biến môi trường ANTHROPIC_API_KEY) thay vì mock_vision_reader().",
    )
    args = parser.parse_args()
    run_demo(use_real_vision=args.real_vision)
