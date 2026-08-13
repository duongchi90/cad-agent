"""Causal RED for the architecture-safe R7 publication composition boundary."""

from __future__ import annotations

import importlib
import importlib.util
import inspect


MODULE = "cad_agent.publication_composition"


def _r7_module():
    spec = importlib.util.find_spec(MODULE)
    assert spec is not None, "R7_PUBLICATION_COMPOSITION_MISSING"
    return importlib.import_module(MODULE)


def test_r7_publication_composition_module_exists() -> None:
    module = _r7_module()
    assert module.__name__ == MODULE


def test_r7_publication_composition_exposes_exact_public_entrypoints() -> None:
    module = _r7_module()
    assert callable(getattr(module, "execute_verified_publication", None))
    assert callable(getattr(module, "validate_verified_publication_result", None))
    error = getattr(module, "VerifiedPublisherError", None)
    assert isinstance(error, type) and issubclass(error, ValueError)
    assert (
        getattr(module, "R7_VERIFIED_PUBLICATION_RESULT_SCHEMA_VERSION", None)
        == "r7-verified-publication-result-1.0"
    )


def test_r7_execute_surface_requires_only_composition_inputs() -> None:
    module = _r7_module()
    execute = getattr(module, "execute_verified_publication", None)
    assert callable(execute)
    signature = inspect.signature(execute)
    assert list(signature.parameters) == [
        "run_id",
        "candidate_state",
        "r5_verdict_result",
        "auto_publish_authorization",
        "manifest_path",
        "expected_manifest_sha256",
        "candidate_path",
        "target_path",
    ]
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )
