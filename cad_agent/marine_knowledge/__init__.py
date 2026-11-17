"""Marine Knowledge Pack V0: source-grounded naval architecture terms, rules, and read-only checks."""

from .contracts import (
    MARINE_CHECK_RESULT_SCHEMA_VERSION,
    MARINE_PACK_SCHEMA_VERSION,
    MarineKnowledgeError,
    SOURCE_MANIFEST_SCHEMA_VERSION,
    validate_check_result,
    validate_knowledge_pack,
    validate_source_manifest,
)
from .manifest import get_marine_source_manifest

__all__ = [
    "MARINE_CHECK_RESULT_SCHEMA_VERSION",
    "MARINE_PACK_SCHEMA_VERSION",
    "MarineKnowledgeError",
    "SOURCE_MANIFEST_SCHEMA_VERSION",
    "get_marine_source_manifest",
    "validate_check_result",
    "validate_knowledge_pack",
    "validate_source_manifest",
]
