"""Bounded real-source ARC extraction contract for Page-1 issue #409.

The approved source crop is private and intentionally not committed.  Set
``CAD_AGENT_PAGE1_CROP`` to run this focused causal test locally.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from cad_agent.fidelity import _render_layout_dxf
from primitive_ir_lib.assemble import arc_to_primitive
from primitive_ir_lib.geometry_extraction import extract_raw_geometry
from primitive_ir_lib.models import Calibration


_CROP_ENV = "CAD_AGENT_PAGE1_CROP"
_CANDIDATE_DXF_ENV = "CAD_AGENT_PAGE1_CANDIDATE_DXF"
_EXPECTED_CROP_SHA256 = "e04056a6606f2351f53756050311aefca4bb8248e25db4928e533633f4b195b7"
_EXPECTED_CANDIDATE_DXF_SHA256 = "fdf696a3b98ae6f8a40a5730a8d007bf2abc3a5ee914ee85c22ad120296f3669"
_COMPARATOR_KERNEL = np.ones((7, 7), dtype=np.uint8)
_EXPECTED_COMPONENTS = {
    "720": (474, (378, 465, 483, 536)),
    "501": (412, (366, 408, 519, 471)),
    "385": (316, (359, 362, 487, 394)),
}

pytestmark = pytest.mark.real_data


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_residual_components(crop: Path, candidate_dxf: Path) -> dict[str, np.ndarray]:
    image = cv2.imread(str(crop), cv2.IMREAD_COLOR)
    assert image is not None
    height, width = image.shape[:2]
    vector = _render_layout_dxf(
        candidate_dxf,
        width_mm=width * 0.17634073294549343,
        height_mm=height * 0.17634073294549343,
        width_px=width,
        height_px=height,
    )
    source_edges = cv2.Canny(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), 50, 150)
    vector_edges = cv2.Canny(cv2.cvtColor(vector, cv2.COLOR_BGR2GRAY), 50, 150)
    source_only = (source_edges > 0) & ~(
        cv2.dilate(vector_edges, _COMPARATOR_KERNEL) > 0
    )
    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(
        source_only.astype(np.uint8), connectivity=8
    )
    components: dict[str, np.ndarray] = {}
    for name, (expected_area, expected_bbox) in _EXPECTED_COMPONENTS.items():
        matches = []
        for label in range(1, component_count):
            x, y, width, height, area = stats[label]
            bbox = (int(x), int(y), int(x + width), int(y + height))
            if int(area) == expected_area and bbox == expected_bbox:
                matches.append(label)
        assert len(matches) == 1, name
        components[name] = labels == matches[0]
    return components


def _rasterize_arc(arc, shape: tuple[int, int]) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    angles = np.arange(arc.start_angle_deg, arc.end_angle_deg + 0.25, 0.25)
    points = np.column_stack(
        (
            arc.center_px[0] + arc.radius_px * np.cos(np.radians(angles)),
            arc.center_px[1] - arc.radius_px * np.sin(np.radians(angles)),
        )
    )
    points = np.rint(points).astype(np.int32).reshape((-1, 1, 2))
    cv2.polylines(mask, [points], isClosed=False, color=255, thickness=1)
    return mask


def _component_coverage(component: np.ndarray, arc, shape: tuple[int, int]) -> float:
    arc_mask = _rasterize_arc(arc, shape)
    tolerance = cv2.dilate(arc_mask, _COMPARATOR_KERNEL) > 0
    return float(np.logical_and(component, tolerance).sum() / max(1, component.sum()))


def _rasterize_arc_primitive(primitive, calibration: Calibration, shape: tuple[int, int]) -> np.ndarray:
    geometry = primitive.geometry
    scale = calibration.pixel_to_unit_scale
    center_x = geometry.center.x / scale + calibration.origin_px[0]
    center_y = calibration.origin_px[1] - geometry.center.y / scale
    radius = geometry.radius / scale
    start = geometry.start_angle_deg
    end = geometry.end_angle_deg
    if end <= start:
        end += 360.0
    angles = np.arange(start, end + 0.25, 0.25)
    points = np.column_stack(
        (
            center_x + radius * np.cos(np.radians(angles)),
            center_y - radius * np.sin(np.radians(angles)),
        )
    )
    mask = np.zeros(shape, dtype=np.uint8)
    cv2.polylines(
        mask,
        [np.rint(points).astype(np.int32).reshape((-1, 1, 2))],
        isClosed=False,
        color=255,
        thickness=1,
    )
    return mask


def _primitive_component_coverage(
    component: np.ndarray,
    primitive,
    calibration: Calibration,
    shape: tuple[int, int],
) -> float:
    primitive_mask = _rasterize_arc_primitive(primitive, calibration, shape)
    tolerance = cv2.dilate(primitive_mask, _COMPARATOR_KERNEL) > 0
    return float(np.logical_and(component, tolerance).sum() / max(1, component.sum()))


def test_page1_arc_extraction_red_green_contract():
    crop_value = os.environ.get(_CROP_ENV)
    candidate_value = os.environ.get(_CANDIDATE_DXF_ENV)
    if not crop_value or not candidate_value:
        pytest.skip(
            f"set {_CROP_ENV} and {_CANDIDATE_DXF_ENV} to run the approved Page-1 source-bound test"
        )
    crop = Path(crop_value)
    candidate_dxf = Path(candidate_value)
    if not crop.is_file():
        raise AssertionError(f"{_CROP_ENV} does not point to a file: {crop}")
    if not candidate_dxf.is_file():
        raise AssertionError(
            f"{_CANDIDATE_DXF_ENV} does not point to a file: {candidate_dxf}"
        )
    assert _sha256(crop) == _EXPECTED_CROP_SHA256
    assert _sha256(candidate_dxf) == _EXPECTED_CANDIDATE_DXF_SHA256

    image = cv2.imread(str(crop), cv2.IMREAD_COLOR)
    assert image is not None and tuple(image.shape[:2]) == (1608, 2261)
    geometry = extract_raw_geometry(image, preset="real_scan_tuned_v1")

    assert len(geometry.lines) == 520
    assert len(geometry.circles) == 19
    components = _source_residual_components(crop, candidate_dxf)

    coverage = {
        name: max(
            (_component_coverage(components[name], arc, image.shape[:2]) for arc in geometry.arcs),
            default=0.0,
        )
        for name in _EXPECTED_COMPONENTS
    }
    assert coverage["720"] >= 0.5, coverage
    assert coverage["501"] >= 0.5, coverage
    assert coverage["385"] < 0.5, coverage


def test_page1_arc_assembly_transform_red_green_contract():
    crop_value = os.environ.get(_CROP_ENV)
    candidate_value = os.environ.get(_CANDIDATE_DXF_ENV)
    if not crop_value or not candidate_value:
        pytest.skip(
            f"set {_CROP_ENV} and {_CANDIDATE_DXF_ENV} to run the approved Page-1 source-bound test"
        )
    crop = Path(crop_value)
    candidate_dxf = Path(candidate_value)
    if not crop.is_file():
        raise AssertionError(f"{_CROP_ENV} does not point to a file: {crop}")
    if not candidate_dxf.is_file():
        raise AssertionError(
            f"{_CANDIDATE_DXF_ENV} does not point to a file: {candidate_dxf}"
        )
    assert _sha256(crop) == _EXPECTED_CROP_SHA256
    assert _sha256(candidate_dxf) == _EXPECTED_CANDIDATE_DXF_SHA256

    image = cv2.imread(str(crop), cv2.IMREAD_COLOR)
    assert image is not None and tuple(image.shape[:2]) == (1608, 2261)
    geometry = extract_raw_geometry(image, preset="real_scan_tuned_v1")
    components = _source_residual_components(crop, candidate_dxf)
    calibration = Calibration(
        unit="mm",
        pixel_to_unit_scale=0.17634073294549343,
        origin_px=(0.0, 1608.0),
        method="manual_override",
        status="verified",
    )
    primitives = [arc_to_primitive(arc, calibration) for arc in geometry.arcs]
    coverage = {
        name: max(
            (
                _primitive_component_coverage(
                    components[name], primitive, calibration, image.shape[:2]
                )
                for primitive in primitives
            ),
            default=0.0,
        )
        for name in _EXPECTED_COMPONENTS
    }
    assert coverage["720"] >= 0.5, coverage
    assert coverage["501"] >= 0.5, coverage
    assert coverage["385"] < 0.5, coverage
