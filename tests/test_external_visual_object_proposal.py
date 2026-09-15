from __future__ import annotations

import importlib


def test_compile_only_external_visual_object_proposal_contract_exists() -> None:
    module = importlib.import_module("cad_agent.source_fusion_proposal")

    compiler = getattr(module, "compile_external_visual_object_proposal", None)
    assert callable(compiler)
