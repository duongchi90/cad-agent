import numpy as np

from primitive_ir_lib import geometry_extraction


def test_extract_circles_tiles_large_images_before_hough(monkeypatch):
    calls = []

    def record_hough_circles(image, method, **kwargs):
        calls.append((image.shape, method, kwargs))
        return None

    monkeypatch.setattr(geometry_extraction.cv2, "HoughCircles", record_hough_circles)

    geometry_extraction.extract_circles(np.zeros((2100, 2000, 3), dtype=np.uint8))

    assert len(calls) > 1
    assert all(shape[0] * shape[1] <= 4_000_000 for shape, _, _ in calls)
    assert all(kwargs["dp"] == 1 for _, _, kwargs in calls)


def test_extract_circles_preserves_single_full_resolution_call_for_small_images(monkeypatch):
    calls = []

    def record_hough_circles(image, method, **kwargs):
        calls.append((image.shape, kwargs))
        return None

    monkeypatch.setattr(geometry_extraction.cv2, "HoughCircles", record_hough_circles)

    geometry_extraction.extract_circles(np.zeros((1000, 1000, 3), dtype=np.uint8))

    assert len(calls) == 1
    assert calls[0][0] == (1000, 1000)
    assert calls[0][1]["dp"] == 1


def test_extract_circles_translates_and_deduplicates_overlap_results(monkeypatch):
    calls = []

    def record_hough_circles(image, method, **kwargs):
        calls.append((image.shape, kwargs))
        if len(calls) == 1:
            return np.array([[[1590.0, 500.0, 40.0]]], dtype=np.float32)
        if len(calls) == 2:
            return np.array([[[190.0, 500.0, 40.0]]], dtype=np.float32)
        return None

    monkeypatch.setattr(geometry_extraction.cv2, "HoughCircles", record_hough_circles)

    circles = geometry_extraction.extract_circles(
        np.zeros((1000, 4500, 3), dtype=np.uint8),
        min_dist=20,
    )

    assert len(calls) > 1
    assert len(circles) == 1
    assert circles[0].center_px == (1590.0, 500.0)
    assert circles[0].radius_px == 40.0


def test_extract_circles_finds_large_image_circle_with_tiled_hough():
    image = np.zeros((2001, 2000, 3), dtype=np.uint8)
    geometry_extraction.cv2.circle(image, (1000, 1000), 100, (255, 255, 255), 3)

    circles = geometry_extraction.extract_circles(image, param2=40, min_dist=150)

    assert any(
        abs(circle.center_px[0] - 1000) <= 3
        and abs(circle.center_px[1] - 1000) <= 3
        and abs(circle.radius_px - 100) <= 5
        for circle in circles
    )
