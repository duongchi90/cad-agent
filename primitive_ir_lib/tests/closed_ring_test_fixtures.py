from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def write_circle_fixture(path: Path, center: tuple[int, int] = (64, 64)) -> None:
    image = np.full((128, 160, 3), 255, dtype=np.uint8)
    cv2.circle(image, center, 22, (0, 0, 0), 2, cv2.LINE_8)
    assert cv2.imwrite(str(path), image)
