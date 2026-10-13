import json
import math
from pathlib import Path

import pytest

from primitive_ir_lib.calibration_registry import add_record, file_sha256, get_verified_scale


def test_registry_reuses_scale_only_for_same_file_hash(tmp_path: Path):
    image = tmp_path / "drawing.png"
    image.write_bytes(b"first")
    registry = tmp_path / "calibrations.json"
    add_record(registry, "fixture", image, 0.25, "Known 100 mm reference measured 400 px")
    assert get_verified_scale(registry, "fixture", image) == 0.25
    image.write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash"):
        get_verified_scale(registry, "fixture", image)


@pytest.mark.parametrize("invalid_scale", [float("nan"), float("inf")], ids=["nan", "positive-infinity"])
def test_registry_writer_rejects_nonfinite_scale_without_changing_bytes(
    tmp_path: Path, invalid_scale: float,
):
    image = tmp_path / "synthetic.png"
    image.write_bytes(b"synthetic image bytes")
    registry = tmp_path / "calibrations.json"
    add_record(registry, "fixture", image, 0.25, "Known synthetic reference")
    before = registry.read_bytes()

    with pytest.raises(ValueError, match="finite|positive"):
        add_record(registry, "fixture", image, invalid_scale, "Known synthetic reference")

    assert registry.read_bytes() == before


@pytest.mark.parametrize("boolean_scale", [True, False], ids=["true", "false"])
@pytest.mark.parametrize("registry_exists", [False, True], ids=["create", "replace"])
def test_registry_writer_rejects_boolean_scale_without_creating_or_changing_registry(
    tmp_path: Path, boolean_scale: bool, registry_exists: bool,
):
    image = tmp_path / "synthetic.png"
    image.write_bytes(b"synthetic image bytes")
    registry = tmp_path / "calibrations.json"
    if registry_exists:
        add_record(registry, "fixture", image, 0.25, "Known synthetic reference")
        before = registry.read_bytes()

    with pytest.raises(ValueError, match="finite|positive|numeric"):
        add_record(registry, "fixture", image, boolean_scale, "Known synthetic reference")

    if registry_exists:
        assert registry.read_bytes() == before
    else:
        assert not registry.exists()


@pytest.mark.parametrize(
    "invalid_scale",
    [float("nan"), float("inf"), 0.0, -0.25],
    ids=["nan", "positive-infinity", "zero", "negative"],
)
def test_registry_reader_rejects_persisted_nonpositive_or_nonfinite_scale(
    tmp_path: Path, invalid_scale: float,
):
    image = tmp_path / "synthetic.png"
    image.write_bytes(b"synthetic image bytes")
    registry = tmp_path / "calibrations.json"
    add_record(registry, "fixture", image, 0.25, "Known synthetic reference")

    payload = json.loads(registry.read_text(encoding="utf-8"))
    record = payload["records"][0]
    record["scale_mm_per_px"] = invalid_scale
    registry.write_text(json.dumps(payload), encoding="utf-8")
    persisted = json.loads(registry.read_text(encoding="utf-8"))["records"][0]
    assert persisted["status"] == "verified"
    assert persisted["sha256"] == file_sha256(image)
    if math.isnan(invalid_scale):
        assert math.isnan(persisted["scale_mm_per_px"])
    else:
        assert persisted["scale_mm_per_px"] == invalid_scale

    with pytest.raises(ValueError, match="finite|positive"):
        get_verified_scale(registry, "fixture", image)


def test_registry_reader_keeps_finite_positive_and_candidate_status_controls(tmp_path: Path):
    image = tmp_path / "synthetic.png"
    image.write_bytes(b"synthetic image bytes")
    registry = tmp_path / "calibrations.json"
    add_record(registry, "fixture", image, 0.25, "Known synthetic reference")
    assert get_verified_scale(registry, "fixture", image) == 0.25

    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["records"][0]["status"] = "needs_verification"
    registry.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="No verified calibration"):
        get_verified_scale(registry, "fixture", image)


@pytest.mark.parametrize("boolean_scale", [True, False], ids=["true", "false"])
def test_registry_reader_rejects_persisted_boolean_scale_with_matching_hash(
    tmp_path: Path, boolean_scale: bool,
):
    image = tmp_path / "synthetic.png"
    image.write_bytes(b"synthetic image bytes")
    registry = tmp_path / "calibrations.json"
    add_record(registry, "fixture", image, 0.25, "Known synthetic reference")

    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["records"][0]["scale_mm_per_px"] = boolean_scale
    registry.write_text(json.dumps(payload), encoding="utf-8")
    persisted = json.loads(registry.read_text(encoding="utf-8"))["records"][0]
    assert persisted["status"] == "verified"
    assert persisted["sha256"] == file_sha256(image)
    assert persisted["scale_mm_per_px"] is boolean_scale

    with pytest.raises(ValueError, match="finite|positive|numeric"):
        get_verified_scale(registry, "fixture", image)
