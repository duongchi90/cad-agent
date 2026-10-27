"""PDF-level controls for full-circle versus chord-closed partial-arc evidence."""

import hashlib
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import fitz
import numpy as np
import pytest

from primitive_ir_lib.run_pdf import (
    _drawing_may_erase_circle,
    _fit_full_line_circle_path,
    _dimension_arrowhead_fill,
    _circle_fill_coverage_fraction,
    _full_page_transparency_group_index,
    _page_circle_witnesses,
    _single_line_record_paths,
    _suspect_geometry,
    run_pdf,
)
import primitive_ir_lib.geometry_extraction as geometry_extraction
import primitive_ir_lib.run_image as run_image_module
from primitive_ir_lib.geometry_extraction import RawCircle, RawGeometry, extract_circles
from primitive_ir_lib.run_image import (
    run as run_image,
)


def _draw_circular_beziers(
    page: fitz.Page, center: fitz.Point, radius: float, end_degrees: float
) -> None:
    shape = page.new_shape()
    boundaries = [0.0, 71.0, 142.0, 213.0, 284.0, end_degrees]
    for start_degrees, stop_degrees in zip(boundaries, boundaries[1:]):
        a0 = math.radians(start_degrees)
        a1 = math.radians(stop_degrees)
        delta = a1 - a0
        handle = (4.0 / 3.0) * math.tan(delta / 4.0) * radius
        p0 = fitz.Point(center.x + radius * math.cos(a0), center.y + radius * math.sin(a0))
        p3 = fitz.Point(center.x + radius * math.cos(a1), center.y + radius * math.sin(a1))
        tangent0 = fitz.Point(-math.sin(a0), math.cos(a0))
        tangent1 = fitz.Point(-math.sin(a1), math.cos(a1))
        p1 = fitz.Point(p0.x + handle * tangent0.x, p0.y + handle * tangent0.y)
        p2 = fitz.Point(p3.x - handle * tangent1.x, p3.y - handle * tangent1.y)
        shape.draw_bezier(p0, p1, p2, p3)
    shape.finish(color=(0.05, 0.05, 0.05), width=1.5, closePath=True)
    shape.commit()


def _circle_primitive_count(page_ir: Path) -> int:
    payload = json.loads(page_ir.read_text(encoding="utf-8"))
    return sum(primitive["type"] == "circle" for primitive in payload["primitives"])


def _circle_primitives(page_ir: Path) -> list[dict]:
    payload = json.loads(page_ir.read_text(encoding="utf-8"))
    return [primitive for primitive in payload["primitives"] if primitive["type"] == "circle"]


def _raw_hough_has_circle_near(
    image_path: Path,
    center: tuple[float, float],
    radius: float,
    *,
    center_tolerance: float = 16.0,
    radius_tolerance: float = 14.0,
) -> bool:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    assert image is not None, f"missing rendered image: {image_path}"
    return any(
        math.hypot(circle.center_px[0] - center[0], circle.center_px[1] - center[1])
        <= center_tolerance
        and abs(circle.radius_px - radius) <= radius_tolerance
        for circle in extract_circles(image)
    )


def _has_circle_near(
    circles: list[dict],
    center: tuple[float, float],
    radius: float,
    *,
    center_tolerance: float = 8.0,
    radius_tolerance: float = 8.0,
) -> bool:
    return any(
        math.hypot(
            circle["geometry"]["center"]["x"] - center[0],
            circle["geometry"]["center"]["y"] - center[1],
        )
        <= center_tolerance
        and abs(circle["geometry"]["radius"] - radius) <= radius_tolerance
        for circle in circles
    )


def _rectangular_clip(rect: fitz.Rect, *, level: int = 0) -> dict:
    corners = [
        fitz.Point(rect.x0, rect.y0),
        fitz.Point(rect.x1, rect.y0),
        fitz.Point(rect.x1, rect.y1),
        fitz.Point(rect.x0, rect.y1),
    ]
    return {
        "type": "clip",
        "level": level,
        "rect": None,
        "scissor": rect,
        "items": [
            ("l", corners[index], corners[(index + 1) % len(corners)])
            for index in range(len(corners))
        ],
    }


def test_later_crossing_line_invalidates_full_circle_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    center = fitz.Point(300, 300)
    radius = 212.5
    page.draw_circle(center, radius, color=(0.05, 0.05, 0.05), width=1.5)
    page.draw_line((0, 300), (600, 300), color=(1.0, 1.0, 1.0), width=1.5)

    require_all_witnesses, witnesses, suspect_regions = _page_circle_witnesses(page, 1.0)
    document.close()

    assert require_all_witnesses is False
    assert witnesses == []
    assert suspect_regions


@pytest.mark.parametrize(
    "center,rotation",
    [
        (fitz.Point(1000, 1000), 0),
        (fitz.Point(5, 200), 0),
        (fitz.Point(1000, 1000), 90),
        (fitz.Point(5, 200), 90),
    ],
    ids=["outside-page", "partially-clipped", "rotated-outside-page", "rotated-partially-clipped"],
)
def test_off_page_or_partially_clipped_circle_is_not_a_validated_witness(
    center: fitz.Point, rotation: int
) -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=400)
    page.set_rotation(rotation)
    page.draw_circle(center, 100, color=(0.05, 0.05, 0.05), width=1.5)

    _, witnesses, suspect_regions = _page_circle_witnesses(page, 1.0)
    document.close()

    assert witnesses == []
    assert suspect_regions


def test_later_remote_stroke_only_quad_frame_preserves_full_circle_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    page.draw_quad(
        fitz.Quad(
            fitz.Point(10, 10),
            fitz.Point(590, 10),
            fitz.Point(10, 590),
            fitz.Point(590, 590),
        ),
        color=(0.05, 0.05, 0.05),
        width=2.0,
    )
    drawings = page.get_drawings(extended=True)
    drawings[-1]["items"].append(("l", fitz.Point(20, 20), fitz.Point(30, 30)))

    with patch.object(fitz.Page, "get_drawings", return_value=drawings):
        _, witnesses, suspect_regions = _page_circle_witnesses(page, 1.0)
    document.close()

    assert len(witnesses) == 1, "remote quad edges must not occlude a circle by their bbox alone"
    assert suspect_regions == []


def test_later_crossing_stroke_only_quad_invalidates_full_circle_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    page.draw_quad(
        fitz.Quad(
            fitz.Point(100, 100),
            fitz.Point(500, 100),
            fitz.Point(100, 500),
            fitz.Point(500, 500),
        ),
        color=(0.05, 0.05, 0.05),
        width=2.0,
    )

    _, witnesses, suspect_regions = _page_circle_witnesses(page, 1.0)
    document.close()

    assert witnesses == []
    assert suspect_regions


def test_malformed_nonfinite_quad_stays_fail_closed() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    drawings = page.get_drawings(extended=True)
    invalid_point = SimpleNamespace(x=math.nan, y=10.0)
    valid_point = SimpleNamespace(x=20.0, y=20.0)
    invalid_quad = SimpleNamespace(
        ul=invalid_point,
        ur=valid_point,
        lr=SimpleNamespace(x=30.0, y=30.0),
        ll=SimpleNamespace(x=10.0, y=30.0),
    )
    drawings.append(
        {
            "type": "s",
            "items": [("qu", invalid_quad)],
            "rect": fitz.Rect(10, 10, 30, 30),
            "color": (0.05, 0.05, 0.05),
            "fill": None,
            "width": 2.0,
            "stroke_opacity": 1.0,
        }
    )

    with patch.object(fitz.Page, "get_drawings", return_value=drawings):
        _, witnesses, suspect_regions = _page_circle_witnesses(page, 1.0)
    document.close()

    assert witnesses == []
    assert suspect_regions


def test_later_filled_quad_covering_circle_invalidates_full_circle_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    page.draw_quad(
        fitz.Quad(
            fitz.Point(20, 20),
            fitz.Point(580, 20),
            fitz.Point(20, 580),
            fitz.Point(580, 580),
        ),
        color=None,
        fill=(1.0, 1.0, 1.0),
    )

    _, witnesses, suspect_regions = _page_circle_witnesses(page, 1.0)
    document.close()

    assert witnesses == []
    assert suspect_regions


def test_filled_disconnected_subpath_closes_before_next_subpath() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    center = (300.0, 300.0)
    radius = 100.0

    # The first open fill subpath is implicitly closed by PDF fill semantics.
    # Its closing edge crosses the circle, while its two explicit edges stay
    # outside. A distant second subpath forces the item parser to flush it.
    shape = page.new_shape()
    shape.draw_polyline(
        [fitz.Point(200, 399.99), fitz.Point(300, 500), fitz.Point(400, 399.99)]
    )
    shape.draw_polyline(
        [fitz.Point(10, 10), fitz.Point(20, 10), fitz.Point(20, 20), fitz.Point(10, 20)]
    )
    shape.finish(color=None, fill=(0.75, 0.75, 0.75), closePath=False)
    shape.commit()

    drawing = next(d for d in page.get_drawings(extended=True) if d["type"] == "f")
    suspect = _suspect_geometry(drawing, 1.0, page.rotation_matrix)

    assert len(suspect["fill_polygons"]) == 2
    assert geometry_extraction._suspect_region_intersects_circle(
        suspect, center[0], center[1], radius, tolerance=2.0
    ), "every disconnected fill subpath must include its implicit closing edge"
    document.close()


def test_later_black_crossing_line_preserves_full_circle_witness(tmp_path: Path) -> None:
    pdf_path = tmp_path / "black-crossing-circle.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    center = fitz.Point(300, 300)
    page.draw_circle(center, 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    page.draw_line((0, 300), (600, 300), color=(0.05, 0.05, 0.05), width=1.5)
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    circle_count = _circle_primitive_count(output_dir / "primitive_ir" / "page_01.json")
    assert circle_count >= 1, "a visible full circle must survive a later non-erasing black stroke"


def test_later_text_over_circle_perimeter_invalidates_vector_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    page.insert_text((500, 305), "XXXX", fontsize=28, color=(0.05, 0.05, 0.05))

    _, witnesses, suspect_regions = _page_circle_witnesses(page, 1.0)
    text_spans = page.get_texttrace()
    document.close()

    assert len(text_spans) == 1
    assert witnesses == [], "later text touching the circle perimeter must fail closed"
    assert suspect_regions


def test_later_wide_same_color_crossing_stroke_invalidates_circle_witness(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "wide-same-color-crossing-circle.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    center = fitz.Point(300, 300)
    page.draw_circle(center, 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    page.draw_line(
        (0, 300),
        (600, 300),
        color=(0.05, 0.05, 0.05),
        width=100.0,
    )
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    assert not _has_circle_near(circles, (600, 600), 425), (
        "a later same-color stroke that covers a material part of the circle perimeter "
        "must invalidate the full-circle witness"
    )


def test_run_pdf_uses_only_later_images_as_circle_occluders(tmp_path: Path) -> None:
    pdf_path = tmp_path / "image-paint-order.pdf"
    output_dir = tmp_path / "out"
    background = np.full((600, 600, 3), 220, dtype=np.uint8)
    success, encoded = cv2.imencode(".png", background)
    assert success
    document = fitz.open()

    image_before_circle = document.new_page(width=600, height=600)
    image_before_circle.insert_image(image_before_circle.rect, stream=encoded.tobytes())
    image_before_circle.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)

    image_after_circle = document.new_page(width=600, height=600)
    image_after_circle.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    image_after_circle.insert_image(image_after_circle.rect, stream=encoded.tobytes())

    masked_image_page = document.new_page(width=600, height=600)
    masked_image_page.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    masked_rgba = np.zeros((32, 32, 4), dtype=np.uint8)
    masked_rgba[:, :, :3] = 0
    masked_rgba[:, 14:18, 3] = 255
    mask_success, masked_encoded = cv2.imencode(".png", masked_rgba)
    assert mask_success
    masked_image_page.insert_image(
        fitz.Rect(500, 284, 525, 316), stream=masked_encoded.tobytes()
    )

    document.save(pdf_path)
    document.close()
    reopened = fitz.open(pdf_path)
    assert any(image[1] > 0 for image in reopened[2].get_images(full=True)), (
        "the negative control must contain a real PDF soft-mask image"
    )
    reopened.close()
    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    before_circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    after_circles = _circle_primitives(output_dir / "primitive_ir" / "page_02.json")
    masked_circles = _circle_primitives(output_dir / "primitive_ir" / "page_03.json")
    assert _has_circle_near(before_circles, (600, 600), 425), (
        "a background image painted before a visible vector circle must not invalidate that witness"
    )
    assert not _has_circle_near(after_circles, (600, 600), 425), (
        "a later background image that erases the vector circle must invalidate its witness"
    )
    assert not _has_circle_near(masked_circles, (600, 600), 425), (
        "a later soft-masked image intersecting the perimeter must remain a conservative occluder"
    )


def test_background_colored_crossing_line_invalidates_full_circle_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    background = (0.75, 0.75, 0.75)
    page.draw_rect(page.rect, color=None, fill=background)
    page.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    page.draw_line((0, 300), (600, 300), color=background, width=1.5)

    _, witnesses, suspect_regions = _page_circle_witnesses(page, 1.0)
    document.close()

    assert witnesses == []
    assert suspect_regions


def test_same_color_filled_wedge_invalidates_full_circle_witness(tmp_path: Path) -> None:
    pdf_path = tmp_path / "same-color-filled-wedge.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    center = fitz.Point(300, 300)
    radius = 212.5
    dark = (0.05, 0.05, 0.05)
    page.draw_circle(center, radius, color=dark, width=1.5)

    start_angle = math.radians(-15.0)
    end_angle = math.radians(15.0)
    wedge = page.new_shape()
    wedge.draw_polyline(
        [
            center,
            fitz.Point(
                center.x + radius * math.cos(start_angle),
                center.y + radius * math.sin(start_angle),
            ),
            fitz.Point(
                center.x + radius * math.cos(end_angle),
                center.y + radius * math.sin(end_angle),
            ),
        ]
    )
    wedge.finish(color=None, fill=dark, closePath=True)
    wedge.commit()
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    assert not _has_circle_near(circles, (600, 600), 425), (
        "a same-color opaque fill that masks part of the circumference must invalidate the full-circle witness"
    )


def test_later_clip_context_does_not_invalidate_prior_circle_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    drawings = page.get_drawings(extended=True)
    drawings.insert(0, _rectangular_clip(fitz.Rect(-100, -100, 700, 700)))

    with patch.object(fitz.Page, "get_drawings", return_value=drawings):
        require_all_witnesses, witnesses, suspect_regions = _page_circle_witnesses(page, 1.0)
    document.close()

    assert require_all_witnesses is False
    assert len(witnesses) == 1
    assert suspect_regions == []


def test_prior_clip_cutting_circle_does_not_supply_full_circle_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    drawings = page.get_drawings(extended=True)
    for drawing in drawings:
        drawing["level"] = 1
    drawings.insert(0, _rectangular_clip(fitz.Rect(0, 0, 400, 600), level=0))

    with patch.object(fitz.Page, "get_drawings", return_value=drawings):
        require_all_witnesses, witnesses, suspect_regions = _page_circle_witnesses(page, 1.0)
    document.close()

    assert require_all_witnesses is False
    assert witnesses == []
    assert suspect_regions


def test_expired_clip_and_group_levels_do_not_invalidate_later_circle_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    drawings = page.get_drawings(extended=True)
    drawings.insert(0, _rectangular_clip(fitz.Rect(0, 0, 100, 600), level=0))
    drawings.insert(1, {"type": "group", "level": 0, "rect": fitz.Rect(0, 0, 100, 600)})

    with patch.object(fitz.Page, "get_drawings", return_value=drawings):
        require_all_witnesses, witnesses, suspect_regions = _page_circle_witnesses(page, 1.0)
    document.close()

    assert require_all_witnesses is False
    assert len(witnesses) == 1
    assert suspect_regions == []


def test_page_transparency_group_and_paired_dimension_arrows_preserve_concentric_circle_witnesses(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "page-group-dimension-circles.pdf"
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    center = fitz.Point(300, 300)
    radii = (212.63, 167.97)

    for radius in radii:
        page.draw_circle(center, radius, color=(0.0, 0.0, 0.0), width=1.41)

    def draw_diameter_dimension(radius: float) -> None:
        left_tip = fitz.Point(center.x - radius, center.y)
        left_shared = fitz.Point(left_tip.x + 8.0, left_tip.y)
        right_tip = fitz.Point(center.x + radius, center.y)
        right_shared = fitz.Point(right_tip.x - 8.0, right_tip.y)

        def draw_arrow(tip: fitz.Point, shared: fitz.Point) -> None:
            page.draw_line(shared, tip, color=(0.0, 0.0, 0.0), width=0.705)
            half_width = 3.0
            triangle = [
                fitz.Point(shared.x, shared.y - half_width),
                tip,
                fitz.Point(shared.x, shared.y + half_width),
            ]
            fill = page.new_shape()
            fill.draw_polyline(triangle + [triangle[0]])
            fill.finish(color=None, fill=(0.0, 0.0, 0.0), closePath=True)
            fill.commit()
            outline = page.new_shape()
            outline.draw_polyline(triangle + [triangle[0]])
            outline.finish(color=(0.0, 0.0, 0.0), width=0.705, closePath=True)
            outline.commit()

        draw_arrow(left_tip, left_shared)
        draw_arrow(right_tip, right_shared)
        page.draw_line(left_shared, right_shared, color=(0.0, 0.0, 0.0), width=0.705)

    draw_diameter_dimension(radii[0])
    draw_diameter_dimension(radii[1])
    document.xref_set_key(
        page.xref,
        "Group",
        "<< /S /Transparency /CS /DeviceRGB >>",
    )
    document.save(pdf_path)
    document.close()

    reopened = fitz.open(pdf_path)
    try:
        require_all_witnesses, witnesses, suspect_regions = _page_circle_witnesses(
            reopened[0], 2.0
        )
        drawings = reopened[0].get_drawings(extended=True)
    finally:
        reopened.close()

    assert require_all_witnesses is False
    assert len(witnesses) == 2
    assert sorted(witness[2] / 2.0 for witness in witnesses) == pytest.approx(sorted(radii), abs=0.05)
    assert suspect_regions == []

    fill_index = next(
        index for index, drawing in enumerate(drawings) if drawing.get("type") in {"f", "fs"}
    )
    nonnormal_fill = [dict(drawing) for drawing in drawings]
    nonnormal_fill[fill_index]["blendmode"] = "Multiply"
    assert _dimension_arrowhead_fill(
        nonnormal_fill, fill_index, witnesses[0], drawings[1].get("color")
    ) is False


def test_full_page_group_exception_rejects_modified_and_ambiguous_groups(tmp_path: Path) -> None:
    pdf_path = tmp_path / "page-group-controls.pdf"
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_circle(fitz.Point(300, 300), 100, color=(0.0, 0.0, 0.0), width=1.0)
    document.xref_set_key(page.xref, "Group", "<< /S /Transparency /CS /DeviceRGB >>")
    document.save(pdf_path)
    document.close()
    document = fitz.open(pdf_path)
    page = document[0]
    drawings = page.get_drawings(extended=True)
    assert _full_page_transparency_group_index(page, drawings) == 0

    for group_key in ("/I true", "/K true"):
        document.xref_set_key(
            page.xref,
            "Group",
            f"<< /S /Transparency /CS /DeviceRGB {group_key} >>",
        )
        assert _full_page_transparency_group_index(page, drawings) is None

    document.xref_set_key(page.xref, "Group", "<< /S /Transparency /CS /DeviceRGB >>")
    partial = [dict(drawing) for drawing in drawings]
    partial[0]["rect"] = fitz.Rect(0, 0, 300, 600)
    assert _full_page_transparency_group_index(page, partial) is None

    nonnormal = [dict(drawing) for drawing in drawings]
    nonnormal[0]["blendmode"] = "Multiply"
    assert _full_page_transparency_group_index(page, nonnormal) is None

    nested = [dict(drawing) for drawing in drawings]
    nested.append(dict(nested[0]))
    assert _full_page_transparency_group_index(page, nested) is None

    document.close()


def test_run_pdf_does_not_promote_chord_closed_partial_arc_to_circle(tmp_path: Path) -> None:
    pdf_path = tmp_path / "circle-controls.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()
    center = fitz.Point(300, 300)
    radius = 212.5

    full_circle = document.new_page(width=600, height=600)
    full_circle.draw_circle(center, radius, color=(0.05, 0.05, 0.05), width=1.5)
    full_circle.draw_circle(center, 170.0, color=(0.05, 0.05, 0.05), width=1.5)

    partial = document.new_page(width=600, height=600)
    _draw_circular_beziers(partial, center, radius, 355.0)

    ellipse = document.new_page(width=600, height=600)
    ellipse.draw_oval(fitz.Rect(100, 115, 500, 485), color=(0.05, 0.05, 0.05), width=1.5)

    mixed_raster = document.new_page(width=600, height=600)
    source_image = np.full((1200, 1200, 3), 210, dtype=np.uint8)
    cv2.circle(source_image, (600, 600), 425, (30, 30, 30), 2, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", source_image)
    assert success
    mixed_raster.insert_image(mixed_raster.rect, stream=encoded.tobytes())
    curve = mixed_raster.new_shape()
    curve.draw_bezier((25, 30), (35, 5), (50, 55), (65, 30))
    curve.finish(color=(0.05, 0.05, 0.05), width=1.0)
    curve.commit()

    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    full_circle_count = _circle_primitive_count(output_dir / "primitive_ir" / "page_01.json")
    chord_closed_arc_count = _circle_primitive_count(output_dir / "primitive_ir" / "page_02.json")
    ellipse_circle_count = _circle_primitive_count(output_dir / "primitive_ir" / "page_03.json")
    mixed_raster_count = _circle_primitive_count(output_dir / "primitive_ir" / "page_04.json")

    assert full_circle_count >= 2, "both complete concentric source circles must remain recognized"
    assert chord_closed_arc_count == 0, "a chord-closed 355-degree arc is not a full source circle"
    assert ellipse_circle_count == 0, "an ellipse must not be used as a full-circle witness"
    assert mixed_raster_count >= 1, (
        "an unrelated local vector curve must not suppress a raster circle"
    )


def test_run_pdf_refines_circle_geometry_from_unique_pdf_witness(tmp_path: Path) -> None:
    pdf_path = tmp_path / "circle-witness-precision.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()
    page = document.new_page(width=842, height=595)
    center = fitz.Point(161.55, 401.59)
    page_height = page.rect.height
    radii = (45.2725, 17.01095)
    for radius in radii:
        page.draw_circle(center, radius, color=(0.05, 0.05, 0.05), width=0.75)
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    assert len(circles) == 2, "each uniquely visible PDF circle must have one raster candidate"
    for radius in radii:
        closest = min(
            circles,
            key=lambda circle: abs(circle["geometry"]["radius"] * 0.5 - radius),
        )
        output_radius_pt = closest["geometry"]["radius"] * 0.5
        output_center_pt = (
            closest["geometry"]["center"]["x"] * 0.5,
            closest["geometry"]["center"]["y"] * 0.5,
        )
        expected_center_pt = (center.x, page_height - center.y)
        assert abs(output_radius_pt - radius) <= 0.05
        assert math.dist(output_center_pt, expected_center_pt) <= 0.05


def test_run_pdf_keeps_raster_circle_enclosed_by_unrelated_curve_bounds(tmp_path: Path) -> None:
    pdf_path = tmp_path / "raster-circle-enclosed-by-vector-bounds.pdf"
    image_path = tmp_path / "same-page-render.png"
    baseline_dir = tmp_path / "baseline"
    gated_dir = tmp_path / "gated"
    document = fitz.open()
    page = document.new_page(width=600, height=600)

    source_image = np.full((1200, 1200, 3), 210, dtype=np.uint8)
    cv2.circle(source_image, (600, 600), 425, (30, 30, 30), 2, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", source_image)
    assert success
    page.insert_image(page.rect, stream=encoded.tobytes())

    # The four cubic sides enclose the raster circle, but remain well outside
    # its circumference. Their PDF drawing rectangle alone overlaps it.
    shape = page.new_shape()
    corners = [fitz.Point(40, 40), fitz.Point(560, 40), fitz.Point(560, 560), fitz.Point(40, 560)]
    for start, end in zip(corners, corners[1:] + corners[:1]):
        delta = end - start
        shape.draw_bezier(start, start + delta / 3, start + delta * (2 / 3), end)
    shape.finish(color=(0.05, 0.05, 0.05), width=1.0, closePath=True)
    shape.commit()

    page.get_pixmap(dpi=144, alpha=False).save(image_path)
    document.save(pdf_path)
    document.close()

    from primitive_ir_lib.run_image import run as run_image

    run_image(
        str(image_path),
        str(baseline_dir / "primitive_ir.json"),
        scale_mm_per_px=1.0,
        preset="real_scan_tuned_v1",
    )
    run_pdf(pdf_path, gated_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    baseline_circles = _circle_primitives(baseline_dir / "primitive_ir.json")
    gated_circles = _circle_primitives(gated_dir / "primitive_ir" / "page_01.json")

    assert _has_circle_near(baseline_circles, (600, 600), 425), (
        "baseline must find the source raster circle"
    )
    assert _has_circle_near(gated_circles, (600, 600), 425), (
        "an unrelated curve bound must not suppress that same untouched raster circle"
    )


def test_run_pdf_preserves_raster_circle_inside_mixed_rectangle_curve_bounds(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "raster-circle-inside-mixed-vector-bounds.pdf"
    image_path = tmp_path / "same-page-render.png"
    baseline_dir = tmp_path / "baseline"
    gated_dir = tmp_path / "gated"
    document = fitz.open()
    page = document.new_page(width=600, height=600)

    source_image = np.full((1200, 1200, 3), 220, dtype=np.uint8)
    cv2.circle(source_image, (600, 600), 425, (20, 20, 20), 4, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", source_image)
    assert success
    page.insert_image(page.rect, stream=encoded.tobytes())

    # PyMuPDF returns this as one drawing with items ['re', 'c', 'l'];
    # every actual vector path remains far from the raster circle perimeter.
    shape = page.new_shape()
    shape.draw_rect(fitz.Rect(40, 40, 560, 560))
    shape.draw_bezier((25, 30), (35, 5), (50, 55), (65, 30))
    shape.finish(color=(0.05, 0.05, 0.05), width=1.0)
    shape.commit()

    page.get_pixmap(dpi=144, alpha=False).save(image_path)
    document.save(pdf_path)
    document.close()

    from primitive_ir_lib.run_image import run as run_image

    run_image(
        str(image_path),
        str(baseline_dir / "primitive_ir.json"),
        scale_mm_per_px=1.0,
        preset="real_scan_tuned_v1",
    )
    run_pdf(pdf_path, gated_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    baseline_circles = _circle_primitives(baseline_dir / "primitive_ir.json")
    gated_circles = _circle_primitives(gated_dir / "primitive_ir" / "page_01.json")
    assert _has_circle_near(baseline_circles, (600, 600), 425), (
        "baseline must find the source raster circle"
    )
    assert _has_circle_near(gated_circles, (600, 600), 425), (
        "an unrelated rectangle item must not replace supported path geometry with its full bounds"
    )


def test_run_pdf_keeps_local_raster_circle_on_rotated_page(tmp_path: Path) -> None:
    pdf_path = tmp_path / "rotated-independent-raster-circle.pdf"
    output_dir = tmp_path / "out"
    source_image = np.full((600, 600, 3), 220, dtype=np.uint8)
    cv2.circle(source_image, (150, 200), 70, (20, 20, 20), 4, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", source_image)
    assert success
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.insert_image(page.rect, stream=encoded.tobytes())
    _draw_circular_beziers(page, fitz.Point(450, 400), 40, 300.0)
    page.set_rotation(90)
    rendered_center = fitz.Point(150, 200) * page.rotation_matrix
    expected_center = (rendered_center.x, page.rect.height - rendered_center.y)
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72, preset="real_scan_tuned_v1")

    circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    assert _has_circle_near(circles, expected_center, 70), (
        "a local unsupported page rotation must not suppress an independent raster circle"
    )


def test_run_pdf_keeps_local_raster_circle_on_cropped_rotated_page(tmp_path: Path) -> None:
    pdf_path = tmp_path / "cropped-rotated-independent-raster-circle.pdf"
    output_dir = tmp_path / "out"
    source_image = np.full((600, 600, 3), 220, dtype=np.uint8)
    cv2.circle(source_image, (200, 200), 70, (20, 20, 20), 4, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", source_image)
    assert success
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.insert_image(page.rect, stream=encoded.tobytes())
    _draw_circular_beziers(page, fitz.Point(400, 400), 40, 300.0)
    page.set_cropbox(fitz.Rect(100, 100, 500, 500))
    page.set_rotation(90)
    rendered_center = fitz.Point(100, 100) * page.rotation_matrix
    expected_center = (rendered_center.x, page.rect.height - rendered_center.y)
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72, preset="real_scan_tuned_v1")

    circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    assert _has_circle_near(circles, expected_center, 70), (
        "crop and rotation must keep the suspect arc local to its transformed rendered position"
    )


def test_run_pdf_rejects_raster_circle_erased_by_wide_vector_arc(tmp_path: Path) -> None:
    pdf_path = tmp_path / "raster-circle-erased-by-wide-vector-arc.pdf"
    image_path = tmp_path / "same-page-render.png"
    gated_dir = tmp_path / "gated"
    document = fitz.open()
    page = document.new_page(width=600, height=600)

    source_image = np.full((600, 600, 3), 220, dtype=np.uint8)
    cv2.circle(source_image, (200, 200), 70, (20, 20, 20), 4, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", source_image)
    assert success
    page.insert_image(page.rect, stream=encoded.tobytes())

    # At x=276 the centerline misses the detected circumference by about
    # 8 px, but the 18 px background-colored stroke erases part of the arc.
    shape = page.new_shape()
    shape.draw_bezier((276, 120), (276, 160), (276, 240), (276, 280))
    shape.finish(color=(220 / 255, 220 / 255, 220 / 255), width=18.0)
    shape.commit()

    page.get_pixmap(dpi=72, alpha=False).save(image_path)
    document.save(pdf_path)
    document.close()

    assert _raw_hough_has_circle_near(image_path, (200, 200), 70), (
        "raw Hough must still propose the source raster circle before source admission"
    )
    run_pdf(pdf_path, gated_dir, scale_mm_per_px=1.0, dpi=72, preset="real_scan_tuned_v1")

    gated_circles = _circle_primitives(gated_dir / "primitive_ir" / "page_01.json")
    assert not _has_circle_near(gated_circles, (200, 400), 70), (
        "a wide background-colored vector stroke must not leave the erased raster circle as a full circle"
    )


def test_run_pdf_rejects_circle_whose_perimeter_is_inside_a_filled_path(tmp_path: Path) -> None:
    pdf_path = tmp_path / "raster-circle-erased-by-filled-path.pdf"
    image_path = tmp_path / "same-page-render.png"
    gated_dir = tmp_path / "gated"
    source_image = np.full((600, 600, 3), 220, dtype=np.uint8)
    center = (200.0, 200.0)
    cv2.circle(source_image, (200, 200), 70, (20, 20, 20), 4, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", source_image)
    assert success

    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.insert_image(page.rect, stream=encoded.tobytes())
    page.draw_circle(center, 70, color=(0.05, 0.05, 0.05), width=1.0)
    sector_angles = [math.radians(degree) for degree in range(31)]
    points = [
        fitz.Point(center[0] + 80.0 * math.cos(angle), center[1] + 80.0 * math.sin(angle))
        for angle in sector_angles
    ]
    points.extend(
        fitz.Point(center[0] + 60.0 * math.cos(angle), center[1] + 60.0 * math.sin(angle))
        for angle in reversed(sector_angles)
    )
    shape = page.new_shape()
    shape.draw_polyline(points)
    shape.finish(color=None, fill=(220 / 255, 220 / 255, 220 / 255), closePath=True)
    shape.commit()
    page.get_pixmap(dpi=72, alpha=False).save(image_path)
    document.save(pdf_path)
    document.close()

    assert _raw_hough_has_circle_near(image_path, (200, 200), 70), (
        "raw Hough must still propose the source raster circle before source admission"
    )
    run_pdf(pdf_path, gated_dir, scale_mm_per_px=1.0, dpi=72, preset="real_scan_tuned_v1")

    gated_circles = _circle_primitives(gated_dir / "primitive_ir" / "page_01.json")
    assert not _has_circle_near(gated_circles, (200, 400), 70), (
        "filled vector paint over the circle perimeter must not leave a full-circle candidate"
    )


def test_run_pdf_rejects_white_on_white_circle_witness(tmp_path: Path) -> None:
    pdf_path = tmp_path / "invisible-circle-witness.pdf"
    output_dir = tmp_path / "out"
    center = fitz.Point(300, 300)
    radius = 212.5
    black = (0.05, 0.05, 0.05)
    document = fitz.open()

    hidden_witness = document.new_page(width=600, height=600)
    hidden_witness.draw_circle(center, radius, color=(1.0, 1.0, 1.0), width=1.5)
    _draw_circular_beziers(hidden_witness, center, radius, 355.0)

    visible_circle = document.new_page(width=600, height=600)
    visible_circle.draw_circle(center, radius, color=black, width=1.5)

    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    hidden_witness_count = _circle_primitive_count(output_dir / "primitive_ir" / "page_01.json")
    visible_circle_count = _circle_primitive_count(output_dir / "primitive_ir" / "page_02.json")

    assert hidden_witness_count == 0, (
        "white-on-white vector geometry cannot witness a visible circle"
    )
    assert visible_circle_count >= 1, "a visible source circle must remain recognized"


@pytest.mark.parametrize(
    "center",
    [fitz.Point(1000, 1000), fitz.Point(5, 200)],
    ids=["outside-page", "partially-clipped"],
)
def test_run_pdf_does_not_materialize_page_clipped_vector_circle(
    tmp_path: Path, center: fitz.Point
) -> None:
    pdf_path = tmp_path / "page-clipped-circle.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()
    page = document.new_page(width=600, height=400)
    page.draw_circle(center, 100, color=(0.05, 0.05, 0.05), width=1.5)
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72, preset="real_scan_tuned_v1")

    circle_count = _circle_primitive_count(output_dir / "primitive_ir" / "page_01.json")
    assert circle_count == 0, "page-clipped source geometry cannot become a complete CIRCLE"


def test_run_pdf_manifest_and_render_use_the_same_source_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import primitive_ir_lib.run_pdf as run_pdf_module

    pdf_path = tmp_path / "source.pdf"
    output_dir = tmp_path / "out"
    original_doc = fitz.open()
    original_page = original_doc.new_page(width=120, height=80)
    original_page.draw_rect(fitz.Rect(10, 10, 40, 40), color=None, fill=(1, 0, 0))
    original_bytes = original_doc.tobytes()
    original_doc.close()

    replacement_doc = fitz.open()
    replacement_page = replacement_doc.new_page(width=120, height=80)
    replacement_page.draw_rect(fitz.Rect(70, 10, 100, 40), color=None, fill=(0, 0, 1))
    replacement_bytes = replacement_doc.tobytes()
    replacement_doc.close()
    pdf_path.write_bytes(original_bytes)

    original_open = fitz.open
    expected_doc = original_open(stream=original_bytes, filetype="pdf")
    expected_render = expected_doc[0].get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False).tobytes("png")
    expected_doc.close()
    substituted = False

    def replace_source_before_open(*args: object, **kwargs: object) -> fitz.Document:
        nonlocal substituted
        if not substituted:
            substituted = True
            pdf_path.write_bytes(replacement_bytes)
        return original_open(*args, **kwargs)

    monkeypatch.setattr(run_pdf_module.fitz, "open", replace_source_before_open)
    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72)

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    rendered = (output_dir / "rendered" / "page_01.png").read_bytes()
    assert substituted
    assert manifest["source_pdf_sha256"] == hashlib.sha256(original_bytes).hexdigest()
    assert rendered == expected_render, "render must come from the bytes identified by the manifest"


def test_run_pdf_rejects_circle_erased_by_white_paint_on_gray_paper(tmp_path: Path) -> None:
    pdf_path = tmp_path / "gray-paper-circle-erasure.pdf"
    output_dir = tmp_path / "out"
    center = fitz.Point(300, 300)
    radius = 212.5
    black = (0.05, 0.05, 0.05)
    gray = (0.75, 0.75, 0.75)
    document = fitz.open()

    erased_witness = document.new_page(width=600, height=600)
    erased_witness.draw_rect(erased_witness.rect, color=None, fill=gray)
    erased_witness.draw_circle(center, radius, color=black, width=1.5)
    erased_witness.draw_line((0, 300), (600, 300), color=(1.0, 1.0, 1.0), width=1.5)

    gray_positive_control = document.new_page(width=600, height=600)
    gray_positive_control.draw_rect(gray_positive_control.rect, color=None, fill=gray)
    gray_positive_control.draw_circle(center, radius, color=black, width=1.5)

    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    erased_witness_count = _circle_primitive_count(output_dir / "primitive_ir" / "page_01.json")
    gray_positive_count = _circle_primitive_count(output_dir / "primitive_ir" / "page_02.json")

    assert erased_witness_count == 0, (
        "later white paint must invalidate a dark circle witness on gray paper"
    )
    assert gray_positive_count >= 1, "a visible dark circle on gray paper must remain recognized"


def test_run_pdf_keeps_raster_circle_outside_uncertain_vector_bounds(tmp_path: Path) -> None:
    pdf_path = tmp_path / "mixed-raster-and-erased-vector-circle.pdf"
    output_dir = tmp_path / "out"
    page_size = 1200
    raster_center = (950, 950)
    raster_radius = 130
    image = np.full((page_size, page_size, 3), 220, dtype=np.uint8)
    cv2.circle(image, raster_center, raster_radius, (20, 20, 20), 4, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", image)
    assert success

    document = fitz.open()
    page = document.new_page(width=page_size, height=page_size)
    page.insert_image(page.rect, stream=encoded.tobytes())
    page.draw_circle((300, 300), 150, color=(0.05, 0.05, 0.05), width=1.5)
    page.draw_line((0, 300), (600, 300), color=(1.0, 1.0, 1.0), width=1.5)
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72, preset="real_scan_tuned_v1")

    payload = json.loads((output_dir / "primitive_ir" / "page_01.json").read_text(encoding="utf-8"))
    circles = [primitive for primitive in payload["primitives"] if primitive["type"] == "circle"]

    assert len(circles) == 1, (
        "keep the independent raster circle but reject the erased vector circle"
    )
    center = circles[0]["geometry"]["center"]
    assert math.isclose(center["x"], 950, abs_tol=3)
    assert math.isclose(center["y"], 250, abs_tol=3)


def test_run_pdf_rejects_segmented_partial_arc_but_keeps_raster_circle(tmp_path: Path) -> None:
    pdf_path = tmp_path / "segmented-vector-arc-and-independent-raster-circle.pdf"
    output_dir = tmp_path / "out"
    page_size = 1200
    raster_center = (950, 950)
    raster_radius = 130
    image = np.full((page_size, page_size, 3), 220, dtype=np.uint8)
    cv2.circle(image, raster_center, raster_radius, (20, 20, 20), 4, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", image)
    assert success

    document = fitz.open()
    segmented_arc = document.new_page(width=page_size, height=page_size)
    segmented_arc.insert_image(segmented_arc.rect, stream=encoded.tobytes())
    shape = segmented_arc.new_shape()
    center = fitz.Point(300, 300)
    radius = 150
    points = [
        fitz.Point(
            center.x + radius * math.cos(math.radians(degree)),
            center.y + radius * math.sin(math.radians(degree)),
        )
        for degree in range(356)
    ]
    for start, end in zip(points, points[1:]):
        shape.draw_line(start, end)
    shape.draw_line(points[-1], points[0])
    shape.finish(color=(0.05, 0.05, 0.05), width=1.5)
    shape.commit()

    straight_line_control = document.new_page(width=page_size, height=page_size)
    straight_line_control.insert_image(straight_line_control.rect, stream=encoded.tobytes())
    straight_line_control.draw_line((40, 40), (700, 40), color=(0.05, 0.05, 0.05), width=1.5)
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72, preset="real_scan_tuned_v1")

    segmented_payload = json.loads(
        (output_dir / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    straight_payload = json.loads(
        (output_dir / "primitive_ir" / "page_02.json").read_text(encoding="utf-8")
    )
    segmented_circles = [
        primitive for primitive in segmented_payload["primitives"] if primitive["type"] == "circle"
    ]
    straight_line_circles = [
        primitive for primitive in straight_payload["primitives"] if primitive["type"] == "circle"
    ]

    assert len(segmented_circles) == 1, (
        "reject the segmented vector arc but retain its independent raster circle"
    )
    segmented_center = segmented_circles[0]["geometry"]["center"]
    assert math.isclose(segmented_center["x"], 950, abs_tol=3)
    assert math.isclose(segmented_center["y"], 250, abs_tol=3)
    assert len(straight_line_circles) == 1, (
        "ordinary straight drafting linework must not suppress a raster circle"
    )


def test_run_pdf_rejects_split_path_partial_arc_and_chord(tmp_path: Path) -> None:
    pdf_path = tmp_path / "split-path-segmented-arc-and-controls.pdf"
    output_dir = tmp_path / "out"
    page_size = 400

    def add_partial_arc_and_chord(
        page: fitz.Page,
        center: fitz.Point,
        radius: float,
        *,
        fragment_count: int = 1,
    ) -> None:
        points = [
            fitz.Point(
                center.x + radius * math.cos(math.radians(degree)),
                center.y + radius * math.sin(math.radians(degree)),
            )
            for degree in range(356)
        ]
        segments = list(zip(points, points[1:]))
        for fragment_index in range(fragment_count):
            start_index = round(fragment_index * len(segments) / fragment_count)
            end_index = round((fragment_index + 1) * len(segments) / fragment_count)
            arc = page.new_shape()
            for start, end in segments[start_index:end_index]:
                arc.draw_line(start, end)
            arc.finish(color=(0.05, 0.05, 0.05), width=1.5, closePath=False)
            arc.commit()
        chord = page.new_shape()
        chord.draw_line(points[-1], points[0])
        chord.finish(color=(0.05, 0.05, 0.05), width=1.5, closePath=False)
        chord.commit()

    document = fitz.open()
    split_page = document.new_page(width=page_size, height=page_size)
    add_partial_arc_and_chord(split_page, fitz.Point(200, 200), 70)

    microfragment_page = document.new_page(width=page_size, height=page_size)
    add_partial_arc_and_chord(
        microfragment_page,
        fitz.Point(200, 200),
        70,
        fragment_count=30,
    )

    circle_page = document.new_page(width=page_size, height=page_size)
    circle_points = [
        fitz.Point(
            200 + 70 * math.cos(math.radians(360.0 * index / 64)),
            200 + 70 * math.sin(math.radians(360.0 * index / 64)),
        )
        for index in range(64)
    ]
    full_circle = circle_page.new_shape()
    for start, end in zip(circle_points, circle_points[1:] + circle_points[:1]):
        full_circle.draw_line(start, end)
    full_circle.finish(color=(0.05, 0.05, 0.05), width=1.5)
    full_circle.commit()

    raster_page = document.new_page(width=page_size, height=page_size)
    raster = np.full((page_size, page_size, 3), 220, dtype=np.uint8)
    raster_center = (80, 80)
    raster_radius = 25
    cv2.circle(raster, raster_center, raster_radius, (20, 20, 20), 2, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", raster)
    assert success
    raster_page.insert_image(raster_page.rect, stream=encoded.tobytes())
    add_partial_arc_and_chord(raster_page, fitz.Point(280, 280), 55)
    document.save(pdf_path)
    document.close()

    raster_document = fitz.open(pdf_path)
    split_render = tmp_path / "split-path.png"
    microfragment_render = tmp_path / "microfragment-path.png"
    raster_document[0].get_pixmap(matrix=fitz.Matrix(1.0, 1.0), alpha=False).save(
        split_render
    )
    raster_document[1].get_pixmap(matrix=fitz.Matrix(1.0, 1.0), alpha=False).save(
        microfragment_render
    )
    raster_document.close()
    pre_gate_ir = tmp_path / "pre-gate.json"
    run_image(str(split_render), str(pre_gate_ir), scale_mm_per_px=1.0)
    assert _has_circle_near(_circle_primitives(pre_gate_ir), (200, 200), 70), (
        "the red control must prove raster Hough actually proposes the unsupported circle"
    )
    microfragment_pre_gate_ir = tmp_path / "microfragment-pre-gate.json"
    run_image(str(microfragment_render), str(microfragment_pre_gate_ir), scale_mm_per_px=1.0)
    assert _has_circle_near(
        _circle_primitives(microfragment_pre_gate_ir), (200, 200), 70
    ), "the fragmented-path red control must prove Hough proposes the unsupported circle"

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72, preset="real_scan_tuned_v1")

    split_circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    microfragment_circles = _circle_primitives(output_dir / "primitive_ir" / "page_02.json")
    full_circles = _circle_primitives(output_dir / "primitive_ir" / "page_03.json")
    raster_circles = _circle_primitives(output_dir / "primitive_ir" / "page_04.json")
    assert split_circles == [], (
        "separate vector paths for an arc and chord cannot witness a full circle"
    )
    assert microfragment_circles == [], (
        "many short open arc paths and a separate chord cannot bypass the full-circle witness gate"
    )
    assert _has_circle_near(full_circles, (200, 200), 70), "a complete source circle must survive"
    assert len(raster_circles) == 1, (
        "the independent raster circle must survive the uncertain vector paths"
    )
    raster_circle_center = raster_circles[0]["geometry"]["center"]
    assert math.isclose(raster_circle_center["x"], raster_center[0], abs_tol=3)
    assert math.isclose(raster_circle_center["y"], page_size - raster_center[1], abs_tol=3)


def test_run_pdf_keeps_source_supported_line_segmented_circle(tmp_path: Path) -> None:
    pdf_path = tmp_path / "line-segmented-source-circle.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()
    page = document.new_page(width=120, height=120)
    center = fitz.Point(60, 60)
    radius = 21.25
    points = [
        fitz.Point(
            center.x + radius * math.cos(math.radians(360.0 * index / 32)),
            center.y + radius * math.sin(math.radians(360.0 * index / 32)),
        )
        for index in range(32)
    ]
    shape = page.new_shape()
    for start, end in zip(points, points[1:] + points[:1]):
        shape.draw_line(start, end)
    shape.finish(color=(0.05, 0.05, 0.05), width=1.5)
    shape.commit()
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    assert _has_circle_near(circles, (120, 120), 42.5), (
        "a complete, source-visible circle drawn as connected line segments must survive source gating"
    )


def test_run_pdf_keeps_consecutive_single_line_concentric_cycles_when_raster_aliases(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "separate-line-record-concentric-circles.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()
    page = document.new_page(width=120, height=120)
    center = fitz.Point(60, 60)
    radii = (20.0, 20.25, 21.0)
    for radius in radii:
        points = [
            fitz.Point(
                center.x + radius * math.cos(math.radians(360.0 * index / 32)),
                center.y + radius * math.sin(math.radians(360.0 * index / 32)),
            )
            for index in range(32)
        ]
        for start, end in zip(points, points[1:] + points[:1]):
            page.draw_line(start, end, color=(0.05, 0.05, 0.05), width=0.6)
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    actual_radii = sorted(circle["geometry"]["radius"] for circle in circles)
    assert len(actual_radii) == 3, (
        "each distinct, closed source cycle must survive even when raster Hough candidates alias"
    )
    assert np.allclose(actual_radii, sorted(radius * 2.0 for radius in radii), atol=0.2), (
        f"source vector radii should remain distinct and exact; got {actual_radii}"
    )


def test_geometry_owner_materializes_source_cycles_when_raster_candidates_alias(
    monkeypatch,
) -> None:
    image = np.full((240, 240, 3), 255, dtype=np.uint8)
    cv2.circle(image, (100, 100), 21, (0, 0, 0), thickness=2)
    cv2.circle(image, (180, 180), 15, (0, 0, 0), thickness=2)
    aliased_raster_circle = RawCircle(
        id="aliased", center_px=(100.0, 100.0), radius_px=20.5,
        confidence=0.75, bbox_px=(79.5, 79.5, 120.5, 120.5),
    )
    independent_raster_circle = RawCircle(
        id="independent", center_px=(180.0, 180.0), radius_px=15.0,
        confidence=0.75, bbox_px=(165.0, 165.0, 195.0, 195.0),
    )
    monkeypatch.setattr(
        geometry_extraction,
        "extract_circles",
        lambda *_args, **_kwargs: [aliased_raster_circle, independent_raster_circle],
    )
    monkeypatch.setattr(geometry_extraction, "extract_lines", lambda *_args, **_kwargs: [])

    raw_geometry = geometry_extraction.extract_raw_geometry(
        image,
        preset="default",
        pdf_vector_circle_witnesses=[
            (100.0, 100.0, 20.0),
            (100.0, 100.0, 20.25),
            (100.0, 100.0, 21.0),
            (100.0, 100.0, 21.0),
            (100.0, 100.0, float("nan")),
        ],
    )

    assert sorted(circle.radius_px for circle in raw_geometry.circles) == [
        15.0, 20.0, 20.25, 21.0,
    ], "exact source cycles should survive raster aliasing, while duplicates collapse"
    assert raw_geometry.circles[0] is independent_raster_circle, (
        "an unrelated source-supported raster circle must remain intact"
    )


@pytest.mark.parametrize(
    ("witness", "max_radius", "rejection_reason"),
    [
        ((102.0, 100.0, 22.0), 20, "configured radius limit"),
        ((102.0, 100.0, 23.0), 200, "distributed source support"),
    ],
)
def test_rejected_vector_witness_does_not_suppress_supported_raster_circle(
    monkeypatch, witness, max_radius, rejection_reason,
) -> None:
    image = np.full((240, 240, 3), 255, dtype=np.uint8)
    cv2.circle(image, (100, 100), 20, (0, 0, 0), thickness=2)
    raster_circle = RawCircle(
        id="raster", center_px=(100.0, 100.0), radius_px=20.0,
        confidence=0.75, bbox_px=(80.0, 80.0, 120.0, 120.0),
    )
    monkeypatch.setattr(
        geometry_extraction, "extract_circles", lambda *_args, **_kwargs: [raster_circle]
    )
    monkeypatch.setattr(geometry_extraction, "extract_lines", lambda *_args, **_kwargs: [])

    raw_geometry = geometry_extraction.extract_raw_geometry(
        image,
        preset="default",
        max_radius=max_radius,
        pdf_vector_circle_witnesses=[witness],
    )

    assert raw_geometry.circles == [raster_circle], (
        f"a witness rejected by {rejection_reason} must not suppress an "
        "independently source-supported raster circle"
    )


def test_only_validated_pdf_circle_witness_skips_redundant_raster_ridge(
    monkeypatch,
) -> None:
    image = np.full((240, 240, 3), 255, dtype=np.uint8)
    witness = (100.0, 100.0, 20.0)
    monkeypatch.setattr(geometry_extraction, "extract_circles", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(geometry_extraction, "extract_lines", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        geometry_extraction,
        "_circle_has_distributed_source_support",
        lambda *_args, **_kwargs: False,
    )

    unvalidated = geometry_extraction.extract_raw_geometry(
        image,
        pdf_vector_circle_witnesses=[witness],
    )
    validated = geometry_extraction.extract_raw_geometry(
        image,
        validated_pdf_vector_circle_witnesses=[witness],
    )

    assert unvalidated.circles == [], "unvalidated tuples still need raster support"
    assert [
        (circle.center_px, circle.radius_px) for circle in validated.circles
    ] == [((100.0, 100.0), 20.0)]


def test_extreme_source_circle_radius_is_rejected_before_unbounded_sampling(
    monkeypatch,
) -> None:
    source_gray = np.full((100, 100), 255, dtype=np.uint8)
    original_linspace = geometry_extraction.np.linspace
    requested_sample_counts: list[int] = []

    def bounded_linspace(*args, **kwargs):
        sample_count = int(kwargs.get("num", args[2] if len(args) > 2 else 50))
        requested_sample_counts.append(sample_count)
        assert sample_count <= 32_768, "circle witness exceeded the sample budget"
        return original_linspace(*args, **kwargs)

    monkeypatch.setattr(geometry_extraction.np, "linspace", bounded_linspace)

    assert not geometry_extraction._circle_has_distributed_source_support(
        source_gray, 50.0, 50.0, 10_000_000.0
    )
    assert requested_sample_counts == []


def test_run_image_only_forwards_pdf_circle_evidence_without_mutating_geometry(
    tmp_path: Path, monkeypatch,
) -> None:
    image_path = tmp_path / "input.png"
    image_path.write_bytes(b"test image bytes")
    image = np.full((30, 40, 3), 255, dtype=np.uint8)
    raster_circle = RawCircle(
        id="raster", center_px=(5.0, 5.0), radius_px=3.0,
        confidence=0.75, bbox_px=(2.0, 2.0, 8.0, 8.0),
    )
    raw_geometry = RawGeometry(circles=[raster_circle])
    captured: dict = {}

    monkeypatch.setattr(run_image_module.cv2, "imread", lambda _path: image)

    def extract(_image, **kwargs):
        captured["extract_kwargs"] = kwargs
        return raw_geometry

    def build_document(**kwargs):
        captured["raw_circles"] = kwargs["raw_circles"]
        return SimpleNamespace(cross_validations=[])

    monkeypatch.setattr(run_image_module, "extract_raw_geometry", extract)
    monkeypatch.setattr(run_image_module, "build_document", build_document)
    monkeypatch.setattr(run_image_module, "cross_validate", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(run_image_module, "save_document", lambda *_args, **_kwargs: None)

    witnesses = [(25.0, 20.0, 8.0)]
    validated_witnesses = [(32.0, 21.0, 7.0)]
    suspect_regions = [(1.0, 2.0, 3.0, 4.0)]
    run_image(
        image_path=str(image_path),
        output_path=str(tmp_path / "out" / "primitive_ir.json"),
        scale_mm_per_px=1.0,
        pdf_vector_circle_witnesses=witnesses,
        validated_pdf_vector_circle_witnesses=validated_witnesses,
        pdf_vector_circle_suspect_regions=suspect_regions,
        require_pdf_vector_circle_witness=True,
    )

    assert captured["extract_kwargs"] == {
        "preset": "real_scan_tuned_v1",
        "pdf_vector_circle_witnesses": witnesses,
        "validated_pdf_vector_circle_witnesses": validated_witnesses,
        "pdf_vector_circle_suspect_regions": suspect_regions,
        "require_pdf_vector_circle_witness": True,
    }
    assert captured["raw_circles"] == [raster_circle]
    assert captured["raw_circles"][0] is raster_circle


def test_run_pdf_deduplicates_duplicate_single_line_circle_paint(tmp_path: Path) -> None:
    pdf_path = tmp_path / "duplicate-single-line-circle-paint.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()
    page = document.new_page(width=120, height=120)
    center = fitz.Point(60, 60)
    radius = 21.25
    points = [
        fitz.Point(
            center.x + radius * math.cos(math.radians(360.0 * index / 32)),
            center.y + radius * math.sin(math.radians(360.0 * index / 32)),
        )
        for index in range(32)
    ]
    for _ in range(2):
        for start, end in zip(points, points[1:] + points[:1]):
            page.draw_line(start, end, color=(0.05, 0.05, 0.05), width=0.6)
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    assert len(circles) == 1, "duplicate paint of one source cycle must not emit duplicate circles"
    assert math.isclose(circles[0]["geometry"]["radius"], radius * 2.0, abs_tol=0.2)


def test_run_pdf_does_not_promote_single_line_record_arc_plus_chord(tmp_path: Path) -> None:
    pdf_path = tmp_path / "single-line-record-arc-plus-chord.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()
    page = document.new_page(width=120, height=120)
    center = fitz.Point(60, 60)
    radius = 30.0
    points = [
        fitz.Point(
            center.x + radius * math.cos(math.radians(355.0 * index / 35)),
            center.y + radius * math.sin(math.radians(355.0 * index / 35)),
        )
        for index in range(36)
    ]
    for start, end in zip(points, points[1:]):
        page.draw_line(start, end, color=(0.05, 0.05, 0.05), width=0.8)
    page.draw_line(points[-1], points[0], color=(0.05, 0.05, 0.05), width=0.8)
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    assert circles == [], "a separately recorded closing chord must not turn a partial arc into a circle"


def test_later_background_line_invalidates_single_record_circle_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=120, height=120)
    page.draw_rect(page.rect, color=None, fill=(0.75, 0.75, 0.75))
    center = fitz.Point(60, 60)
    radius = 30.0
    points = [
        fitz.Point(
            center.x + radius * math.cos(math.radians(360.0 * index / 32)),
            center.y + radius * math.sin(math.radians(360.0 * index / 32)),
        )
        for index in range(32)
    ]
    for start, end in zip(points, points[1:] + points[:1]):
        page.draw_line(start, end, color=(0.05, 0.05, 0.05), width=0.8)
    page.draw_line((30, 60), (90, 60), color=(0.75, 0.75, 0.75), width=2.0)

    _, witnesses, suspects = _page_circle_witnesses(page, 2.0)
    document.close()

    assert witnesses == [], "later background-colored paint crossing the perimeter invalidates the cycle"
    assert suspects, "an occluded vector circle remains a bounded suspect region"


def test_same_color_later_stroke_requires_width_and_intersection_evidence() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_rect(page.rect, color=None, fill=(0.75, 0.75, 0.75))
    center = fitz.Point(300, 300)
    radius = 212.5
    circle_width = 1.5
    circle_color = (0.05, 0.05, 0.05)
    points = [
        fitz.Point(
            center.x + radius * math.cos(math.radians(360.0 * index / 128)),
            center.y + radius * math.sin(math.radians(360.0 * index / 128)),
        )
        for index in range(128)
    ]
    circle = page.new_shape()
    for start, end in zip(points, points[1:] + points[:1]):
        circle.draw_line(start, end)
    circle.finish(color=circle_color, width=circle_width)
    circle.commit()

    # Equal-width same-color drafting linework is the thin positive control.
    page.draw_line(
        (30, center.y), (570, center.y), color=circle_color, width=circle_width,
    )
    _, thin_witnesses, thin_suspects = _page_circle_witnesses(page, 1.0)
    assert len(thin_witnesses) == 1
    assert thin_suspects == []
    document.close()

    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_rect(page.rect, color=None, fill=(0.75, 0.75, 0.75))
    circle = page.new_shape()
    for start, end in zip(points, points[1:] + points[:1]):
        circle.draw_line(start, end)
    circle.finish(color=circle_color, width=circle_width)
    circle.commit()
    # This width is 0.245 * radius: it fell below the old 0.25 * radius
    # exemption while still being far wider than the circle's source stroke.
    page.draw_line(
        (30, center.y), (570, center.y), color=circle_color, width=52.0625,
    )
    _, crossing_witnesses, crossing_suspects = _page_circle_witnesses(page, 1.0)
    document.close()

    assert crossing_witnesses == [], (
        "a wider same-color stroke crossing the source contour must not be "
        "skipped solely because it is below a radius-based threshold"
    )
    assert crossing_suspects, "a contour with uncertain occlusion remains a bounded suspect"

    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_rect(page.rect, color=None, fill=(0.75, 0.75, 0.75))
    circle = page.new_shape()
    for start, end in zip(points, points[1:] + points[:1]):
        circle.draw_line(start, end)
    circle.finish(color=circle_color, width=circle_width)
    circle.commit()
    # Width alone cannot invalidate a witness when the line misses its perimeter.
    page.draw_line((30, 30), (570, 30), color=circle_color, width=52.0625)
    _, distant_witnesses, distant_suspects = _page_circle_witnesses(page, 1.0)
    document.close()

    assert len(distant_witnesses) == 1
    assert distant_suspects == []


def test_same_color_stroke_width_fails_closed_except_explicit_hairline() -> None:
    hairline = {"type": "s", "color": (0.05, 0.05, 0.05), "width": 0.0}
    assert not _drawing_may_erase_circle(hairline, hairline["color"], 0.0)

    for width in (None, "invalid", float("nan"), float("inf"), -1.0, 10**1000):
        drawing = {"type": "s", "color": (0.05, 0.05, 0.05), "width": width}
        assert _drawing_may_erase_circle(drawing, drawing["color"], 1.5)

    missing_width = {"type": "s", "color": (0.05, 0.05, 0.05)}
    assert _drawing_may_erase_circle(missing_width, missing_width["color"], 1.5)


def test_single_line_cycle_with_parser_gap_is_not_a_circle_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=120, height=120)
    center = fitz.Point(60, 60)
    radius = 21.25
    points = [
        fitz.Point(
            center.x + radius * math.cos(math.radians(360.0 * index / 32)),
            center.y + radius * math.sin(math.radians(360.0 * index / 32)),
        )
        for index in range(32)
    ]
    for start, end in zip(points, points[1:]):
        page.draw_line(start, end, color=(0.05, 0.05, 0.05), width=0.8)
    page.draw_line(points[-1], fitz.Point(points[0].x + 0.05, points[0].y), color=(0.05, 0.05, 0.05), width=0.8)

    _, witnesses, suspects = _page_circle_witnesses(page, 2.0)
    document.close()

    assert witnesses == [], "a path gap beyond parser endpoint precision is not a closed contour"
    assert suspects, "a nearly closed curved source path must not silently disappear"


def test_single_line_hairline_records_are_eligible_for_source_reconstruction() -> None:
    center = fitz.Point(60, 60)
    radius = 21.25
    points = [
        fitz.Point(
            center.x + radius * math.cos(math.radians(360.0 * index / 32)),
            center.y + radius * math.sin(math.radians(360.0 * index / 32)),
        )
        for index in range(32)
    ]
    records = [
        {
            "type": "s",
            "fill": None,
            "color": (0.05, 0.05, 0.05),
            "width": 0.0,
            "dashes": "[] 0",
            "stroke_opacity": 1.0,
            "items": [("l", start, end)],
            "seqno": index,
        }
        for index, (start, end) in enumerate(zip(points, points[1:] + points[:1]))
    ]

    paths = _single_line_record_paths(records)

    assert len(paths) == 1
    assert paths[0][3] is True
    assert math.isclose(paths[0][2]["rect"].width, radius * 2.0, abs_tol=0.2)
    fitted = _fit_full_line_circle_path(paths[0][2], np.ones(3, dtype=np.float64))
    assert fitted is not None, "zero-width PDF hairlines remain visible stroke geometry"
    assert math.isclose(fitted[2], radius, abs_tol=0.1)


def test_interleaved_single_line_branch_breaks_contour_reconstruction() -> None:
    document = fitz.open()
    page = document.new_page(width=120, height=120)
    center = fitz.Point(60, 60)
    radius = 21.25
    points = [
        fitz.Point(
            center.x + radius * math.cos(math.radians(360.0 * index / 32)),
            center.y + radius * math.sin(math.radians(360.0 * index / 32)),
        )
        for index in range(32)
    ]
    for index, (start, end) in enumerate(zip(points, points[1:] + points[:1])):
        page.draw_line(start, end, color=(0.05, 0.05, 0.05), width=0.8)
        if index == 15:
            page.draw_line(center, end, color=(0.05, 0.05, 0.05), width=0.8)

    _, witnesses, suspects = _page_circle_witnesses(page, 2.0)
    document.close()

    assert witnesses == [], "a branch inserted into the source record sequence is ambiguous"
    assert suspects, "the broken curved record sequence remains a bounded suspect"


def test_line_segmented_circle_witness_requires_known_contrast() -> None:
    document = fitz.open()
    document.new_page(width=120, height=120)
    document.new_page(width=120, height=120)
    white_page = document[0]
    gray_page = document[1]
    gray_page.draw_rect(gray_page.rect, color=None, fill=(0.75, 0.75, 0.75))
    for page, color in ((white_page, (1.0, 1.0, 1.0)), (gray_page, (0.05, 0.05, 0.05))):
        center = fitz.Point(60, 60)
        radius = 21.25
        points = [
            fitz.Point(
                center.x + radius * math.cos(math.radians(360.0 * index / 32)),
                center.y + radius * math.sin(math.radians(360.0 * index / 32)),
            )
            for index in range(32)
        ]
        shape = page.new_shape()
        for start, end in zip(points, points[1:] + points[:1]):
            shape.draw_line(start, end)
        shape.finish(color=color, width=1.5)
        shape.commit()

    _, white_witnesses, white_suspects = _page_circle_witnesses(white_page, 2.0)
    _, gray_witnesses, gray_suspects = _page_circle_witnesses(gray_page, 2.0)
    document.close()

    assert white_witnesses == [], (
        "a line path matching white paper must not witness a visible circle"
    )
    assert white_suspects, "an invisible line contour remains a suspect source region"
    assert len(gray_witnesses) == 1, (
        "a dark line circle may witness against a known gray paper background"
    )
    assert gray_suspects == []


def test_run_pdf_rejects_line_segmented_polygon_and_ellipse_as_circle(tmp_path: Path) -> None:
    pdf_path = tmp_path / "line-segmented-polygon-and-ellipse.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()

    polygon = document.new_page(width=120, height=120)
    polygon_center = fitz.Point(60, 60)
    polygon_radius = 21.25
    polygon_points = [
        fitz.Point(
            polygon_center.x + polygon_radius * math.cos(math.radians(360.0 * index / 16)),
            polygon_center.y + polygon_radius * math.sin(math.radians(360.0 * index / 16)),
        )
        for index in range(16)
    ]
    polygon_shape = polygon.new_shape()
    for start, end in zip(polygon_points, polygon_points[1:] + polygon_points[:1]):
        polygon_shape.draw_line(start, end)
    polygon_shape.finish(color=(0.05, 0.05, 0.05), width=1.5)
    polygon_shape.commit()

    ellipse = document.new_page(width=120, height=120)
    ellipse_center = fitz.Point(60, 60)
    ellipse_shape = ellipse.new_shape()
    ellipse_points = [
        fitz.Point(
            ellipse_center.x + 30 * math.cos(math.radians(360.0 * index / 32)),
            ellipse_center.y + 15 * math.sin(math.radians(360.0 * index / 32)),
        )
        for index in range(32)
    ]
    for start, end in zip(ellipse_points, ellipse_points[1:] + ellipse_points[:1]):
        ellipse_shape.draw_line(start, end)
    ellipse_shape.finish(color=(0.05, 0.05, 0.05), width=1.5)
    ellipse_shape.commit()

    document.save(pdf_path)
    document.close()
    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    polygon_circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    ellipse_circles = _circle_primitives(output_dir / "primitive_ir" / "page_02.json")
    assert not _has_circle_near(polygon_circles, (120, 120), 42.5), (
        "a closed polygon must not be promoted to a source circle"
    )
    assert not _has_circle_near(ellipse_circles, (120, 120), 45), (
        "a line-segmented ellipse must remain distinct from a source circle"
    )


def test_run_pdf_rejects_open_line_ellipse_without_suppressing_crossed_raster_circle(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "open-line-ellipse-and-crossed-raster-circle.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()

    ellipse_page = document.new_page(width=400, height=400)
    ellipse_center = fitz.Point(200, 200)
    ellipse_points = [
        fitz.Point(
            ellipse_center.x + 70 * math.cos(math.radians(degree)),
            ellipse_center.y + 62 * math.sin(math.radians(degree)),
        )
        for degree in range(0, 356, 5)
    ]
    ellipse_shape = ellipse_page.new_shape()
    for start, end in zip(ellipse_points, ellipse_points[1:]):
        ellipse_shape.draw_line(start, end)
    ellipse_shape.finish(color=(0.05, 0.05, 0.05), width=1.5, closePath=False)
    ellipse_shape.commit()

    raster_page = document.new_page(width=400, height=400)
    raster = np.full((400, 400, 3), 220, dtype=np.uint8)
    cv2.circle(raster, (200, 200), 65, (20, 20, 20), 3, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", raster)
    assert success
    raster_page.insert_image(raster_page.rect, stream=encoded.tobytes())
    raster_page.draw_line((130, 200), (270, 200), color=(0.05, 0.05, 0.05), width=1.5)

    document.save(pdf_path)
    document.close()

    rendered = fitz.open(pdf_path)
    ellipse_render = tmp_path / "open-ellipse.png"
    rendered[0].get_pixmap(dpi=72, alpha=False).save(ellipse_render)
    rendered.close()
    assert _raw_hough_has_circle_near(
        ellipse_render, (200, 200), 66, center_tolerance=16, radius_tolerance=14
    ), "raw Hough must prove it proposes the ellipse-induced circle candidate"

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72, preset="real_scan_tuned_v1")

    ellipse_circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    crossed_raster_circles = _circle_primitives(output_dir / "primitive_ir" / "page_02.json")
    assert not _has_circle_near(
        ellipse_circles, (200, 200), 66, center_tolerance=16, radius_tolerance=14
    ), "the open-ellipse Hough candidate must be rejected by PDF source gating"
    assert _has_circle_near(crossed_raster_circles, (200, 200), 65), (
        "a straight drafting line crossing an independent raster circle must not suppress it"
    )


def _dimension_arrowhead_fixture(*, include_leader: bool = True) -> tuple[tuple[float, float, float], list[dict]]:
    # Translated source-proven B041 topology: a short axis segment meets the
    # closed filled triangle, and a longer leader continues from the same node.
    dx, dy = -300.0, -170.0

    def point(x: float, y: float) -> fitz.Point:
        return fitz.Point(x + dx, y + dy)

    triangle_points = [
        point(355.32, 239.50),
        point(348.84, 242.92),
        point(356.04, 242.38),
    ]
    line = {
        "type": "s",
        "seqno": 1,
        "items": [("l", point(355.68, 240.94), point(348.84, 242.92))],
    }
    fill = {
        "type": "fs",
        "fill": (0.0, 0.0, 0.0),
        "width": 0.72,
        "seqno": 2,
        "items": [
            ("l", triangle_points[i], triangle_points[(i + 1) % 3])
            for i in range(3)
        ],
    }
    drawings = [line, fill]
    if include_leader:
        drawings.append({
            "type": "s",
            "seqno": 4,
            "items": [
                ("l", point(355.68, 240.94), point(369.36, 237.16)),
                ("l", point(369.36, 237.16), point(444.24, 216.64)),
            ],
        })
    return (69.36, 67.16, 21.2657), drawings


def test_dimension_arrowhead_overprint_requires_attached_axis_and_leader() -> None:
    circle, drawings = _dimension_arrowhead_fixture()

    assert _dimension_arrowhead_fill(drawings, 1, circle)

    _, without_leader = _dimension_arrowhead_fixture(include_leader=False)
    assert not _dimension_arrowhead_fill(without_leader, 1, circle)

    _, misaligned = _dimension_arrowhead_fixture()
    misaligned[2]["items"][0] = (
        "l",
        fitz.Point(55.68, 70.94),
        fitz.Point(78.0, 80.0),
    )
    assert not _dimension_arrowhead_fill(misaligned, 1, circle)


def test_dimension_arrowhead_overprint_uses_actual_polygon_and_local_limit() -> None:
    circle, drawings = _dimension_arrowhead_fixture()
    triangle = [
        (point.x, point.y)
        for _, point, _ in drawings[1]["items"]
    ]

    coverage = _circle_fill_coverage_fraction(circle, triangle)
    assert 0.0 < coverage <= 0.08

    oversized = [(39.0, 37.0), (99.0, 37.0), (69.0, 97.0)]
    assert _circle_fill_coverage_fraction(circle, oversized) > 0.08

    _, oversized_drawings = _dimension_arrowhead_fixture()
    oversized_drawings[1]["items"] = [
        ("l", fitz.Point(*oversized[i]), fitz.Point(*oversized[(i + 1) % 3]))
        for i in range(3)
    ]
    assert not _dimension_arrowhead_fill(oversized_drawings, 1, circle)


def test_unassociated_triangle_remains_a_circle_occluder() -> None:
    document = fitz.open()
    page = document.new_page(width=160, height=140)
    page.draw_circle((69.36, 67.16), 21.2657, color=(0.05, 0.05, 0.05), width=0.72)
    circle, drawings = _dimension_arrowhead_fixture(include_leader=False)
    line, fill = drawings
    page.draw_line(line["items"][0][1], line["items"][0][2], color=(0.0, 0.0, 0.0), width=0.5)
    shape = page.new_shape()
    points = [start for _, start, _ in fill["items"]]
    shape.draw_polyline(points + [points[0]])
    shape.finish(color=None, fill=(0.0, 0.0, 0.0), width=0.72, closePath=True)
    shape.commit()

    _, witnesses, suspects = _page_circle_witnesses(page, 1.0)

    assert not witnesses
    assert suspects
    document.close()


@pytest.mark.real_data
def test_nakuja_page_group_recovers_only_the_two_dimensioned_circles(tmp_path: Path) -> None:
    pdf_value = os.environ.get("CAD_AGENT_NAKUJA_CIRCLE_PDF")
    if not pdf_value:
        pytest.skip("set CAD_AGENT_NAKUJA_CIRCLE_PDF to the approved private Nakuja PDF")
    pdf_path = Path(pdf_value)
    assert pdf_path.is_file(), "CAD_AGENT_NAKUJA_CIRCLE_PDF must point to the approved PDF"
    assert hashlib.sha256(pdf_path.read_bytes()).hexdigest() == (
        "c9411e6769725c252425da18380a76b4db07036ad2b7801ceabc11d17f8a246c"
    ), "Nakuja source identity changed"

    output_dir = tmp_path / "nakuja-circle-output"
    run_pdf(
        pdf_path,
        output_dir,
        scale_mm_per_px=0.0587963,
        dpi=144,
        preset="real_scan_tuned_v1",
    )
    ir_path = output_dir / "primitive_ir" / "page_01.json"
    circles = _circle_primitives(ir_path)
    assert len(circles) == 2, f"unexpected circle candidates: {circles}"
    geometries = [circle["geometry"] for circle in circles]
    centers = [
        (geometry["center"]["x"], geometry["center"]["y"])
        for geometry in geometries
    ]
    radii = sorted(float(geometry["radius"]) for geometry in geometries)
    assert centers[0] == pytest.approx(centers[1], abs=0.05)
    assert radii == pytest.approx([19.75, 25.0], abs=0.1)

    from dxf_builder_lib.builder import build_dxf
    from dxf_builder_lib.reviewer import review_dxf
    from semantic_ir_lib.io_utils import load_primitive_ir_document

    build = build_dxf(
        load_primitive_ir_document(str(ir_path)),
        str(tmp_path / "nakuja-circles.dxf"),
    )
    review = review_dxf(build, strict_primitive_inventory=True)
    assert review.passed, review.mismatches
    assert len(build.handle_by_primitive_id) == len(circles) + 358
    assert not build.skipped_primitive_ids


@pytest.mark.real_data
def test_b041_pdf_preserves_three_source_supported_orthographic_circles(
    tmp_path: Path,
) -> None:
    pdf_value = os.environ.get("CAD_AGENT_B041_CIRCLE_PDF")
    if not pdf_value:
        pytest.skip("set CAD_AGENT_B041_CIRCLE_PDF to the approved private B041 PDF")
    pdf_path = Path(pdf_value)
    assert pdf_path.is_file(), "CAD_AGENT_B041_CIRCLE_PDF must point to the approved PDF"
    assert hashlib.sha256(pdf_path.read_bytes()).hexdigest() == (
        "bf853aee4ba9b8381476d5ef1fa930d48a478ea56c3fe097695d41210d3afbe3"
    ), "B041 source identity changed"

    output_dir = tmp_path / "b041-circle-output"
    # 25.4 / 144 converts rendered pixels to page millimetres only; this is not
    # modelspace calibration or evidence of physical dimensions.
    run_pdf(
        pdf_path,
        output_dir,
        scale_mm_per_px=25.4 / 144.0,
        dpi=144,
        preset="real_scan_tuned_v1",
    )

    circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    expected = (
        ((56.99125, 68.23075), 15.97190, "source path 98 / outer Ø32"),
        ((56.99125, 68.23075), 6.00137, "source path 99 / M12"),
        ((130.30714, 126.23300), 7.50207, "source path 68 / R7.50"),
    )
    missing = [
        label
        for center, radius, label in expected
        if not _has_circle_near(
            circles,
            center,
            radius,
            center_tolerance=1.0,
            radius_tolerance=0.5,
        )
    ]
    assert not missing, f"missing source-supported orthographic circles: {missing}"
    assert len(circles) == 3, f"unexpected circle candidates, including isometric false positives: {circles}"


@pytest.mark.real_data
def test_fastening_bar_preserves_two_complete_source_circle_witnesses(
    tmp_path: Path,
) -> None:
    pdf_value = os.environ.get("CAD_AGENT_FASTENING_BAR_CIRCLE_PDF")
    if not pdf_value:
        pytest.skip("set CAD_AGENT_FASTENING_BAR_CIRCLE_PDF to the approved private PDF")
    pdf_path = Path(pdf_value)
    assert pdf_path.is_file(), "CAD_AGENT_FASTENING_BAR_CIRCLE_PDF must point to the approved PDF"
    assert hashlib.sha256(pdf_path.read_bytes()).hexdigest() == (
        "bf374d514e47f25bf82b9227145e9c057ef398cb76226b2fd4be662b0596b1cd"
    ), "Fastening Bar source identity changed"

    expected_pdf_circles = ((181.17, 448.93, 6.93), (181.17, 307.27, 6.93))
    with fitz.open(pdf_path) as document:
        paths = []
        for drawing in document[0].get_drawings():
            rect = drawing["rect"]
            center = ((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2)
            radius = rect.width / 2
            if (
                len(drawing["items"]) == 4
                and all(item[0] == "c" for item in drawing["items"])
                and abs(rect.width - rect.height) <= 0.01
                and any(
                    abs(center[0] - x) <= 0.01
                    and abs(center[1] - y) <= 0.01
                    and abs(radius - r) <= 0.01
                    for x, y, r in expected_pdf_circles
                )
            ):
                paths.append((center, radius, drawing["items"]))
        assert len(paths) == 2, f"expected two complete source circles, found {paths}"
        for _, _, items in paths:
            assert np.hypot(
                items[0][1].x - items[-1][-1].x,
                items[0][1].y - items[-1][-1].y,
            ) <= 0.01

    output_dir = tmp_path / "fastening-bar-circle-output"
    run_pdf(
        pdf_path,
        output_dir,
        scale_mm_per_px=25.4 / 144.0,
        dpi=144,
        preset="real_scan_tuned_v1",
    )
    circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    expected_output = (
        ((63.91275, 51.53025), 2.44507),
        ((63.91275, 101.50475), 2.44507),
    )
    missing = [
        (center, radius)
        for center, radius in expected_output
        if not _has_circle_near(
            circles,
            center,
            radius,
            center_tolerance=0.25,
            radius_tolerance=0.15,
        )
    ]
    assert not missing, f"missing source-supported Fastening Bar circles: {missing}"
    assert len(circles) == 2, f"unexpected circle output: {circles}"
