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
import json
import numpy as np
from pathlib import Path

from primitive_ir_lib.geometry_extraction import RawLine, extract_raw_geometry
from primitive_ir_lib.line_merging import merge_collinear_lines
from primitive_ir_lib.line_merging import _source_dash_gap_intervals
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


def test_internal_witness_barrier_survives_overlapping_hough_segments():
    """A long fused detection must not bridge its own witness split via overlaps."""
    image = np.full((220, 420, 3), 255, dtype=np.uint8)
    cv2.line(image, (20, 100), (380, 100), (0, 0, 0), 2)
    cv2.line(image, (200, 78), (200, 122), (0, 0, 0), 1)

    merged = merge_collinear_lines(
        [
            _line((20, 100), (380, 100), "long"),
            _line((20, 100), (225, 100), "left-overlap"),
            _line((195, 100), (380, 100), "right-overlap"),
        ],
        blocking_texts=[],
        image_bgr=image,
        use_tick_mark_detection=False,
    )

    segments = sorted(
        (round(min(line.p1_px[0], line.p2_px[0])), round(max(line.p1_px[0], line.p2_px[0])))
        for line in merged
    )
    assert len(segments) == 2, segments
    assert segments[0][1] == segments[1][0]
    assert abs(segments[0][1] - 200) <= 3


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


def test_integrated_merger_preserves_cadenced_c04_dash_pattern():
    fixture = Path(__file__).parent / "fixtures" / "C04_DASHED_HIDDEN_LINE.png"
    image = cv2.imread(str(fixture))
    metadata = json.loads(fixture.with_suffix(".json").read_text(encoding="utf-8"))
    assert image is not None
    for preset in ("default", "real_scan_tuned_v1"):
        raw = extract_raw_geometry(image, preset=preset).lines
        merged = merge_collinear_lines(raw, image_bgr=image)

        assert len(raw) == 8
        assert len(merged) == len(raw), f"{preset} joined regular source-supported dashes"
        expected = {
            line.id: (line.p1_px, line.p2_px, line.confidence, line.bbox_px)
            for line in raw
        }
        actual = {
            line.id: (line.p1_px, line.p2_px, line.confidence, line.bbox_px)
            for line in merged
        }
        assert actual == expected, f"{preset} changed source segment identity or geometry"
        for gap in metadata["ground_truth_geometry"]["forbidden_gap_intervals"]:
            assert not any(
                abs((line.p1_px[0] + line.p2_px[0]) / 2 - gap["x_center"]) <= gap["x_tol"]
                and min(line.p1_px[1], line.p2_px[1]) <= gap["gap_end"]
                and max(line.p1_px[1], line.p2_px[1]) >= gap["gap_start"]
                for line in merged
            ), f"{preset} bridges forbidden source gap {gap}"


_VERTICAL_CADENCED_RUNS = (
    (40, 54),
    (62, 76),
    (84, 98),
    (106, 120),
    (128, 142),
    (150, 164),
)
_VERTICAL_CADENCED_GAPS_2PX = ((56, 60), (78, 82), (100, 104), (122, 126), (144, 148))
_VERTICAL_CADENCED_GAPS_1PX = ((55, 61), (77, 83), (99, 105), (121, 127), (143, 149))


def _vertical_cadenced_image(*, background_gray: int, ink_gray: int, stroke_width_px: int):
    image = np.full((240, 260, 3), background_gray, dtype=np.uint8)
    for start, end in _VERTICAL_CADENCED_RUNS:
        cv2.line(image, (150, start), (150, end), (ink_gray, ink_gray, ink_gray), stroke_width_px)
    return image


def _assert_integrated_merge_preserves_cadenced_gaps(
    image,
    *,
    expected_gaps: tuple[tuple[int, int], ...],
    source_parameters: str,
):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    assert all(
        np.all(gray[start : end + 1, 148:153] == 255)
        for start, end in expected_gaps
    ), f"fixture construction lost a white source gap: {source_parameters}"

    raw = extract_raw_geometry(image, preset="default").lines
    assert raw, f"default extractor found no line segments: {source_parameters}"
    merged = merge_collinear_lines(raw, blocking_texts=[], image_bgr=image)
    merged_spans = [
        (min(line.p1_px[1], line.p2_px[1]), max(line.p1_px[1], line.p2_px[1]))
        for line in merged
        if abs((line.p1_px[0] + line.p2_px[0]) / 2 - 150) <= 3
    ]
    bridged_gaps = [
        gap
        for gap in expected_gaps
        if any(start <= gap[0] and end >= gap[1] for start, end in merged_spans)
    ]
    assert not bridged_gaps, (
        f"integrated extractor->merger path rejoined source gaps {bridged_gaps}; "
        f"source_parameters={source_parameters}; merged_spans={merged_spans}"
    )


def test_integrated_merger_preserves_faint_cadenced_source_gaps():
    """Ink intensity 210 on white; default preset; 2px strokes at x=150."""
    parameters = "background_gray=255, ink_gray=210, stroke_width_px=2, preset=default"
    image = _vertical_cadenced_image(background_gray=255, ink_gray=210, stroke_width_px=2)
    _assert_integrated_merge_preserves_cadenced_gaps(
        image, expected_gaps=_VERTICAL_CADENCED_GAPS_2PX, source_parameters=parameters,
    )


def test_integrated_merger_preserves_thin_cadenced_source_gaps():
    """Black 1px strokes on white; default preset; centerline x=150."""
    parameters = "background_gray=255, ink_gray=0, stroke_width_px=1, preset=default"
    image = _vertical_cadenced_image(background_gray=255, ink_gray=0, stroke_width_px=1)
    _assert_integrated_merge_preserves_cadenced_gaps(
        image, expected_gaps=_VERTICAL_CADENCED_GAPS_1PX, source_parameters=parameters,
    )


def test_c04_four_fragments_with_four_visible_runs_keep_source_gaps():
    """Keep the four-source-run control on the frozen C04 fixture."""
    fixture = Path(__file__).parent / "fixtures" / "C04_DASHED_HIDDEN_LINE.png"
    image = cv2.imread(str(fixture))
    assert image is not None

    raw = extract_raw_geometry(image, preset="default").lines
    selected = sorted(
        raw,
        key=lambda line: (line.p1_px[1] + line.p2_px[1]) / 2,
    )[:4]
    assert len(selected) == 4

    # Count visible dark runs from the frozen source pixels along the shaft's
    # center column, limited to the interval actually presented to merger.
    y_start = int(min(min(line.p1_px[1], line.p2_px[1]) for line in selected))
    y_end = int(max(max(line.p1_px[1], line.p2_px[1]) for line in selected))
    center_column = cv2.cvtColor(image[y_start : y_end + 1, 150:151], cv2.COLOR_BGR2GRAY)[:, 0]
    source_supported = center_column < 200
    transitions = np.diff(np.r_[False, source_supported, False].astype(np.int8))
    run_starts = np.flatnonzero(transitions == 1)
    run_ends = np.flatnonzero(transitions == -1) - 1
    visible_run_count = len(run_starts)
    assert visible_run_count == 4
    visible_gaps = [
        (y_start + int(previous_end) + 1, y_start + int(next_start) - 1)
        for previous_end, next_start in zip(run_ends[:-1], run_starts[1:])
    ]

    merged = merge_collinear_lines(selected, image_bgr=image)
    merged_spans = [
        (int(min(line.p1_px[1], line.p2_px[1])), int(max(line.p1_px[1], line.p2_px[1])))
        for line in merged
    ]
    newly_bridged_gaps = [
        gap
        for gap in visible_gaps
        if any(start <= gap[0] and end >= gap[1] for start, end in merged_spans)
    ]

    assert not newly_bridged_gaps, (
        f"4 fragments span {visible_run_count} visible runs; "
        f"source gaps {newly_bridged_gaps} were bridged into {merged_spans}"
    )


def test_c04_three_input_fragments_with_four_visible_runs_keep_first_gap():
    fixture = Path(__file__).parent / "fixtures" / "C04_DASHED_HIDDEN_LINE.png"
    image = cv2.imread(str(fixture))
    assert image is not None

    raw = sorted(
        extract_raw_geometry(image, preset="default").lines,
        key=lambda line: (line.p1_px[1] + line.p2_px[1]) / 2,
    )
    selected = [raw[0], raw[1], raw[3]]
    assert len(selected) == 3

    y_start = int(min(min(line.p1_px[1], line.p2_px[1]) for line in selected))
    y_end = int(max(max(line.p1_px[1], line.p2_px[1]) for line in selected))
    center_column = cv2.cvtColor(image[y_start : y_end + 1, 150:151], cv2.COLOR_BGR2GRAY)[:, 0]
    supported = center_column < 200
    transitions = np.diff(np.r_[False, supported, False].astype(np.int8))
    visible_run_count = int(np.count_nonzero(transitions == 1))
    assert visible_run_count == 4

    merged = merge_collinear_lines(selected, image_bgr=image)

    first_gap = (56, 60)
    assert not any(
        min(line.p1_px[1], line.p2_px[1]) <= first_gap[0]
        and max(line.p1_px[1], line.p2_px[1]) >= first_gap[1]
        for line in merged
    ), f"3 input fragments span 4 visible runs; bridged {first_gap} into {merged}"


def test_rotated_cadenced_dashes_are_not_rejoined():
    image = np.full((220, 260, 3), 255, dtype=np.uint8)
    angle = np.deg2rad(28)
    origin = np.array([35.0, 45.0])
    direction = np.array([np.cos(angle), np.sin(angle)])
    raw = []
    for index, start in enumerate(range(0, 176, 22)):
        p1 = origin + direction * start
        p2 = origin + direction * (start + 16)
        a, b = tuple(np.rint(p1).astype(int)), tuple(np.rint(p2).astype(int))
        cv2.line(image, a, b, (0, 0, 0), 2)
        raw.append(_line(tuple(p1), tuple(p2), f"rotated-{index}"))

    merged = merge_collinear_lines(
        raw, blocking_texts=[], image_bgr=image,
    )

    assert len(merged) == len(raw), "raster cadence detection must not depend on axis alignment"


def test_rounded_rotated_cadenced_endpoints_keep_source_gaps_separate():
    image = np.full((240, 260, 3), 255, dtype=np.uint8)
    angle = np.deg2rad(28)
    origin = np.array([30.0, 25.0])
    direction = np.array([np.cos(angle), np.sin(angle)])
    raw = []
    for index in range(6):
        start = 40 + 22 * index
        end = 54 + 22 * index
        p1 = origin + direction * start
        p2 = origin + direction * end
        rounded_p1 = tuple(np.rint(p1).astype(int))
        rounded_p2 = tuple(np.rint(p2).astype(int))
        cv2.line(image, rounded_p1, rounded_p2, (0, 0, 0), 2)
        raw.append(_line(rounded_p1, rounded_p2, f"rounded-matrix-{index}"))

    merged = merge_collinear_lines(raw, blocking_texts=[], image_bgr=image)

    assert len(merged) == len(raw), "rounded endpoints must not rotate the source-cadence sampling axis"


def test_truncated_but_repeated_dash_cadence_remains_separate():
    image = np.full((100, 120, 3), 255, dtype=np.uint8)
    raw = []
    for index, start in enumerate([0, 22, 44, 66, 88]):
        end = min(start + 14, image.shape[0] - 1)
        cv2.line(image, (60, start), (60, end), (0, 0, 0), 2)
        raw.append(_line((60, start), (60, end), f"truncated-{index}"))

    merged = merge_collinear_lines(
        raw, blocking_texts=[], image_bgr=image,
    )

    assert len(merged) == len(raw), "image-edge truncation must not erase repeated dash evidence"


def test_crossing_witnesses_do_not_look_like_a_regular_dash_cadence():
    image = np.full((180, 220, 3), 255, dtype=np.uint8)
    raw = []
    for index, start in enumerate([10, 36, 62, 88]):
        end = start + 20
        cv2.line(image, (start, 90), (end, 90), (0, 0, 0), 2)
        raw.append(_line((start, 90), (end, 90), f"crossing-{index}"))
        if index < 3:
            crossing_x = end + 3
            cv2.line(image, (crossing_x, 70), (crossing_x, 110), (0, 0, 0), 1)

    merged = merge_collinear_lines(
        raw, blocking_texts=[], image_bgr=image,
    )

    assert len(merged) == 1, "independent perpendicular source witnesses must retain recovery"
    assert round(merged[0].p1_px[0]) == 10
    assert round(merged[0].p2_px[0]) == 108


def test_irregular_gaps_are_not_misclassified_as_regular_dash_cadence():
    image = np.full((180, 220, 3), 255, dtype=np.uint8)
    for start, end in [(10, 24), (30, 45), (57, 71), (79, 94), (110, 124)]:
        cv2.line(image, (60, start), (60, end), (0, 0, 0), 2)

    assert _source_dash_gap_intervals(image, 60, 0, np.pi / 2, 10, 124) == []
