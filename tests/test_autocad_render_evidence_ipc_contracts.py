from __future__ import annotations

import json
from pathlib import Path

IPC_ROOT = Path(__file__).parents[1] / "contracts/autocad-ipc"


def test_native_render_examples_do_not_fabricate_render_or_pdf_artifacts() -> None:
    result = json.loads(
        (IPC_ROOT / "examples/native-render-evidence-result.json").read_text(encoding="utf-8")
    )

    assert result["success"] is False
    assert result["errors"] == ["NATIVE_RENDER_NOT_IMPLEMENTED"]
    assert result["payload"] == {}
