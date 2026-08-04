from __future__ import annotations

import copy
from typing import Any

RUN_ID = "RUN-VISUAL-SYNTHETIC-001"
SOURCE_SHA = "1" * 64
DRAWING_SHA = "2" * 64
MUTATION_SHA = "3" * 64
RENDER_SHA = "4" * 64
REFERENCE_PACKAGE_SHA = "5" * 64
COMPARISON_SHA = "6" * 64
REVIEW_SHA = "7" * 64
INITIAL_TARGET_SHA = "8" * 64
PAGE_ID = "PAGE-001"
VIEW_ID = "SIDE"
REGION_ID = "SIDE-CABIN"
TARGET_PATH = "D:\\Synthetic\\drawing.dwg"
BACKUP_ROOT = "D:\\Synthetic\\Backups"


def clone(payload: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(payload)


def valid_visual_run_manifest() -> dict[str, Any]:
    return {
        "schema_version": "visual-run-manifest-1.0",
        "run_id": RUN_ID,
        "state": "CREATED",
        "authority": "DISPOSABLE_REVIEW",
        "source": {
            "source_type": "PDF",
            "source_sha256": SOURCE_SHA,
            "page_ids": [PAGE_ID],
        },
        "drawing": {
            "absolute_path": TARGET_PATH,
            "initial_sha256": DRAWING_SHA,
        },
        "evidence_root": "runs/RUN-VISUAL-SYNTHETIC-001",
        "latest_mutation_sha256": MUTATION_SHA,
    }
