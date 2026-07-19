"""
test_line_merging.py — Test merge_collinear_lines() bằng fixture tổng hợp mô
phỏng lại đúng kịch bản lỗi ở mục 5.3 báo cáo kiểm thử Phase 1 (18/07/2026):

  - witness-line của 1 kích thước bị gãy làm 3 mảnh do centerline cắt ngang
    -> PHẢI gộp lại thành 1 line liền mạch.
  - 2 witness-line liền kề của 2 kích thước khác nhau trong 1 chuỗi dimension
    (khoảng trống ranh giới thật ~22px, nhỏ hơn khoảng trống gãy khúc kỹ
    thuật) -> KHÔNG được gộp vào nhau, nhờ neo là vị trí text dimension_value
    nằm giữa 2 line.

Bổ sung (Lớp 1 — "Phương án tổng thể" sau báo cáo): các test
test_tick_mark_* dưới đây kiểm chứng tick-mark/arrowhead detection (dò trên
ảnh gốc, độc lập OCR) hoạt động ĐÚNG như 1 tín hiệu chặn gộp — kể cả khi
KHÔNG có text nào neo giúp (mô phỏng đúng tình huống OCR thất bại mà
text-anchor một mình không xử lý được).
"""

from __future__ import annotations

import cv2
import numpy as np

from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.line_merging import merge_collinear_lines
from primitive_ir_lib.text_extraction import RawText, classify_semantic_role


def _line(p1, p2, id_, confidence=0.9):
    return RawLine(
        id=id_, p1_px=p1, p2_px=p2, confidence=confidence,
        bbox_px=(min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1])),
    )


def _text(content, bbox, id_):
    role, value = classify_semantic_role(content)
    return RawText(
        id=id_, content=content, bbox_px=bbox, rotation_deg=0.0,
        confidence=0.95, source="text_vision", parsed_value=value, semantic_role=role,
    )


def test_merges_broken_witness_line_across_centerline_gap():
    # witness-line của 5500mm bị centerline cắt ngang thành 3 mảnh (gap nhỏ, không có text nào chen giữa)
    l1 = _line((0, 100), (150, 100), "l1")
    l2 = _line((155, 100), (300, 100), "l2")  # gap 5px so với l1
    l3 = _line((304, 100), (500, 100), "l3")  # gap 4px so với l2
    merged = merge_collinear_lines([l1, l2, l3], blocking_texts=[])
    assert len(merged) == 1
    assert merged[0].length_px() == 500.0


def test_does_not_merge_across_dimension_chain_boundary():
    # 2 witness-line liền kề của 2760mm và 1525mm, gap ranh giới thật ~22px,
    # có text "1525" nằm ngay trong khoảng trống đó (đúng vị trí witness-line của chính nó bắt đầu)
    line_2760 = _line((0, 140), (276, 140), "l2760")
    line_1525 = _line((298, 140), (450.5, 140), "l1525")  # gap = 298 - 276 = 22px
    text_2760 = _text("2760", (100, 125, 176, 138), "t2760")
    text_1525 = _text("1525", (280, 125, 316, 138), "t1525")  # tâm bbox ~ (298, 131.5), rơi vào gap [276,298]

    merged = merge_collinear_lines(
        [line_2760, line_1525],
        blocking_texts=[text_2760, text_1525],
        gap_tol_px=25.0,  # >= 22px, nếu không có anchor sẽ bị gộp nhầm (đúng lỗi mục 5.3)
    )
    ids = sorted(m.id for m in merged)
    assert len(merged) == 2, f"Không được gộp qua ranh giới chuỗi dimension, nhưng ra: {ids}"
    assert ids == ["l1525", "l2760"]


def test_merges_when_no_text_blocks_even_with_larger_gap_but_still_within_tol():
    # Không có text nào chen giữa (không phải ranh giới chuỗi) -> vẫn gộp như hành vi gốc
    l1 = _line((0, 200), (100, 200), "a")
    l2 = _line((115, 200), (250, 200), "b")  # gap 15px, không text
    merged = merge_collinear_lines([l1, l2], blocking_texts=[], gap_tol_px=25.0)
    assert len(merged) == 1
    assert merged[0].length_px() == 250.0


def test_does_not_merge_lines_with_different_angle():
    horiz = _line((0, 0), (100, 0), "h")
    vert = _line((100, 0), (100, 100), "v")
    merged = merge_collinear_lines([horiz, vert], blocking_texts=[])
    assert len(merged) == 2


def test_does_not_merge_parallel_lines_offset_perpendicular():
    l1 = _line((0, 0), (100, 0), "top")
    l2 = _line((105, 20), (200, 20), "bottom")  # cùng phương ngang nhưng lệch trục 20px
    merged = merge_collinear_lines([l1, l2], blocking_texts=[], perp_tol_px=6.0)
    assert len(merged) == 2


def _canvas_with_two_witness_lines_and_tick_marks(gap_start=276, gap_end=298, y=140):
    """Ảnh tổng hợp: 2 witness-line ngang với tick-mark chéo ở 2 đầu đối
    diện quanh khoảng trống ranh giới — KHÔNG có text nào (mô phỏng OCR thất
    bại), chỉ tick-mark là tín hiệu duy nhất có thể chặn gộp."""
    img = np.full((220, 500, 3), 255, dtype=np.uint8)
    cv2.line(img, (0, y), (gap_start, y), (0, 0, 0), 2)
    cv2.line(img, (gap_end, y), (450, y), (0, 0, 0), 2)
    # tick-mark chéo ở đầu mút bên phải của line trái (ranh giới thật)
    cv2.line(img, (gap_start - 8, y + 8), (gap_start + 8, y - 8), (0, 0, 0), 2)
    # tick-mark chéo ở đầu mút bên trái của line phải (ranh giới thật)
    cv2.line(img, (gap_end - 8, y + 8), (gap_end + 8, y - 8), (0, 0, 0), 2)
    return img


def test_tick_mark_blocks_merge_even_without_any_blocking_text():
    # Không có blocking_texts (OCR "thất bại") -> nếu chỉ có Lớp 2 (text-anchor)
    # sẽ gộp nhầm y hệt lỗi mục 5.3. Với image_bgr + tick-mark (Lớp 1), vẫn
    # phải KHÔNG gộp.
    img = _canvas_with_two_witness_lines_and_tick_marks()
    line_left = _line((0, 140), (276, 140), "l_left")
    line_right = _line((298, 140), (450, 140), "l_right")

    merged = merge_collinear_lines(
        [line_left, line_right],
        blocking_texts=[],  # cố tình để trống -> chỉ tick-mark có thể cứu
        image_bgr=img,
        gap_tol_px=25.0,
    )
    ids = sorted(m.id for m in merged)
    assert len(merged) == 2, f"Tick-mark phải chặn gộp dù không có text neo, nhưng ra: {ids}"
    assert ids == ["l_left", "l_right"]


def test_without_image_bgr_falls_back_to_gap_tol_and_merges():
    # Cùng hình học như trên nhưng KHÔNG truyền image_bgr và KHÔNG có
    # blocking_texts -> không còn tín hiệu nào chặn -> gộp theo gap_tol_px cũ
    # (đúng hành vi rơi về baseline khi thiếu cả 2 lớp tín hiệu).
    line_left = _line((0, 140), (276, 140), "l_left")
    line_right = _line((298, 140), (450, 140), "l_right")

    merged = merge_collinear_lines(
        [line_left, line_right],
        blocking_texts=[],
        image_bgr=None,
        gap_tol_px=25.0,
    )
    assert len(merged) == 1


def test_tick_mark_does_not_block_technical_break_without_tick_marks():
    # Ảnh chỉ có 1 line liền bị centerline cắt ngang (không có tick-mark ở
    # chỗ gãy) -> tick-mark detection không tìm thấy gì ở đó -> vẫn gộp bình
    # thường như gãy khúc kỹ thuật (không có dương tính giả).
    img = np.full((220, 500, 3), 255, dtype=np.uint8)
    cv2.line(img, (0, 100), (150, 100), (0, 0, 0), 2)
    cv2.line(img, (155, 100), (300, 100), (0, 0, 0), 2)
    # vẽ 1 centerline mỏng cắt ngang tại vùng gap để mô phỏng thực tế, không
    # phải tick-mark (không chéo, đây là 1 đường DỌC cắt ngang qua gap)
    cv2.line(img, (152, 60), (152, 140), (0, 0, 0), 1)

    l1 = _line((0, 100), (150, 100), "a")
    l2 = _line((155, 100), (300, 100), "b")
    merged = merge_collinear_lines([l1, l2], blocking_texts=[], image_bgr=img, gap_tol_px=25.0)
    assert len(merged) == 1
