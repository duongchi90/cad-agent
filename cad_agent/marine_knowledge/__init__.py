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
from .observer import normalize_observation, observe_dxf_bytes, observe_dxf_file
from .pack import (
    get_marine_knowledge_pack,
    get_marine_pack_status,
    is_marine_pack_enabled,
    lookup_term,
    query_rules,
)
from .skills import (
    build_marine_core_proposal,
    classify_marine_drawing,
    detect_drawing_gaps_and_conflicts,
    evaluate_regulation_applicability_and_submittal,
)
from .text_normalization import fold_marine_search_text, normalize_marine_cad_text

__all__ = [
    "MARINE_CHECK_RESULT_SCHEMA_VERSION",
    "MARINE_PACK_SCHEMA_VERSION",
    "MarineKnowledgeError",
    "SOURCE_MANIFEST_SCHEMA_VERSION",
    "build_marine_core_proposal",
    "classify_marine_drawing",
    "detect_drawing_gaps_and_conflicts",
    "evaluate_regulation_applicability_and_submittal",
    "fold_marine_search_text",
    "get_marine_knowledge_pack",
    "get_marine_pack_status",
    "get_marine_source_manifest",
    "is_marine_pack_enabled",
    "lookup_term",
    "normalize_marine_cad_text",
    "normalize_observation",
    "observe_dxf_bytes",
    "observe_dxf_file",
    "query_rules",
    "validate_check_result",
    "validate_knowledge_pack",
    "validate_source_manifest",
]
