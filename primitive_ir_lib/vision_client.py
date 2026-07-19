"""
vision_client.py — lớp ứng dụng nối `vision_reader`/`cell_reader` (interface
pluggable đã định nghĩa ở text_extraction.py và table_extraction.py) với
Claude Vision API THẬT.

Đây chính là 2 việc còn ghi ở mục "Việc CHƯA làm" của README:
  1. Kết nối vision_reader với Claude Vision API thật (tier 3: ghi chú dài,
     số kích thước xoay — Tesseract benchmark thất bại hoàn toàn, mục 9.2).
  2. Kết nối cell_reader trong tier 2 với Vision cho ô mà Tesseract vẫn
     thất bại (chữ nhỏ/xoay trong bảng nhiều cột).

Cố ý tách khỏi text_extraction.py/table_extraction.py (đúng nguyên tắc đã
ghi trong docstring 2 file đó): logic xử lý ảnh/text thuần tuý phải test
được offline không cần mạng/API key; phần "gọi API thật" nằm ở tầng ứng
dụng, tại đây.

Cài đặt thêm (không nằm trong requirements.txt gốc vì là optional):
    pip install anthropic --break-system-packages

Dùng API key qua biến môi trường ANTHROPIC_API_KEY (SDK tự đọc, không cần
truyền tay) — xem https://docs.claude.com cho cách lấy key.
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Callable, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

Bbox = Tuple[int, int, int, int]

_DEFAULT_PROMPT = (
    "Đọc CHÍNH XÁC chuỗi ký tự trong ảnh này. Ảnh có thể là một số kích "
    "thước kỹ thuật (có thể xoay dọc/ngang), một ô trong bảng thông số, "
    "hoặc một ghi chú kỹ thuật ngắn trên bản vẽ cơ khí/ô tô. "
    "Chỉ trả về ĐÚNG chuỗi ký tự đọc được, không giải thích, không thêm "
    "chữ thừa, không thêm dấu chấm câu ở cuối. Nếu ô trống hoặc không đọc "
    "được, trả về chuỗi rỗng."
)


def _encode_png_b64(crop_bgr: np.ndarray) -> str:
    ok, buf = cv2.imencode(".png", crop_bgr)
    if not ok:
        raise ValueError("Không encode được crop sang PNG (ảnh rỗng hoặc hỏng?)")
    return base64.b64encode(buf).decode("ascii")


def make_vision_reader(
    model: str = "claude-sonnet-4-6",
    prompt: str = _DEFAULT_PROMPT,
    max_tokens: int = 50,
    max_retries: int = 2,
    retry_backoff_s: float = 1.5,
    upscale_below_px: int = 40,
) -> Callable[[np.ndarray], str]:
    """Trả về 1 callable `vision_reader(crop_bgr) -> str` thật, gọi Claude
    Vision API — đúng chữ ký mà `text_extraction.extract_text_vision()` và
    `table_extraction.extract_table_cells(cell_reader=...)` yêu cầu.

    Import `anthropic` lazy bên trong hàm này (không import ở đầu file) để
    phần còn lại của package vẫn chạy được trong môi trường không cài
    `anthropic` (vd sandbox build gốc không có mạng).

    upscale_below_px: nếu cạnh nhỏ nhất của crop nhỏ hơn ngưỡng này, phóng
    to trước khi gửi — Vision đọc chữ rất nhỏ (như số trong ô bảng đã tách,
    hay ghi chú xoay bị crop sát) kém hơn hẳn nếu ảnh gốc quá bé (kinh
    nghiệm benchmark mục 9.2: crop < ~40px cạnh ngắn hay bị đọc sai/rỗng).
    """
    try:
        import anthropic
    except ImportError as exc:
        raise ImportError(
            "Cần cài package 'anthropic' để dùng vision_reader thật: "
            "pip install anthropic --break-system-packages"
        ) from exc

    client = anthropic.Anthropic()  # tự đọc ANTHROPIC_API_KEY từ env

    def _reader(crop_bgr: np.ndarray) -> str:
        if crop_bgr is None or crop_bgr.size == 0:
            return ""

        crop = crop_bgr
        h, w = crop.shape[:2]
        if min(h, w) > 0 and min(h, w) < upscale_below_px:
            scale = upscale_below_px / min(h, w)
            crop = cv2.resize(
                crop, (max(1, int(w * scale)), max(1, int(h * scale))),
                interpolation=cv2.INTER_CUBIC,
            )

        b64 = _encode_png_b64(crop)
        last_err: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": b64,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }],
                )
                text_blocks = [
                    block.text for block in response.content
                    if getattr(block, "type", None) == "text"
                ]
                return "".join(text_blocks).strip()
            except Exception as exc:  # noqa: BLE001 - muốn bắt mọi lỗi API để retry
                last_err = exc
                if attempt < max_retries:
                    logger.warning(
                        "vision_reader: lỗi gọi API (lần %d/%d): %s — thử lại sau %.1fs",
                        attempt + 1, max_retries + 1, exc, retry_backoff_s,
                    )
                    time.sleep(retry_backoff_s)
                else:
                    logger.error("vision_reader: hết lượt retry, bỏ qua crop này: %s", exc)

        # Hết retry mà vẫn lỗi: KHÔNG raise (1 crop lỗi không nên sập cả
        # pipeline) — trả rỗng, để downstream (classify_semantic_role,
        # cross_validate) xử lý như 1 text không đọc được. Ghi log để biết.
        if last_err is not None:
            logger.error("vision_reader: đọc thất bại crop %sx%s: %s", w, h, last_err)
        return ""

    return _reader


def make_hybrid_cell_reader(
    vision_reader: Optional[Callable[[np.ndarray], str]] = None,
    tesseract_min_confidence: int = 60,
    **vision_reader_kwargs,
) -> Callable[[np.ndarray, Bbox], str]:
    """Trả về 1 `cell_reader(image_bgr, bbox) -> str` cho
    `table_extraction.extract_table_cells(cell_reader=...)`, theo chiến
    lược hybrid: thử Tesseract trước (rẻ), CHỈ gọi Vision khi Tesseract
    thất bại hoàn toàn (rỗng) hoặc confidence dưới ngưỡng — đúng mục "Việc
    CHƯA làm" #2 trong README, đồng thời tránh gọi Vision cho MỌI ô (tốn
    tiền/chậm) khi phần lớn ô là số/chữ sạch mà Tesseract đã đọc tốt (đã
    verify ở verify_tier2.py: 6/6 ô đúng chỉ với Tesseract thuần trên ảnh
    tổng hợp — nhưng ảnh scan thật có thể có ô chữ nhỏ/xoay cần Vision).

    Nếu không truyền `vision_reader`, hàm này tự tạo 1 cái qua
    `make_vision_reader(**vision_reader_kwargs)` (yêu cầu ANTHROPIC_API_KEY
    trong env + package `anthropic`).
    """
    from .text_extraction import extract_text_tesseract  # tránh import vòng

    reader = vision_reader if vision_reader is not None else make_vision_reader(**vision_reader_kwargs)

    def _cell_reader(image_bgr: np.ndarray, bbox: Bbox) -> str:
        x0, y0, x1, y1 = (int(round(v)) for v in bbox)
        crop = image_bgr[y0:y1, x0:x1]
        if crop.size == 0:
            return ""

        results = extract_text_tesseract(crop)
        if results:
            content = " ".join(r.content.strip() for r in results if r.content.strip())
            avg_conf = sum(r.confidence for r in results) / len(results) * 100.0
            if content and avg_conf >= tesseract_min_confidence:
                return content
            logger.info(
                "hybrid_cell_reader: Tesseract confidence thấp (%.0f%% < %d%%) hoặc "
                "rỗng cho ô %s -> fallback Vision", avg_conf, tesseract_min_confidence, bbox,
            )
        else:
            logger.info("hybrid_cell_reader: Tesseract không đọc được ô %s -> fallback Vision", bbox)

        return reader(crop)

    return _cell_reader
