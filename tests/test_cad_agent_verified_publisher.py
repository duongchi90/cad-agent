"""Causal RED for the R7 publication composition boundary.

The first RED commit is intentionally production-free. It proves the public
R7 owner is genuinely missing on the accepted Gate-0B main before behavioral
coverage is expanded.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect


MODULE = "cad_agent.verified_publisher"


def _publisher_module():
    spec = importlib.util.find_spec(MODULE)
    assert spec is not None, "R7_VERIFIED_PUBLISHER_MISSING"
    return importlib.import_module(MODULE)


def test_r7_publication_composition_module_exists() -> None:
    module = _publisher_module()
    assert module.__name__ == MODULE


def test_r7_publication_composition_exposes_exact_public_entrypoints() -> None:
    module = _publisher_module()
    execute = getattr(module, "execute_verified_publication", None)
    validate = getattr(module, "validate_verified_publication_result", None)
    error = getattr(module, "VerifiedPublisherError", None)
    version = getattr(module, "R7_VERIFIED_PUBLICATION_RESULT_SCHEMA_VERSION", None)

    assert callable(execute), "R7_EXECUTE_PUBLIC_SEAM_MISSING"
    assert callable(validate), "R7_RESULT_VALIDATOR_PUBLIC_SEAM_MISSING"
    assert isinstance(error, type) and issubclass(error, ValueError)
    assert version == "r7-verified-publication-result-1.0"


def test_r7_execute_surface_requires_only_composition_inputs() -> None:
    module = _publisher_module()
    execute = getattr(module, "execute_verified_publication", None)
    assert callable(execute), "R7_EXECUTE_PUBLIC_SEAM_MISSING"

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
