"""Marine Knowledge Pack V0: source-grounded naval architecture terms, rules, and read-only checks."""

from .contracts import (
    MARINE_CHECK_RESULT_SCHEMA_VERSION,
    MARINE_PACK_SCHEMA_VERSION,
    MarineKnowledgeError,
    SOURCE_MANIFEST_SCHEMA_VERSION,
    SUPPORTED_REGULATIONS,
    validate_check_result,
    validate_knowledge_pack,
    validate_source_manifest,
    verify_source_citation,
)
from .evidence_binding import (
    ENGINEERING_FACT_SCHEMA_VERSION,
    PROVENANCE_CLASSES,
    VERIFICATION_STATES,
    build_engineering_fact,
    evaluate_dimension_fact,
    explain_fact_traceability,
    rebind_observation_dimensions,
    strip_mtext_formatting,
    validate_engineering_fact,
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
    audit_engineering_evidence_binding,
    build_marine_core_proposal,
    classify_marine_drawing,
    detect_drawing_gaps_and_conflicts,
    evaluate_regulation_applicability_and_submittal,
)
from .text_normalization import fold_marine_search_text, normalize_marine_cad_text

__all__ = [
    "ENGINEERING_FACT_SCHEMA_VERSION",
    "MARINE_CHECK_RESULT_SCHEMA_VERSION",
    "MARINE_PACK_SCHEMA_VERSION",
    "MarineKnowledgeError",
    "PROVENANCE_CLASSES",
    "SOURCE_MANIFEST_SCHEMA_VERSION",
    "SUPPORTED_REGULATIONS",
    "VERIFICATION_STATES",
    "audit_engineering_evidence_binding",
    "build_engineering_fact",
    "build_marine_core_proposal",
    "classify_marine_drawing",
    "detect_drawing_gaps_and_conflicts",
    "evaluate_dimension_fact",
    "evaluate_regulation_applicability_and_submittal",
    "explain_fact_traceability",
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
    "rebind_observation_dimensions",
    "strip_mtext_formatting",
    "validate_check_result",
    "validate_engineering_fact",
    "validate_knowledge_pack",
    "validate_source_manifest",
    "verify_source_citation",
]
