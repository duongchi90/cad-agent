from pathlib import Path

import pytest

from primitive_ir_lib.calibration_registry import add_record, get_verified_scale


def test_registry_reuses_scale_only_for_same_file_hash(tmp_path: Path):
    image = tmp_path / "drawing.png"
    image.write_bytes(b"first")
    registry = tmp_path / "calibrations.json"
    add_record(registry, "fixture", image, 0.25, "Known 100 mm reference measured 400 px")
    assert get_verified_scale(registry, "fixture", image) == 0.25
    image.write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash"):
        get_verified_scale(registry, "fixture", image)