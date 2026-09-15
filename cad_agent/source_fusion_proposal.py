"""Compile-only boundary for external visual/object proposals.

This module is intentionally pre-fusion: proposal data is not accepted semantic
or PrimitiveIR evidence and this seam has no CAD or source mutation side effect.
"""

from __future__ import annotations


def compile_external_visual_object_proposal(*, proposal: object, expected_binding: object):
    """Compile an external visual proposal into a verification request."""
    raise NotImplementedError("EXTERNAL_VISUAL_OBJECT_PROPOSAL_NOT_IMPLEMENTED")


__all__ = ["compile_external_visual_object_proposal"]
