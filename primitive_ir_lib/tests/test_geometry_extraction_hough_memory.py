import numpy as np

from primitive_ir_lib import geometry_extraction


def test_extract_circles_uses_coarser_accumulator_for_large_images(monkeypatch):
    calls = []

    def record_hough_circles(image, method, **kwargs):
        calls.append((image.shape, method, kwargs))
        return None

    monkeypatch.setattr(geometry_extraction.cv2, "HoughCircles", record_hough_circles)

    geometry_extraction.extract_circles(np.zeros((2001, 2000, 3), dtype=np.uint8))

    assert len(calls) == 1
    assert calls[0][2]["dp"] == 2


def test_extract_circles_preserves_full_resolution_for_small_images(monkeypatch):
    calls = []

    def record_hough_circles(image, method, **kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.setattr(geometry_extraction.cv2, "HoughCircles", record_hough_circles)

    geometry_extraction.extract_circles(np.zeros((1000, 1000, 3), dtype=np.uint8))

    assert len(calls) == 1
    assert calls[0]["dp"] == 1


def test_extract_circles_finds_large_image_circle_after_accumulator_scaling():
    image = np.zeros((2001, 2000, 3), dtype=np.uint8)
    geometry_extraction.cv2.circle(image, (1000, 1000), 100, (255, 255, 255), 3)

    circles = geometry_extraction.extract_circles(image, param2=40, min_dist=150)

    assert any(
        abs(circle.center_px[0] - 1000) <= 3
        and abs(circle.center_px[1] - 1000) <= 3
        and abs(circle.radius_px - 100) <= 5
        for circle in circles
    )
