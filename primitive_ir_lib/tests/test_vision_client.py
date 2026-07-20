"""
test_vision_client.py — test make_hybrid_cell_reader() KHÔNG cần mạng/API
key: dùng vision_reader giả (fake) để kiểm chứng đúng LOGIC fallback
(Tesseract trước, Vision chỉ khi cần), không test bản thân lệnh gọi API
thật (việc đó cần key thật, xem docstring vision_client.py).
"""

from __future__ import annotations


import numpy as np

from primitive_ir_lib.vision_client import make_hybrid_cell_reader


def _make_text_crop(text: str, w: int = 200, h: int = 80) -> np.ndarray:
    """Tạo 1 ảnh BGR trắng có chữ đen rõ ràng — Tesseract đọc tốt được."""
    import cv2
    img = np.full((h, w, 3), 255, dtype=np.uint8)
    cv2.putText(img, text, (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 0), 3)
    return img


def _blank_crop(w: int = 60, h: int = 60) -> np.ndarray:
    """Ảnh trắng tinh — Tesseract chắc chắn đọc ra rỗng."""
    return np.full((h, w, 3), 255, dtype=np.uint8)


def test_hybrid_reader_uses_tesseract_when_confident():
    calls = []

    def fake_vision_reader(crop_bgr):
        calls.append(crop_bgr)
        return "SHOULD_NOT_BE_CALLED"

    reader = make_hybrid_cell_reader(vision_reader=fake_vision_reader, tesseract_min_confidence=1)
    image = _make_text_crop("4200")
    content = reader(image, (0, 0, image.shape[1], image.shape[0]))

    assert "4200" in content, f"Tesseract lẽ ra đọc được '4200', got: {content!r}"
    assert len(calls) == 0, "Không nên fallback sang Vision khi Tesseract đủ confidence"
    print("OK   test_hybrid_reader_uses_tesseract_when_confident")


def test_hybrid_reader_falls_back_to_vision_when_tesseract_empty():
    calls = []

    def fake_vision_reader(crop_bgr):
        calls.append(crop_bgr)
        return "VISION_RESULT"

    reader = make_hybrid_cell_reader(vision_reader=fake_vision_reader, tesseract_min_confidence=60)
    image = _blank_crop()
    content = reader(image, (0, 0, image.shape[1], image.shape[0]))

    assert content == "VISION_RESULT"
    assert len(calls) == 1, "Phải fallback sang Vision khi Tesseract không đọc được gì"
    print("OK   test_hybrid_reader_falls_back_to_vision_when_tesseract_empty")


def test_hybrid_reader_falls_back_when_confidence_below_threshold():
    calls = []

    def fake_vision_reader(crop_bgr):
        calls.append(crop_bgr)
        return "VISION_RESULT"

    # threshold cực cao (999) ép mọi kết quả Tesseract bị coi là "confidence thấp"
    reader = make_hybrid_cell_reader(vision_reader=fake_vision_reader, tesseract_min_confidence=999)
    image = _make_text_crop("1900")
    content = reader(image, (0, 0, image.shape[1], image.shape[0]))

    assert content == "VISION_RESULT"
    assert len(calls) == 1
    print("OK   test_hybrid_reader_falls_back_when_confidence_below_threshold")


def test_hybrid_reader_empty_bbox_returns_empty_without_calling_vision():
    calls = []

    def fake_vision_reader(crop_bgr):
        calls.append(crop_bgr)
        return "SHOULD_NOT_BE_CALLED"

    reader = make_hybrid_cell_reader(vision_reader=fake_vision_reader)
    image = _make_text_crop("4200")
    # bbox rỗng (x0==x1)
    content = reader(image, (5, 5, 5, 50))

    assert content == ""
    assert len(calls) == 0
    print("OK   test_hybrid_reader_empty_bbox_returns_empty_without_calling_vision")


_TESTS = [
    test_hybrid_reader_uses_tesseract_when_confident,
    test_hybrid_reader_falls_back_to_vision_when_tesseract_empty,
    test_hybrid_reader_falls_back_when_confidence_below_threshold,
    test_hybrid_reader_empty_bbox_returns_empty_without_calling_vision,
]


def run_all():
    passed = 0
    for t in _TESTS:
        t()
        passed += 1
    print(f"\n{passed}/{len(_TESTS)} test PASS")


if __name__ == "__main__":
    run_all()
