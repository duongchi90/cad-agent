"""
text_extraction.py — Text/Label Extraction theo chiến lược 3 tier đã benchmark
ở mục 9.2 của tài liệu tổng hợp:

  tier 1 (title block / mã bản vẽ sạch)      -> Tesseract, rẻ, đủ dùng
  tier 2 (bảng nhiều cột)                     -> cần tách ô theo lưới trước
                                                  (CHƯA làm ở module này, xem
                                                  action item mục 8 — grid-cell
                                                  splitting cần geometry của
                                                  line-detection làm input)
  tier 3 (ghi chú dài / số kích thước xoay)  -> Vision (VLM), Tesseract thất
                                                  bại hoàn toàn ở benchmark thật

QUAN TRỌNG: hàm extract_text_vision() KHÔNG tự gọi API — nó nhận vào một
callable `vision_reader(crop_bgr) -> str` do người gọi cung cấp. Lý do:
môi trường build package này chạy sandbox không có mạng, và việc gọi Claude
Vision API cần được thực hiện ở tầng ứng dụng (có API key/kết nối thật), tách
biệt khỏi phần logic xử lý ảnh/text thuần túy ở đây. Xem demo_pipeline.py để
biết cách nối 1 vision_reader thật (dùng Anthropic API) vào chỗ này.
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import numpy as np
import pytesseract

from .models import new_id, SemanticRole

Bbox = Tuple[int, int, int, int]  # (x_min, y_min, x_max, y_max) pixel


@dataclass
class RawText:
    id: str
    content: str
    bbox_px: Bbox
    rotation_deg: float
    confidence: float
    source: str  # "text_tesseract" | "text_vision"
    parsed_value: Optional[float] = None
    semantic_role: SemanticRole = "unknown"


# ---------------------------------------------------------- semantic role --
_DRAWING_CODE_RE = re.compile(r"^[A-Z]{1,4}[-_][A-Z0-9]+([-_/][A-Z0-9]+)*$")
_PURE_NUMBER_RE = re.compile(r"^\d{2,5}([.,]\d+)?$")


def classify_semantic_role(content: str) -> Tuple[SemanticRole, Optional[float]]:
    """Phân loại RULE-BASED (không AI) — cố ý đơn giản, vì đây chỉ là gợi ý
    ban đầu. Vai trò cuối cùng còn phải chờ cross_validate() xác nhận (đối
    với dimension_value) hoặc Pattern Recognition (Phase 2) xác nhận thêm."""
    text = content.strip()

    if _PURE_NUMBER_RE.match(text):
        value = float(text.replace(",", "."))
        return "dimension_value", value

    if _DRAWING_CODE_RE.match(text):
        return "drawing_code", None

    if len(text) > 25 or (" " in text and len(text.split()) >= 4):
        return "general_note", None

    return "unknown", None


# -------------------------------------------------------------- tier 1: --
def extract_text_tesseract(
    image_bgr: np.ndarray,
    roi_boxes: Optional[List[Bbox]] = None,
    min_confidence: int = 40,
    lang: str = "eng",
) -> List[RawText]:
    """Tesseract trên toàn ảnh hoặc trên từng ROI đã khoanh (vd vùng title
    block). Dùng cho tier 1 (mục 9.2): mã bản vẽ, title block sạch — KHÔNG
    dùng hàm này cho ghi chú dài/số xoay, benchmark thật cho thấy thất bại
    nặng (xem mục 9.2 dòng "GHI CHÚ/YÊU CẦU KỸ THUẬT" và "số kích thước xoay").

    LƯU Ý VẬN HÀNH: mặc định lang='eng' vì môi trường build package này chỉ
    có gói 'eng' cài sẵn (kiểm tra bằng `tesseract --list-langs`). Với dữ
    liệu thật có nhãn tiếng Việt trong title block (vd "SỐ LƯỢNG", "VẬT
    LIỆU"), nên cài thêm `tesseract-ocr-vie` (`apt-get install
    tesseract-ocr-vie`) và truyền lang='vie+eng'. Mã bản vẽ/số liệu thuần
    (vd 'TP-TL-A001/07/26') không cần gói 'vie' vì không có dấu.
    """
    if not roi_boxes:
        # Xác nhận bởi mục 4 báo cáo kiểm thử Phase 1 (18/07/2026): quét
        # Tesseract toàn ảnh 1600x900 chỉ ra 21 mảnh text, gần như toàn rác
        # do nét vẽ dày đặc — chỉ đúng thiết kế khi có ROI (vd vùng khung
        # tên). Cảnh báo runtime để tránh gọi nhầm trên ảnh bản vẽ đầy đủ.
        warnings.warn(
            "extract_text_tesseract() được gọi không có roi_boxes trên ảnh "
            f"{image_bgr.shape[1]}x{image_bgr.shape[0]}px — theo benchmark thật "
            "(mục 4 báo cáo kiểm thử Phase 1), quét toàn ảnh bản vẽ CAD dễ ra "
            "kết quả rác. Nên khoanh ROI (vd vùng khung tên) trước khi gọi.",
            stacklevel=2,
        )
    regions = roi_boxes if roi_boxes else [(0, 0, image_bgr.shape[1], image_bgr.shape[0])]
    results: List[RawText] = []

    for (x0, y0, x1, y1) in regions:
        crop = image_bgr[y0:y1, x0:x1]
        if crop.size == 0:
            continue
        data = pytesseract.image_to_data(
            crop, lang=lang, output_type=pytesseract.Output.DICT,
            config="--psm 6",
        )
        n = len(data["text"])
        # Gộp các từ trên cùng 1 dòng (block_num, par_num, line_num giống nhau)
        lines: dict = {}
        for i in range(n):
            word = data["text"][i].strip()
            conf = int(data["conf"][i]) if data["conf"][i] not in ("-1", "") else -1
            if not word or conf < min_confidence:
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(key, {"words": [], "confs": [], "boxes": []})
            lines[key]["words"].append(word)
            lines[key]["confs"].append(conf)
            lines[key]["boxes"].append((
                data["left"][i], data["top"][i],
                data["left"][i] + data["width"][i], data["top"][i] + data["height"][i],
            ))

        for key, group in lines.items():
            content = " ".join(group["words"])
            avg_conf = sum(group["confs"]) / len(group["confs"]) / 100.0
            xs0 = min(b[0] for b in group["boxes"]) + x0
            ys0 = min(b[1] for b in group["boxes"]) + y0
            xs1 = max(b[2] for b in group["boxes"]) + x0
            ys1 = max(b[3] for b in group["boxes"]) + y0
            role, value = classify_semantic_role(content)
            results.append(RawText(
                id=new_id("rawtext"),
                content=content,
                bbox_px=(xs0, ys0, xs1, ys1),
                rotation_deg=0.0,
                confidence=round(avg_conf, 3),
                source="text_tesseract",
                parsed_value=value,
                semantic_role=role,
            ))
    return results


# -------------------------------------------------------------- tier 3: --
def extract_text_vision(
    image_bgr: np.ndarray,
    crop_boxes: List[Bbox],
    vision_reader: Callable[[np.ndarray], str],
    rotations_deg: Optional[List[float]] = None,
    confidence: float = 0.95,
) -> List[RawText]:
    """Dùng cho tier 3 (mục 9.2): ghi chú dài, chữ nhỏ, số kích thước xoay —
    nơi Tesseract benchmark thất bại hoàn toàn hoặc sai cả câu.

    `vision_reader` là callable do tầng ứng dụng cung cấp, nhận vào 1 crop
    ảnh (numpy array BGR) và trả về chuỗi text đã đọc. Tách rời khỏi phần
    gọi API thật (xem demo_pipeline.py) để module này test được offline.

    confidence mặc định 0.95 vì benchmark thật ở mục 9.2 cho thấy Vision đọc
    "gần như tuyệt đối" trên các case Tesseract thất bại — nhưng nên hạ giá
    trị này nếu chưa cross-validate được (xem cross_validation.py: confidence
    lý tưởng nên được nâng lên 1.0 chỉ SAU khi cross_validate xác nhận khớp).
    """
    if rotations_deg is None:
        rotations_deg = [0.0] * len(crop_boxes)
    if len(rotations_deg) != len(crop_boxes):
        raise ValueError("rotations_deg phải cùng độ dài với crop_boxes")

    results: List[RawText] = []
    for (x0, y0, x1, y1), rot in zip(crop_boxes, rotations_deg):
        crop = image_bgr[y0:y1, x0:x1]
        if crop.size == 0:
            continue
        content = vision_reader(crop).strip()
        role, value = classify_semantic_role(content)
        results.append(RawText(
            id=new_id("rawtext"),
            content=content,
            bbox_px=(x0, y0, x1, y1),
            rotation_deg=rot,
            confidence=confidence,
            source="text_vision",
            parsed_value=value,
            semantic_role=role,
        ))
    return results
