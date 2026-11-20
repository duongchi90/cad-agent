"""Fail-closed contract validators for Marine Knowledge Pack V0.

Reuses canonical JSON hashing and identifier discipline from
``cad_agent.drawing_contracts`` without adding runtime dependencies or altering
``CAD Core`` approval semantics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import hashlib
from io import BytesIO
from pathlib import Path
import re
from typing import Any
import unicodedata

from pypdf import PdfReader

from cad_agent.drawing_contracts import canonical_json_sha256

SOURCE_MANIFEST_SCHEMA_VERSION = "marine-source-manifest-1.0"
MARINE_PACK_SCHEMA_VERSION = "marine-knowledge-pack-1.0"
MARINE_CHECK_RESULT_SCHEMA_VERSION = "marine-check-result-1.0"

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SAFE_DRAWING_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_QCVN72_CONSOLIDATED_SHA256 = "4ffed2dad51f16d72bff5661a17be4d4793fe547133f999c41ded1ea72696b20"

_ALLOWED_PROPOSAL_ACTIONS = frozenset(
    {
        "FIX_TITLE_BLOCK_TYPE_MISMATCH",
        "RECONCILE_SERVICE_AREA_SCOPE",
        "CONFIRM_REGULATORY_SERVICE_AREA",
        "SET_INSUNITS_AND_VERIFY_CALIBRATION",
        "SET_INSUNITS_AND_COMPLETE_TITLE_BLOCK",
        "REVIEW_WATERTIGHT_BULKHEAD_SUBDIVISION",
        "REVIEW_DOUBLE_BOTTOM_SCANTLINGS",
        "VERIFY_SMALL_HULL_SCANTLINGS",
        "REQUEST_NATIVE_CAD_AND_CALIBRATION",
        "COMPLETE_TITLE_BLOCK_FIELDS",
        "VERIFY_LONGLINE_BOW_TO_RIGHT",
        "STANDARDIZE_TEXT_HEIGHTS_AT_SCALE",
        "CHECK_NON_UNIFORM_VERTICAL_SCALE",
        "RECONCILE_MAIN_ENGINE_SPECIFICATION",
        "RECONCILE_L_PARTICULAR",
        "RECONCILE_LPP_PARTICULAR",
        "RECONCILE_B_PARTICULAR",
        "RECONCILE_D_PARTICULAR",
        "RECONCILE_DRAFT_PARTICULAR",
        "RECONCILE_SHIP_TYPE_AND_HULL_ID",
        "RECONCILE_METRIC_CONFLICT",
        "VERIFY_CORRUPTED_NUMERIC_TEXT",
        "VERIFY_CAD_GEOMETRY_ENTITIES",
    }
)
_PROPOSAL_FIELDS = frozenset(
    {
        "proposal_id",
        "target_drawing_id",
        "action_kind",
        "cad_mutation",
        "proposal_only",
        "requires_cad_core_admission",
        "required_core_gates",
        "evidence",
        "reason",
    }
)

_ALLOWED_DRAFT_STATUSES = frozenset({"CANDIDATE_UNAPPROVED", "DRAFT_REVIEW_ONLY"})
_ALLOWED_RESULT_PACK_STATUSES = _ALLOWED_DRAFT_STATUSES | frozenset({"DISABLED"})
_ALLOWED_EXCERPT_DISPOSITIONS = frozenset({"PUBLIC_VERBATIM_EXCERPT", "PRIVATE_SOURCE_SUMMARY_ONLY"})
_ALLOWED_DOC_KINDS = frozenset(
    {
        "REGULATION",
        "TEXTBOOK",
        "DRAWING_SAMPLE",
        "PRIVATE_SAMPLE",
        "ARCHIVE_BUNDLE",
        "EXCLUDED_NON_MARINE",
    }
)
_ALLOWED_USAGE_RIGHTS = frozenset(
    {
        "PUBLIC_REGULATION_NO_REDISTRIBUTION",
        "OPEN_ACADEMIC_RESEARCH",
        "PRIVATE_LOCAL_NO_COMMIT",
        "INTERNAL_FIXTURE",
        "OUT_OF_SCOPE_EXCLUDED",
    }
)
_ALLOWED_USAGE_STATUSES = frozenset(
    {
        "ACTIVE_INDEXED",
        "SAMPLE_ONLY_READ_ONLY",
        "REFERENCE_METADATA_ONLY",
        "EXCLUDED_NON_MARINE",
    }
)
_ALLOWED_VERDICTS = frozenset({"PASS", "CONFLICT", "INSUFFICIENT_EVIDENCE", "NOT_APPLICABLE"})
_ALLOWED_RESULT_STATUSES = _ALLOWED_VERDICTS | frozenset({"DISABLED"})
_ALLOWED_CONFIDENCES = frozenset({"HIGH", "MEDIUM", "LOW"})

_SOURCE_FIELDS = frozenset(
    {
        "source_id",
        "title",
        "document_kind",
        "version",
        "origin",
        "sha256",
        "page_count",
        "applicable_scope",
        "usage_rights",
        "commit_prohibited",
        "usage_status",
        "notes",
    }
)
_MANIFEST_FIELDS = frozenset(
    {"schema_version", "manifest_id", "revision", "status", "sources", "manifest_sha256"}
)
_TERM_FIELDS = frozenset(
    {
        "term_id",
        "canonical_name_vi",
        "canonical_name_en",
        "aliases",
        "category",
        "source_id",
        "source_version",
        "clause",
        "pdf_page",
        "reg_page",
        "verbatim_excerpt",
        "excerpt_disposition",
        "technical_summary",
        "applicable_drawing_types",
        "approval_status",
    }
)
_RULE_FIELDS = frozenset(
    {
        "rule_id",
        "title",
        "source_id",
        "source_version",
        "clause",
        "pdf_page",
        "reg_page",
        "applicable_domains",
        "applicable_drawing_types",
        "conditions",
        "exceptions",
        "verbatim_excerpt",
        "excerpt_disposition",
        "technical_summary",
        "verification_method",
        "confidence_default",
        "limitation",
        "approval_status",
    }
)
_PACK_FIELDS = frozenset(
    {
        "schema_version",
        "id",
        "revision",
        "status",
        "cad_mutation",
        "default_core_behavior_changed",
        "domain_pack_compatibility",
        "domains",
        "drawing_types",
        "vocabulary",
        "source_manifest_sha256",
        "terms",
        "rules",
        "pack_sha256",
    }
)
_FINDING_FIELDS = frozenset(
    {
        "finding_id",
        "verdict",
        "rule_id",
        "source_id",
        "source_sha256",
        "source_version",
        "clause",
        "pdf_page",
        "reg_page",
        "pagination_basis",
        "conditions_applied",
        "exceptions_checked",
        "evidence",
        "reason",
        "confidence",
        "limitation",
    }
)
_CHECK_RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "skill_id",
        "pack_id",
        "pack_sha256",
        "pack_status",
        "cad_mutation",
        "regulatory_compliance_proven",
        "status",
        "summary",
        "observed_scope",
        "applicable_regulation_scope",
        "partial_package",
        "findings",
        "checks_executed",
        "checks_not_executed",
        "limitations",
        "proposal_only_actions",
    }
)


class MarineKnowledgeError(ValueError):
    """Raised when a Marine Knowledge Pack contract fails closed."""


def _fail(code: str) -> None:
    raise MarineKnowledgeError(code)


def _require_mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail(code)
    return dict(value)


def _require_non_empty_str(value: object, code: str) -> str:
    if type(value) is not str or not value.strip():
        _fail(code)
    return value


def _require_id(value: object, code: str) -> str:
    text = _require_non_empty_str(value, code)
    if _ID_RE.fullmatch(text) is None:
        _fail(code)
    return text


def _require_sha256(value: object, code: str) -> str:
    text = _require_non_empty_str(value, code)
    if _SHA256_RE.fullmatch(text) is None:
        _fail(code)
    return text


def _require_str_list(value: object, code: str, *, min_items: int = 0) -> list[str]:
    if not isinstance(value, list) or len(value) < min_items:
        _fail(code)
    return [_require_non_empty_str(item, code) for item in value]


def _require_pos_int_list(value: object, code: str, *, min_items: int = 0) -> list[int]:
    if not isinstance(value, list) or len(value) < min_items:
        _fail(code)
    for item in value:
        if type(item) is not int or item < 1:
            _fail(code)
    return list(value)


def seal_source_manifest(raw_manifest: Mapping[str, object]) -> dict[str, Any]:
    """Compute and attach canonical ``manifest_sha256`` to a manifest mapping."""
    payload = deepcopy(dict(raw_manifest))
    payload.pop("manifest_sha256", None)
    digest = canonical_json_sha256(payload)
    payload["manifest_sha256"] = digest
    return validate_source_manifest(payload)


def validate_source_manifest(payload: object) -> dict[str, Any]:
    """Validate a ``marine-source-manifest-1.0`` document and verify its SHA-256."""
    data = _require_mapping(payload, "MANIFEST_SCHEMA_INVALID")
    if set(data) != _MANIFEST_FIELDS:
        _fail("MANIFEST_SCHEMA_INVALID")
    if data["schema_version"] != SOURCE_MANIFEST_SCHEMA_VERSION:
        _fail("MANIFEST_SCHEMA_INVALID")
    _require_id(data["manifest_id"], "MANIFEST_ID_INVALID")
    _require_non_empty_str(data["revision"], "MANIFEST_REVISION_INVALID")
    if data["status"] not in _ALLOWED_DRAFT_STATUSES:
        _fail("MANIFEST_APPROVAL_STATUS_FORBIDDEN")

    sources = data["sources"]
    if not isinstance(sources, list) or not sources:
        _fail("MANIFEST_SOURCES_EMPTY")
    seen_ids: set[str] = set()
    for raw_src in sources:
        src = _require_mapping(raw_src, "MANIFEST_SOURCE_INVALID")
        if set(src) != _SOURCE_FIELDS:
            _fail("MANIFEST_SOURCE_SCHEMA_INVALID")
        sid = _require_id(src["source_id"], "MANIFEST_SOURCE_ID_INVALID")
        if sid in seen_ids:
            _fail("MANIFEST_DUPLICATE_SOURCE_ID")
        seen_ids.add(sid)
        _require_non_empty_str(src["title"], "MANIFEST_SOURCE_TITLE_INVALID")
        if src["document_kind"] not in _ALLOWED_DOC_KINDS:
            _fail("MANIFEST_SOURCE_KIND_INVALID")
        _require_non_empty_str(src["version"], "MANIFEST_SOURCE_VERSION_INVALID")
        _require_non_empty_str(src["origin"], "MANIFEST_SOURCE_ORIGIN_INVALID")
        _require_sha256(src["sha256"], "MANIFEST_SOURCE_SHA256_INVALID")
        page_count = src["page_count"]
        if page_count is not None and (type(page_count) is not int or page_count < 1):
            _fail("MANIFEST_SOURCE_PAGE_COUNT_INVALID")
        _require_str_list(src["applicable_scope"], "MANIFEST_SOURCE_SCOPE_INVALID")
        if src["usage_rights"] not in _ALLOWED_USAGE_RIGHTS:
            _fail("MANIFEST_SOURCE_RIGHTS_INVALID")
        if type(src["commit_prohibited"]) is not bool:
            _fail("MANIFEST_SOURCE_COMMIT_FLAG_INVALID")
        if src["document_kind"] in {"REGULATION", "TEXTBOOK", "ARCHIVE_BUNDLE", "PRIVATE_SAMPLE"} and not src["commit_prohibited"]:
            _fail("MANIFEST_BINARY_SOURCE_MUST_FORBID_COMMIT")
        if src["usage_status"] not in _ALLOWED_USAGE_STATUSES:
            _fail("MANIFEST_SOURCE_USAGE_STATUS_INVALID")
        _require_non_empty_str(src["notes"], "MANIFEST_SOURCE_NOTES_INVALID")

    digest = _require_sha256(data["manifest_sha256"], "MANIFEST_HASH_INVALID")
    body = {k: v for k, v in data.items() if k != "manifest_sha256"}
    if canonical_json_sha256(body) != digest:
        _fail("MANIFEST_HASH_MISMATCH")
    return deepcopy(data)


def _validate_term(raw_term: object, sources_by_id: Mapping[str, Mapping[str, Any]]) -> str:
    term = _require_mapping(raw_term, "TERM_SCHEMA_INVALID")
    if set(term) != _TERM_FIELDS:
        _fail("TERM_SCHEMA_INVALID")
    tid = _require_id(term["term_id"], "TERM_ID_INVALID")
    _require_non_empty_str(term["canonical_name_vi"], "TERM_NAME_INVALID")
    _require_non_empty_str(term["canonical_name_en"], "TERM_NAME_INVALID")
    _require_str_list(term["aliases"], "TERM_ALIASES_INVALID", min_items=1)
    _require_non_empty_str(term["category"], "TERM_CATEGORY_INVALID")
    sid = _require_id(term["source_id"], "TERM_SOURCE_ID_INVALID")
    src_entry = sources_by_id.get(sid)
    if src_entry is None:
        _fail("TERM_UNKNOWN_SOURCE_ID")
    _require_non_empty_str(term["source_version"], "TERM_SOURCE_VERSION_INVALID")
    _require_non_empty_str(term["clause"], "TERM_CLAUSE_INVALID")
    _require_pos_int_list(term["pdf_page"], "TERM_PDF_PAGE_INVALID", min_items=1)
    _require_pos_int_list(term["reg_page"], "TERM_REG_PAGE_INVALID", min_items=0)
    disp = term["excerpt_disposition"]
    if disp not in _ALLOWED_EXCERPT_DISPOSITIONS:
        _fail("TERM_EXCERPT_DISPOSITION_INVALID")
    _require_non_empty_str(term["technical_summary"], "TERM_SUMMARY_INVALID")
    excerpt = term["verbatim_excerpt"]
    if src_entry.get("usage_rights") == "PRIVATE_LOCAL_NO_COMMIT":
        if disp != "PRIVATE_SOURCE_SUMMARY_ONLY" or excerpt is not None:
            _fail("TERM_PRIVATE_VERBATIM_EXCERPT_FORBIDDEN")
    elif disp == "PRIVATE_SOURCE_SUMMARY_ONLY":
        if excerpt is not None:
            _fail("TERM_EXCERPT_INVALID")
    else:
        _require_non_empty_str(excerpt, "TERM_EXCERPT_INVALID")
    _require_str_list(term["applicable_drawing_types"], "TERM_DRAWING_TYPES_INVALID", min_items=1)
    if term["approval_status"] not in _ALLOWED_DRAFT_STATUSES:
        _fail("TERM_UNAPPROVED_ESCALATION_FORBIDDEN")
    return tid


def _validate_rule(raw_rule: object, sources_by_id: Mapping[str, Mapping[str, Any]]) -> str:
    rule = _require_mapping(raw_rule, "RULE_SCHEMA_INVALID")
    if set(rule) != _RULE_FIELDS:
        _fail("RULE_SCHEMA_INVALID")
    rid = _require_id(rule["rule_id"], "RULE_ID_INVALID")
    _require_non_empty_str(rule["title"], "RULE_TITLE_INVALID")
    sid = _require_id(rule["source_id"], "RULE_SOURCE_ID_INVALID")
    src_entry = sources_by_id.get(sid)
    if src_entry is None:
        _fail("RULE_UNKNOWN_SOURCE_ID")
    _require_non_empty_str(rule["source_version"], "RULE_SOURCE_VERSION_INVALID")
    _require_non_empty_str(rule["clause"], "RULE_CLAUSE_INVALID")
    _require_pos_int_list(rule["pdf_page"], "RULE_PDF_PAGE_INVALID", min_items=1)
    _require_pos_int_list(rule["reg_page"], "RULE_REG_PAGE_INVALID", min_items=0)
    _require_str_list(rule["applicable_domains"], "RULE_DOMAINS_INVALID", min_items=1)
    _require_str_list(rule["applicable_drawing_types"], "RULE_DRAWING_TYPES_INVALID", min_items=1)
    _require_str_list(rule["conditions"], "RULE_CONDITIONS_INVALID", min_items=1)
    _require_str_list(rule["exceptions"], "RULE_EXCEPTIONS_INVALID", min_items=0)
    disp = rule["excerpt_disposition"]
    if disp not in _ALLOWED_EXCERPT_DISPOSITIONS:
        _fail("RULE_EXCERPT_DISPOSITION_INVALID")
    _require_non_empty_str(rule["technical_summary"], "RULE_SUMMARY_INVALID")
    excerpt = rule["verbatim_excerpt"]
    if src_entry.get("usage_rights") == "PRIVATE_LOCAL_NO_COMMIT":
        if disp != "PRIVATE_SOURCE_SUMMARY_ONLY" or excerpt is not None:
            _fail("RULE_PRIVATE_VERBATIM_EXCERPT_FORBIDDEN")
    elif disp == "PRIVATE_SOURCE_SUMMARY_ONLY":
        if excerpt is not None:
            _fail("RULE_EXCERPT_INVALID")
    else:
        _require_non_empty_str(excerpt, "RULE_EXCERPT_INVALID")
    _require_non_empty_str(rule["verification_method"], "RULE_VERIFICATION_METHOD_INVALID")
    if rule["confidence_default"] not in _ALLOWED_CONFIDENCES:
        _fail("RULE_CONFIDENCE_INVALID")
    _require_non_empty_str(rule["limitation"], "RULE_LIMITATION_INVALID")
    if rule["approval_status"] not in _ALLOWED_DRAFT_STATUSES:
        _fail("RULE_UNAPPROVED_ESCALATION_FORBIDDEN")
    return rid


def seal_knowledge_pack(
    raw_pack: Mapping[str, object],
    *,
    source_manifest: Mapping[str, object],
) -> dict[str, Any]:
    """Attach canonical ``pack_sha256`` and validate the full knowledge pack."""
    manifest = validate_source_manifest(source_manifest)
    payload = deepcopy(dict(raw_pack))
    payload["source_manifest_sha256"] = manifest["manifest_sha256"]
    payload.pop("pack_sha256", None)
    payload["pack_sha256"] = canonical_json_sha256(payload)
    return validate_knowledge_pack(payload, source_manifest=manifest)


def validate_knowledge_pack(
    payload: object,
    *,
    source_manifest: Mapping[str, object],
) -> dict[str, Any]:
    """Validate ``marine-knowledge-pack-1.0`` against its source manifest."""
    manifest = validate_source_manifest(source_manifest)
    sources_by_id = {
        src["source_id"]: src
        for src in manifest["sources"]
        if src["usage_status"] != "EXCLUDED_NON_MARINE"
    }
    data = _require_mapping(payload, "PACK_SCHEMA_INVALID")
    if set(data) != _PACK_FIELDS:
        _fail("PACK_SCHEMA_INVALID")
    if data["schema_version"] != MARINE_PACK_SCHEMA_VERSION:
        _fail("PACK_SCHEMA_INVALID")
    _require_id(data["id"], "PACK_ID_INVALID")
    _require_non_empty_str(data["revision"], "PACK_REVISION_INVALID")
    if data["status"] not in _ALLOWED_DRAFT_STATUSES:
        _fail("PACK_UNAPPROVED_STATUS_FORBIDDEN")
    if data["cad_mutation"] is not False or data["default_core_behavior_changed"] is not False:
        _fail("PACK_MUTATION_FORBIDDEN")

    compat = _require_mapping(data["domain_pack_compatibility"], "PACK_COMPAT_INVALID")
    if set(compat) != {"target_schema", "promotable", "requires_human_approval", "approved_by"}:
        _fail("PACK_COMPAT_INVALID")
    if (
        compat["target_schema"] != "domain-pack-1.0"
        or type(compat["promotable"]) is not bool
        or compat["requires_human_approval"] is not True
        or compat["approved_by"] is not None
    ):
        _fail("PACK_COMPAT_INVALID")

    _require_str_list(data["domains"], "PACK_DOMAINS_INVALID", min_items=1)
    _require_str_list(data["drawing_types"], "PACK_DRAWING_TYPES_INVALID", min_items=1)
    _require_str_list(data["vocabulary"], "PACK_VOCAB_INVALID", min_items=1)

    if data["source_manifest_sha256"] != manifest["manifest_sha256"]:
        _fail("PACK_SOURCE_MANIFEST_HASH_MISMATCH")

    terms = data["terms"]
    if not isinstance(terms, list) or len(terms) < 20:
        _fail("PACK_TERMS_BELOW_MINIMUM")
    seen_terms: set[str] = set()
    for term in terms:
        tid = _validate_term(term, sources_by_id)
        if tid in seen_terms:
            _fail("PACK_DUPLICATE_TERM_ID")
        seen_terms.add(tid)

    rules = data["rules"]
    if not isinstance(rules, list) or len(rules) < 8:
        _fail("PACK_RULES_BELOW_MINIMUM")
    seen_rules: set[str] = set()
    for rule in rules:
        rid = _validate_rule(rule, sources_by_id)
        if rid in seen_rules:
            _fail("PACK_DUPLICATE_RULE_ID")
        seen_rules.add(rid)

    digest = _require_sha256(data["pack_sha256"], "PACK_HASH_INVALID")
    body = {k: v for k, v in data.items() if k != "pack_sha256"}
    if canonical_json_sha256(body) != digest:
        _fail("PACK_HASH_MISMATCH")
    return deepcopy(data)


def validate_check_result(payload: object) -> dict[str, Any]:
    """Validate ``marine-check-result-1.0`` fail-closed without mutation or class proof."""
    data = _require_mapping(payload, "RESULT_SCHEMA_INVALID")
    if set(data) != _CHECK_RESULT_FIELDS:
        _fail("RESULT_SCHEMA_INVALID")
    if data["schema_version"] != MARINE_CHECK_RESULT_SCHEMA_VERSION:
        _fail("RESULT_SCHEMA_INVALID")
    _require_id(data["skill_id"], "RESULT_SKILL_ID_INVALID")
    _require_non_empty_str(data["pack_id"], "RESULT_PACK_ID_INVALID")
    if data["status"] not in _ALLOWED_RESULT_STATUSES:
        _fail("RESULT_STATUS_INVALID")
    if data["status"] == "DISABLED":
        if data["pack_sha256"] is not None:
            _require_sha256(data["pack_sha256"], "RESULT_PACK_SHA_INVALID")
    else:
        _require_sha256(data["pack_sha256"], "RESULT_PACK_SHA_INVALID")
    if data["pack_status"] not in _ALLOWED_RESULT_PACK_STATUSES:
        _fail("RESULT_PACK_STATUS_INVALID")
    if data["cad_mutation"] is not False:
        _fail("RESULT_CAD_MUTATION_FORBIDDEN")
    if data["regulatory_compliance_proven"] is not False:
        _fail("RESULT_REGULATORY_PROOF_FORBIDDEN")
    _require_non_empty_str(data["summary"], "RESULT_SUMMARY_INVALID")
    _require_mapping(data["observed_scope"], "RESULT_OBSERVED_SCOPE_INVALID")
    _require_mapping(data["applicable_regulation_scope"], "RESULT_REG_SCOPE_INVALID")
    if type(data["partial_package"]) is not bool:
        _fail("RESULT_PARTIAL_PACKAGE_INVALID")

    findings = data["findings"]
    if not isinstance(findings, list):
        _fail("RESULT_FINDINGS_INVALID")
    for raw_f in findings:
        f = _require_mapping(raw_f, "FINDING_SCHEMA_INVALID")
        if set(f) != _FINDING_FIELDS:
            _fail("FINDING_SCHEMA_INVALID")
        _require_non_empty_str(f["finding_id"], "FINDING_ID_INVALID")
        if f["verdict"] not in _ALLOWED_VERDICTS:
            _fail("FINDING_VERDICT_INVALID")
        _require_non_empty_str(f["rule_id"], "FINDING_RULE_ID_INVALID")
        _require_non_empty_str(f["source_id"], "FINDING_SOURCE_ID_INVALID")
        _require_sha256(f["source_sha256"], "FINDING_SOURCE_SHA_INVALID")
        _require_non_empty_str(f["source_version"], "FINDING_SOURCE_VERSION_INVALID")
        _require_non_empty_str(f["clause"], "FINDING_CLAUSE_INVALID")
        pdf_pages = _require_pos_int_list(f["pdf_page"], "FINDING_PDF_PAGE_INVALID")
        reg_pages = _require_pos_int_list(f["reg_page"], "FINDING_REG_PAGE_INVALID")
        if not pdf_pages and not reg_pages:
            _fail("FINDING_PAGE_CITATION_MISSING")
        _require_non_empty_str(f["pagination_basis"], "FINDING_PAGINATION_BASIS_INVALID")
        _require_str_list(f["conditions_applied"], "FINDING_CONDITIONS_INVALID")
        _require_str_list(f["exceptions_checked"], "FINDING_EXCEPTIONS_INVALID")
        _require_mapping(f["evidence"], "FINDING_EVIDENCE_INVALID")
        _require_non_empty_str(f["reason"], "FINDING_REASON_INVALID")
        if f["confidence"] not in _ALLOWED_CONFIDENCES:
            _fail("FINDING_CONFIDENCE_INVALID")
        _require_non_empty_str(f["limitation"], "FINDING_LIMITATION_INVALID")

    _require_str_list(data["checks_executed"], "RESULT_CHECKS_EXECUTED_INVALID")
    _require_str_list(data["checks_not_executed"], "RESULT_CHECKS_NOT_EXECUTED_INVALID")
    _require_str_list(data["limitations"], "RESULT_LIMITATIONS_INVALID")
    proposals = data["proposal_only_actions"]
    if not isinstance(proposals, list):
        _fail("RESULT_PROPOSALS_INVALID")
    for raw_prop in proposals:
        prop = _require_mapping(raw_prop, "PROPOSAL_SCHEMA_INVALID")
        if set(prop) != _PROPOSAL_FIELDS:
            _fail("PROPOSAL_SCHEMA_INVALID")
        _require_non_empty_str(prop["proposal_id"], "PROPOSAL_ID_INVALID")
        target = _require_non_empty_str(prop["target_drawing_id"], "PROPOSAL_TARGET_INVALID")
        if _SAFE_DRAWING_ID_RE.fullmatch(target) is None:
            _fail("PROPOSAL_TARGET_INVALID")
        action = _require_non_empty_str(prop["action_kind"], "PROPOSAL_ACTION_INVALID")
        if action not in _ALLOWED_PROPOSAL_ACTIONS:
            _fail("PROPOSAL_ACTION_INVALID")
        if prop["cad_mutation"] is not False:
            _fail("PROPOSAL_MUTATION_FORBIDDEN")
        if prop["proposal_only"] is not True or prop["requires_cad_core_admission"] is not True:
            _fail("PROPOSAL_ADMISSION_REQUIRED")
        gates = _require_str_list(prop["required_core_gates"], "PROPOSAL_GATES_INVALID", min_items=2)
        if "CAD_CORE_SOURCE_SUPPORT" not in gates or "CAD_CORE_REVIEW" not in gates:
            _fail("PROPOSAL_GATES_INVALID")
        prop_ev = _require_mapping(prop["evidence"], "PROPOSAL_EVIDENCE_INVALID")
        if prop_ev.get("cad_mutation") is True or prop_ev.get("proposal_only") is False:
            _fail("PROPOSAL_EVIDENCE_INVALID")
        _require_non_empty_str(prop["reason"], "PROPOSAL_REASON_INVALID")
    return deepcopy(data)


SUPPORTED_REGULATIONS = frozenset({"QCVN_72_2025_BGTVT"})


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip().casefold()


_PDF_OUTLINE_CACHE: dict[str, tuple[tuple[int, int, str], ...]] = {}

_PREPOSITION_REF_RE = re.compile(
    r"(?:\b(?:tại|theo|trong|xem|ở|đến|từ|nêu\s+ở|nêu\s+tại|quy\s+định\s+ở|quy\s+định\s+tại|mục|clause|clauses|section)\s+)$",
    re.IGNORECASE,
)


def _walk_pdf_outline(
    reader: PdfReader,
    items: Any,
    acc: list[tuple[int, int, str]],
    level: int = 1,
) -> None:
    for item in items:
        if isinstance(item, list):
            _walk_pdf_outline(reader, item, acc, level=level + 1)
        else:
            try:
                pno = int(reader.get_destination_page_number(item)) + 1
                title = re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(getattr(item, "title", "") or ""))).strip()
                if title:
                    acc.append((pno, level, title))
            except Exception:
                continue


def _get_pdf_outline_entries(reader: PdfReader, source_sha256: str) -> tuple[tuple[int, int, str], ...]:
    cached = _PDF_OUTLINE_CACHE.get(source_sha256)
    if cached is not None:
        return cached
    acc: list[tuple[int, int, str]] = []
    try:
        outline = reader.outline
    except Exception:
        outline = []
    if outline:
        _walk_pdf_outline(reader, outline, acc, level=1)
    frozen = tuple(acc)
    if len(_PDF_OUTLINE_CACHE) >= 8:
        _PDF_OUTLINE_CACHE.clear()
    _PDF_OUTLINE_CACHE[source_sha256] = frozen
    return frozen


def _normalize_preserve_lines(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        cleaned = re.sub(r"\s+", " ", unicodedata.normalize("NFC", raw_line)).strip().casefold()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


def _extract_clause_anchors(
    clause: str,
    *,
    document_kind: str,
) -> tuple[list[tuple[str, str | None]], list[str], list[str]]:
    head = clause.split(";", 1)[0] if document_kind == "TEXTBOOK" else clause
    head_no_parens = re.sub(r"\([^)]*\)", " ", head)

    clause_items: list[tuple[str, str | None]] = []
    seen_items: set[tuple[str, str | None]] = set()

    def _add_item(base: str, sub: str | None) -> None:
        key = (base, sub)
        if key not in seen_items:
            seen_items.add(key)
            clause_items.append(key)

    # Expand explicit sub-item ranges like "2.4.3-1 đến 2.4.3-3"
    for rm in re.finditer(
        r"\b(\d+\.\d+(?:\.\d+)?)-(\d+)\s*(?:đến|to|[-–—])\s*(?:\1-)?(\d+)\b",
        head_no_parens,
        re.IGNORECASE,
    ):
        base, lo_s, hi_s = rm.group(1), rm.group(2), rm.group(3)
        lo_i, hi_i = int(lo_s), int(hi_s)
        if 0 < lo_i <= hi_i and (hi_i - lo_i) <= 20:
            for k in range(lo_i, hi_i + 1):
                _add_item(base, str(k))

    # Expand explicit dotted clause ranges like "3.7.2–3.7.3" or "2.2.1–2.2.2"
    for rm in re.finditer(
        r"\b(\d+\.\d+\.)(\d+)\s*(?:đến|to|[-–—])\s*(?:\1)(\d+)\b",
        head_no_parens,
        re.IGNORECASE,
    ):
        prefix, lo_s, hi_s = rm.group(1), rm.group(2), rm.group(3)
        lo_i, hi_i = int(lo_s), int(hi_s)
        if 0 <= lo_i <= hi_i and (hi_i - lo_i) <= 20:
            for k in range(lo_i, hi_i + 1):
                _add_item(f"{prefix}{k}", None)

    for m in re.finditer(r"\b(\d+\.\d+(?:\.\d+)?)(?:-(\d+))?\b", head_no_parens):
        _add_item(m.group(1), m.group(2))

    chapters = list(
        dict.fromkeys(
            m.group(1)
            for m in re.finditer(r"(?:\bchương|\bch\.)\s*(\d+)\b", head_no_parens, re.IGNORECASE)
        )
    )

    text_anchors: list[str] = []
    if document_kind == "TEXTBOOK":
        for seg in re.split(r"\s*(?:-|&|:|/|,|\+|–|—)\s*", head_no_parens):
            norm_seg = _normalize_ws(seg)
            if not norm_seg or len(norm_seg) < 6:
                continue
            if re.fullmatch(r"(?:chương|ch\.|pdf)?\s*(?:p\.?)?\d+(?:\s*p\.?\d+)?", norm_seg):
                continue
            if norm_seg not in text_anchors:
                text_anchors.append(norm_seg)

    return clause_items, chapters, text_anchors


def _clause_depth(clause_num: str) -> int:
    return len(clause_num.split("."))


def _strip_outline_prefix(title_norm: str) -> str:
    return re.sub(r"^\d+(?:\.\d+)*\s+", "", title_norm).strip()


def _find_heading_offset_in_lines(text_lines: str, heading_body: str, *, min_pos: int = 0) -> int | None:
    if not heading_body:
        return None
    for probe_len in (len(heading_body), 55, 40, 28, 18):
        probe = heading_body[:probe_len].strip()
        if len(probe) < 6:
            continue
        idx = text_lines.find(probe, min_pos)
        if idx != -1:
            return idx
        # Also allow space/newline differences across wrapped PDF lines by regex \s+
        parts = probe.split()
        if len(parts) >= 2:
            pat = r"\s+".join(re.escape(tok) for tok in parts[: min(len(parts), 7)])
            m = re.search(pat, text_lines[min_pos:])
            if m:
                return min_pos + m.start()
    return None


def _has_same_page_following_outline(
    outline_norm: list[tuple[int, int, str]],
    cited_set: set[int],
    *,
    after_page: int,
    exclude_title_prefix: str = "",
) -> bool:
    for o_pno, _o_lvl, o_title in outline_norm:
        if o_pno in cited_set and o_pno >= after_page:
            if exclude_title_prefix and o_title.startswith(exclude_title_prefix):
                continue
            return True
    return False


def _outline_has_next_page_exit(
    outline_norm: list[tuple[int, int, str]],
    cited_set: set[int],
    max_cited: int,
    *,
    clause_num: str | None = None,
) -> bool:
    for oi, (o_pno, o_lvl, o_title) in enumerate(outline_norm):
        if o_pno not in cited_set:
            continue
        if clause_num is not None and not re.match(rf"^{re.escape(clause_num)}(?=\s|$)", o_title):
            continue
        for nj in range(oi + 1, len(outline_norm)):
            n_pno, n_lvl, _ = outline_norm[nj]
            if n_lvl <= o_lvl:
                return n_pno > max_cited
        return False
    return False


def _resolve_regulation_clause_slices(
    *,
    clause_items: list[tuple[str, str | None]],
    ch_anchors: list[str],
    pdf_pages: list[int],
    extracted_pages_lines: list[str],
    outline_entries: tuple[tuple[int, int, str], ...],
) -> tuple[list[str], list[int], bool, str]:
    merged_lines = "\n".join(extracted_pages_lines)
    page_offsets: dict[int, tuple[int, int]] = {}
    cursor = 0
    for idx_p, pno in enumerate(pdf_pages):
        plen = len(extracted_pages_lines[idx_p])
        page_offsets[pno] = (cursor, cursor + plen)
        cursor += plen + 1

    cited_set = set(pdf_pages)
    min_cited = min(pdf_pages)
    max_cited = max(pdf_pages)
    outline_norm = [(pno, lvl, _normalize_ws(title)) for pno, lvl, title in outline_entries]

    slices: list[str] = []
    slice_starts: list[int] = []
    all_bounded = True
    modes: list[str] = []
    if clause_items:
        for base_clause, sub_item in clause_items:
            base_depth = _clause_depth(base_clause)
            matched_slice: str | None = None
            matched_start: int | None = None
            item_bounded = False
            item_mode = "UNRESOLVED"

            # 1. Try body line-start clause heading match first
            body_start: int | None = None
            for bm in re.finditer(
                rf"(?m)(?:^|\n)\s*{re.escape(base_clause)}(?=\s|$)",
                merged_lines,
            ):
                candidate = bm.start()
                if merged_lines[candidate : candidate + 1] == "\n":
                    candidate += 1
                prefix_ctx = merged_lines[max(0, candidate - 40) : candidate].replace("\n", " ")
                if _PREPOSITION_REF_RE.search(prefix_ctx):
                    continue
                body_start = candidate
                break

            if body_start is not None:
                body_end = len(merged_lines)
                closing_found = False
                for nm in re.finditer(r"(?m)(?:^|\n)\s*(\d+\.\d+(?:\.\d+)?)(?=\s|$)", merged_lines[body_start + len(base_clause) :]):
                    cand_num = nm.group(1)
                    rel_pos = body_start + len(base_clause) + nm.start()
                    if merged_lines[rel_pos : rel_pos + 1] == "\n":
                        rel_pos += 1
                    prefix_ctx = merged_lines[max(0, rel_pos - 40) : rel_pos].replace("\n", " ")
                    if _PREPOSITION_REF_RE.search(prefix_ctx):
                        continue
                    if cand_num != base_clause and _clause_depth(cand_num) <= base_depth:
                        body_end = rel_pos
                        closing_found = True
                        break
                matched_slice = merged_lines[body_start:body_end]
                matched_start = body_start
                toc_next_page = _outline_has_next_page_exit(
                    outline_norm,
                    cited_set,
                    max_cited,
                    clause_num=base_clause,
                )
                item_bounded = closing_found or toc_next_page
                item_mode = "BODY_BOUNDED" if item_bounded else "BODY_UNBOUNDED_END"

            # 2. Try outline-numbered clause match (Pass A exact cited page first, then Pass B continuation)
            if matched_slice is None and outline_norm:
                match_idx: int | None = None
                pass_kind = ""
                next_same_or_higher_pno = max_cited + 1
                # Pass A: outline entry lands on an explicitly cited page
                for oi, (o_pno, _o_lvl, o_title) in enumerate(outline_norm):
                    if o_pno in cited_set and re.match(rf"^{re.escape(base_clause)}(?=\s|$)", o_title):
                        next_p = max_cited + 1
                        has_next_same = False
                        for nj in range(oi + 1, len(outline_norm)):
                            n_pno, n_lvl, _n_title = outline_norm[nj]
                            if n_lvl <= _o_lvl:
                                next_p = n_pno
                                has_next_same = True
                                break
                        match_idx = oi
                        next_same_or_higher_pno = next_p if has_next_same else -1
                        pass_kind = "PASS_A"
                        break
                # Pass B: continuation into sub-item from immediately preceding heading
                if match_idx is None and sub_item is not None:
                    for oi, (o_pno, _o_lvl, o_title) in enumerate(outline_norm):
                        if re.match(rf"^{re.escape(base_clause)}(?=\s|$)", o_title):
                            next_p = -1
                            for nj in range(oi + 1, len(outline_norm)):
                                n_pno, n_lvl, _n_title = outline_norm[nj]
                                if n_lvl <= _o_lvl:
                                    next_p = n_pno
                                    break
                            if o_pno < min_cited <= (next_p if next_p != -1 else max_cited + 1):
                                match_idx = oi
                                next_same_or_higher_pno = next_p
                                pass_kind = "PASS_B"
                                break

                if match_idx is not None:
                    o_pno, o_lvl, o_title = outline_norm[match_idx]
                    heading_body = _strip_outline_prefix(o_title)
                    found_s: int | None = None
                    if o_pno in cited_set:
                        p_start = page_offsets[o_pno][0]
                        found_s = _find_heading_offset_in_lines(merged_lines, heading_body, min_pos=p_start)
                        o_start = found_s if found_s is not None else p_start
                    else:
                        o_start = 0

                    o_end = len(merged_lines)
                    closing_bounded = False
                    found_closing_outline = False
                    for nj in range(match_idx + 1, len(outline_norm)):
                        n_pno, n_lvl, n_title = outline_norm[nj]
                        if n_lvl > o_lvl:
                            continue
                        found_closing_outline = True
                        if n_pno in cited_set:
                            n_body = _strip_outline_prefix(n_title)
                            n_min = max(o_start + 5, page_offsets[n_pno][0])
                            found_e = _find_heading_offset_in_lines(merged_lines, n_body, min_pos=n_min)
                            if found_e is None:
                                m_num = re.match(r"^(\d+\.\d+(?:\.\d+)?)\b", n_title)
                                if m_num:
                                    bm_e = re.search(
                                        rf"(?m)(?:^|\n)\s*{re.escape(m_num.group(1))}(?=\s|$)",
                                        merged_lines[n_min:],
                                    )
                                    if bm_e:
                                        found_e = n_min + bm_e.start()
                            if found_e is not None and found_e > o_start:
                                o_end = found_e
                                closing_bounded = True
                                break
                            closing_bounded = False
                            break
                        if n_pno > max_cited:
                            closing_bounded = True
                            break
                    if not found_closing_outline and sub_item is None:
                        closing_bounded = False
                    matched_slice = merged_lines[o_start:o_end]
                    matched_start = o_start
                    if pass_kind == "PASS_A":
                        item_bounded = (found_s is not None) and closing_bounded
                        item_mode = "OUTLINE_PASS_A_BOUNDED" if item_bounded else "OUTLINE_PASS_A_UNBOUNDED"
                    else:
                        # Pass B continuation is provisionally bounded by next outline page if sub_item resolves cleanly below
                        item_bounded = closing_bounded or (next_same_or_higher_pno > max_cited)
                        item_mode = "OUTLINE_PASS_B_SUBITEM"

            # 3. Last-resort direct clause match inside body text (requires closing bound)
            if matched_slice is None:
                direct_start: int | None = None
                for dm in re.finditer(rf"(?<!\d\.){re.escape(base_clause)}(?![.\d-])", merged_lines):
                    cand = dm.start()
                    prefix_ctx = merged_lines[max(0, cand - 40) : cand].replace("\n", " ")
                    if not _PREPOSITION_REF_RE.search(prefix_ctx):
                        direct_start = cand
                        break
                if direct_start is not None:
                    direct_end = len(merged_lines)
                    closing_direct = False
                    for nm in re.finditer(r"(?<!\d\.)(\d+\.\d+(?:\.\d+)?)(?![.\d-])", merged_lines[direct_start + len(base_clause) :]):
                        cand_num = nm.group(1)
                        rel_pos = direct_start + len(base_clause) + nm.start()
                        prefix_ctx = merged_lines[max(0, rel_pos - 40) : rel_pos].replace("\n", " ")
                        if _PREPOSITION_REF_RE.search(prefix_ctx):
                            continue
                        if cand_num != base_clause and _clause_depth(cand_num) <= base_depth:
                            direct_end = rel_pos
                            closing_direct = True
                            break
                    matched_slice = merged_lines[direct_start:direct_end]
                    matched_start = direct_start
                    item_bounded = closing_direct
                    item_mode = "INLINE_BOUNDED" if item_bounded else "INLINE_UNBOUNDED"

            if matched_slice is None:
                _fail("CITATION_CLAUSE_PAGE_MISMATCH")

            if sub_item is not None:
                sub_k = int(sub_item)
                sm = re.search(rf"(?m)(?:^|\n)\s*{sub_k}(?:\s+[^\d,.]|$)", matched_slice)
                if sm is None:
                    sm = re.search(rf"(?:^|\s){sub_k}\s+[^\d,.]", matched_slice)
                if sm is None:
                    _fail("CITATION_CLAUSE_PAGE_MISMATCH")
                s_start = sm.start()
                next_k = sub_k + 1
                s_end = len(matched_slice)
                em = re.search(rf"(?m)(?:^|\n)\s*{next_k}(?:\s+[^\d,.]|$)", matched_slice[s_start + 2 :])
                if em is not None:
                    s_end = s_start + 2 + em.start()
                    if item_mode == "OUTLINE_PASS_B_SUBITEM":
                        item_bounded = True
                matched_slice = matched_slice[s_start:s_end]
                if matched_start is not None:
                    matched_start += s_start
            elif item_mode == "OUTLINE_PASS_B_SUBITEM":
                item_bounded = False

            all_bounded = all_bounded and item_bounded
            modes.append(item_mode)
            slices.append(re.sub(r"\s+", " ", matched_slice).strip())
            if matched_start is None:
                _fail("CITATION_CLAUSE_PAGE_MISMATCH")
            slice_starts.append(matched_start)
        return slices, slice_starts, bool(slices) and all_bounded, ",".join(modes)

    if ch_anchors:
        merged_flat = re.sub(r"\s+", " ", merged_lines).strip()
        for ch in ch_anchors:
            m_ch = re.search(rf"\bchương\s*{re.escape(ch)}\b", merged_flat)
            if m_ch is None:
                _fail("CITATION_CLAUSE_PAGE_MISMATCH")
            slices.append(merged_flat[m_ch.start() :])
            slice_starts.append(m_ch.start())
        return slices, slice_starts, False, "CHAPTER_ONLY_UNBOUNDED"

    _fail("CITATION_CLAUSE_PAGE_MISMATCH")
    return [], [], False, "UNRESOLVED"


_TB_BOUNDARY_RE = re.compile(
    r"(?im)(?:^|\n)[ \t]*(?:(?:(?P<prefix>section|sec\.?|§)[ \t]*)?(?P<number>\d+\.\d+(?:\.\d+)?)|"
    r"(?:chương|phần|mục)\s+[0-9ivxlcdm]+\b)"
)
_TB_MEASUREMENT_UNIT_TOKEN_RE = re.compile(
    r"^(?:%|m/s|m/sec|km/h|km/hr|ft/s|ft/min|m/min|mm|cm|km|m|ft|inch|inches|"
    r"kg|g|t|t/m(?:\^?3|³)|kg/m(?:\^?3|³)|m(?:\^?2|²)|ton|tons|hp|kw|kn|kn/m(?:\^?2|²)?|"
    r"kn[-·]m|n[-·]m|n/mm(?:\^?2|²)?|mpa|knot|knots|deg|degree|degrees|psi|kpa|bar|rpm|in|c)\.?$",
    re.IGNORECASE,
)


def _is_textbook_clause_heading_suffix(suffix: str, *, explicit_section: bool = False) -> bool:
    """Distinguish a numbered heading from a measurement beginning with the same digits."""
    # Heading grammar is local to one extracted physical line. Whitespace
    # normalization across a newline can otherwise treat the next paragraph as
    # the heading's suffix and lose a valid standalone section boundary.
    physical_line_suffix = re.split(r"\r?\n", suffix, maxsplit=1)[0]
    tail = physical_line_suffix.lstrip(" \t")
    if not tail:
        return True
    # "In service" is a common heading title and the token "in" is also an
    # imperial unit. Preserve this recognized multiword title, including when
    # a section marker or dash precedes it.
    heading_tail = re.sub(r"^[-–—][ \t]*", "", tail)
    if re.match(r"(?i)^in\s+(?:service|operation)\b", heading_tail):
        return True
    if tail.startswith(":"):
        content = tail[1:].lstrip()
        return not content or (not content[0].isdigit() and not content.startswith("%"))
    if tail[0] in ".)":
        return len(tail) == 1 or tail[1].isspace()
    if tail[0] in "-–—":
        content = tail[1:].lstrip(" \t")
        token = content.split(maxsplit=1)[0].strip(".,;:()[]{}") if content else ""
        return not content or (
            not content[0].isdigit()
            and not content.startswith("%")
            and not _TB_MEASUREMENT_UNIT_TOKEN_RE.fullmatch(token)
        )
    if physical_line_suffix[:1] in {" ", "\t"}:
        token = tail.split(maxsplit=1)[0].strip(".,;:()[]{}")
        return bool(token) and not _TB_MEASUREMENT_UNIT_TOKEN_RE.fullmatch(token) and token[0].isalpha()
    return False


def _is_textbook_clause_heading_line(line: str, clause_num: str) -> bool:
    match = re.match(
        rf"^\s*(?:(?P<prefix>section|sec\.?|§)\s*)?{re.escape(clause_num)}",
        line,
        re.IGNORECASE,
    )
    return match is not None and _is_textbook_clause_heading_suffix(
        line[match.end() :], explicit_section=bool(match.group("prefix"))
    )


def _find_textbook_next_boundary(
    merged_lines: str,
    *,
    start_after: int,
    outline_norm: list[tuple[int, int, str]],
    resolver_pdf_pages: Sequence[int],
    extracted_pages_lines: Sequence[str],
    clause_num: str | None = None,
) -> tuple[int, bool]:
    """Find the earliest visible or outline-backed textbook section boundary."""
    candidates: list[int] = []
    clause_depth = _clause_depth(clause_num) if clause_num else None
    for m_num in _TB_BOUNDARY_RE.finditer(merged_lines, start_after):
        boundary_num = m_num.group("number")
        if boundary_num and clause_depth is not None and _clause_depth(boundary_num) > clause_depth:
            continue
        if boundary_num and not _is_textbook_clause_heading_suffix(
            merged_lines[m_num.end("number") :], explicit_section=bool(m_num.group("prefix"))
        ):
            continue
        pos = m_num.start()
        if merged_lines[pos : pos + 1] == "\n":
            pos += 1
        candidates.append(pos)
        break

    page_offsets: dict[int, tuple[int, int]] = {}
    cursor = 0
    for page_no, page_text in zip(resolver_pdf_pages, extracted_pages_lines):
        page_offsets[page_no] = (cursor, cursor + len(page_text))
        cursor += len(page_text) + 1

    start_page = next(
        (page_no for page_no, (page_start, page_end) in page_offsets.items() if page_start <= start_after <= page_end),
        None,
    )
    if start_page is not None and outline_norm:
        active_index: int | None = None
        if clause_num:
            matches = [
                index for index, (page_no, _level, title) in enumerate(outline_norm)
                if page_no <= start_page and _is_textbook_clause_heading_line(title, clause_num)
            ]
            if matches:
                active_index = matches[-1]
        if active_index is None:
            earlier = [index for index, (page_no, _level, _title) in enumerate(outline_norm) if page_no <= start_page]
            if earlier:
                active_index = earlier[-1]

        if active_index is not None:
            _active_page, active_level, _active_title = outline_norm[active_index]
            last_resolver_page = max(page_offsets, default=0)
            for page_no, level, title in outline_norm[active_index + 1 :]:
                if level > active_level:
                    continue
                page_span = page_offsets.get(page_no)
                if page_span is None:
                    if page_no > last_resolver_page:
                        candidates.append(len(merged_lines))
                        break
                    return len(merged_lines), False
                page_start, page_end = page_span
                if page_end <= start_after:
                    continue
                local_start_after = max(0, start_after - page_start)
                local_heading = _find_heading_offset_in_lines(
                    merged_lines[page_start:page_end], title, min_pos=local_start_after
                )
                if local_heading is not None:
                    outline_pos = page_start + local_heading
                    if outline_pos > start_after:
                        candidates.append(outline_pos)
                elif page_start > start_after:
                    # An outline page is an authoritative boundary even when its title
                    # cannot be matched in extracted text. Bound before that page.
                    candidates.append(page_start)
                else:
                    # The outline establishes a same-page boundary whose exact text
                    # location is unavailable; abstain from content verification.
                    return len(merged_lines), False
                break

    return (min(candidates), True) if candidates else (len(merged_lines), False)


def _resolve_textbook_clause_slices(
    *,
    clause_items: list[tuple[str, str | None]],
    ch_anchors: list[str],
    text_anchors: list[str],
    extracted_pages_lines: list[str],
    pdf_pages: list[int] | None = None,
    outline_entries: tuple[tuple[int, int, str], ...] = (),
) -> tuple[list[str], bool, str]:
    merged_lines = "\n".join(extracted_pages_lines)
    merged_flat = re.sub(r"\s+", " ", merged_lines).strip()
    outline_norm = [(pno, lvl, _normalize_ws(title)) for pno, lvl, title in outline_entries]
    cited_set = set(pdf_pages or [])
    resolver_pdf_pages: Sequence[int] = (
        range(min(cited_set), max(cited_set) + 1) if len(cited_set) > 1 else tuple(cited_set)
    )

    slices: list[str] = []
    all_bounded = True
    modes: list[str] = []

    if clause_items:
        for base_clause, _sub in clause_items:
            pattern = re.compile(
                rf"(?im)(?:^|\n)[ \t]*(?:(?P<prefix>section|sec\.?|§)[ \t]*)?"
                rf"(?P<number>{re.escape(base_clause)})"
            )
            m = next(
                (
                    candidate
                    for candidate in pattern.finditer(merged_lines)
                    if _is_textbook_clause_heading_suffix(
                        merged_lines[candidate.end("number") :],
                        explicit_section=bool(candidate.group("prefix")),
                    )
                ),
                None,
            )
            if m is None:
                _fail("CITATION_CLAUSE_PAGE_MISMATCH")
            start_pos = m.start() + (1 if merged_lines[m.start() : m.start() + 1] == "\n" else 0)

            end_pos, found_end = _find_textbook_next_boundary(
                merged_lines,
                start_after=m.end("number"),
                outline_norm=outline_norm,
                resolver_pdf_pages=resolver_pdf_pages,
                extracted_pages_lines=extracted_pages_lines,
                clause_num=base_clause,
            )
            slices.append(re.sub(r"\s+", " ", merged_lines[start_pos:end_pos]).strip())
            all_bounded = all_bounded and found_end
            modes.append("TB_CLAUSE_BOUNDED" if found_end else "TB_CLAUSE_UNBOUNDED")
        return slices, bool(slices) and all_bounded, ",".join(modes)

    anchor_positions: list[int] = []
    for heading in text_anchors:
        pos = _find_heading_offset_in_lines(merged_lines, heading, min_pos=0)
        if pos is not None:
            anchor_positions.append(pos)
    if ch_anchors and not anchor_positions:
        for ch in ch_anchors:
            m_ch = re.search(rf"\bchương\s*{re.escape(ch)}\b", merged_lines)
            if m_ch is not None:
                anchor_positions.append(m_ch.start())

    if not anchor_positions:
        # Fallback check against flat text in case PDF wraps line breaks across heading
        for heading in text_anchors:
            pos_f = merged_flat.find(heading)
            if pos_f != -1:
                return [merged_flat[pos_f:]], False, "TB_TEXT_UNBOUNDED"
        _fail("CITATION_CLAUSE_PAGE_MISMATCH")

    for pos in sorted(set(anchor_positions)):
        end_pos, found_end = _find_textbook_next_boundary(
            merged_lines,
            start_after=pos + 6,
            outline_norm=outline_norm,
            resolver_pdf_pages=resolver_pdf_pages,
            extracted_pages_lines=extracted_pages_lines,
        )
        slices.append(re.sub(r"\s+", " ", merged_lines[pos:end_pos]).strip())
        all_bounded = all_bounded and found_end
        modes.append("TB_TEXT_BOUNDED" if found_end else "TB_TEXT_UNBOUNDED")
    return slices, bool(slices) and all_bounded, ",".join(modes)


def verify_source_citation(
    citation: Mapping[str, object],
    manifest: Mapping[str, object],
    *,
    expected_sha256: str | None = None,
    source_file_path: str | Path | None = None,
    source_bytes: bytes | None = None,
    page_texts: Mapping[int, str] | Sequence[str] | None = None,
    allow_local_private_verbatim: bool = False,
) -> dict[str, Any]:
    """Fail-closed citation verification binding bytes, page, clause, and excerpt strictly to SHA-256."""
    valid_manifest = validate_source_manifest(manifest)
    sources = {src["source_id"]: src for src in valid_manifest["sources"]}
    record = _require_mapping(citation, "CITATION_INVALID")
    source_id = _require_non_empty_str(record.get("source_id"), "CITATION_SOURCE_MISSING")
    source_entry = sources.get(source_id)
    if source_entry is None or source_entry["usage_status"] == "EXCLUDED_NON_MARINE":
        _fail("CITATION_SOURCE_UNSUPPORTED")

    clause = _require_non_empty_str(record.get("clause"), "CITATION_CLAUSE_MISSING").strip()
    if source_id == "QCVN_72_2025_BGTVT" and re.match(
        r"^(?:qcvn\s*(?!72)\d+|solas|tcvn)\b", clause, re.IGNORECASE
    ):
        _fail("CITATION_CLAUSE_SOURCE_MISMATCH")

    disp = record.get("excerpt_disposition")
    if disp is not None and disp not in _ALLOWED_EXCERPT_DISPOSITIONS:
        _fail("CITATION_EXCERPT_DISPOSITION_INVALID")
    is_summary_only = disp == "PRIVATE_SOURCE_SUMMARY_ONLY"
    if not allow_local_private_verbatim:
        if source_entry.get("usage_rights") == "PRIVATE_LOCAL_NO_COMMIT" and record.get("verbatim_excerpt") is not None:
            _fail("CITATION_PRIVATE_VERBATIM_FORBIDDEN")
        if is_summary_only and record.get("verbatim_excerpt") is not None:
            _fail("CITATION_PRIVATE_VERBATIM_FORBIDDEN")

    if "source_version" in record and record["source_version"] is not None:
        cited_ver = _require_non_empty_str(record["source_version"], "CITATION_VERSION_MISMATCH")
        manifest_ver = str(source_entry["version"])
        ver_year = re.search(r"\b(19\d{2}|20\d{2})\b", cited_ver)
        man_year = re.search(r"\b(19\d{2}|20\d{2})\b", manifest_ver)
        if ver_year and man_year and ver_year.group(1) != man_year.group(1):
            _fail("CITATION_VERSION_MISMATCH")
        if cited_ver not in manifest_ver and not (
            ver_year and man_year and ver_year.group(1) == man_year.group(1)
        ):
            _fail("CITATION_VERSION_MISMATCH")

    pdf_pages = _require_pos_int_list(record.get("pdf_page", []), "CITATION_PDF_PAGE_INVALID")
    reg_pages = _require_pos_int_list(record.get("reg_page", []), "CITATION_REG_PAGE_INVALID")
    if not pdf_pages and not reg_pages:
        _fail("CITATION_PAGE_MISSING")
    if len(pdf_pages) > 1 and pdf_pages != sorted(set(pdf_pages)):
        _fail("CITATION_PDF_PAGE_ORDER_INVALID")

    page_count = source_entry.get("page_count")
    if isinstance(page_count, int) and any(p > page_count for p in pdf_pages):
        _fail("CITATION_PDF_PAGE_OUT_OF_RANGE")

    if source_entry["document_kind"] == "TEXTBOOK" and reg_pages:
        _fail("CITATION_REG_PAGE_MISMATCH")
    if source_entry["document_kind"] == "REGULATION":
        if not reg_pages or (pdf_pages and len(reg_pages) != len(pdf_pages)):
            _fail("CITATION_PAGINATION_OFFSET_MISMATCH")
        if source_id == "QCVN_72_2025_BGTVT" and source_entry["sha256"] == _QCVN72_CONSOLIDATED_SHA256:
            for pdf_p, reg_p in zip(pdf_pages, reg_pages):
                if reg_p != pdf_p + 16:
                    _fail("CITATION_PAGINATION_OFFSET_MISMATCH")

    cited_sha = _require_sha256(record.get("source_sha256"), "CITATION_SHA_MISSING")
    if cited_sha != source_entry["sha256"]:
        _fail("CITATION_SHA_STALE_OR_MISMATCH")
    if expected_sha256 is not None and _require_sha256(expected_sha256, "CITATION_EXPECTED_SHA_INVALID") != cited_sha:
        _fail("CITATION_SHA_STALE_OR_MISMATCH")

    states: list[str] = ["MANIFEST_MATCH"]
    clause_span_status = "NOT_EVALUATED"
    clause_match_mode = "NOT_EVALUATED"
    raw_bytes: bytes | None = source_bytes
    if raw_bytes is None and source_file_path is not None:
        fpath = Path(source_file_path)
        if fpath.is_file():
            raw_bytes = fpath.read_bytes()

    if raw_bytes is None:
        states.extend(["METADATA_ONLY", "SOURCE_UNAVAILABLE"])
        if page_texts is not None:
            # Caller-supplied page_texts without SHA-256 source bytes are never trusted or promoted.
            states.append("UNVERIFIED_CALLER_PAGE_TEXTS")
    else:
        actual_sha = hashlib.sha256(raw_bytes).hexdigest()
        if actual_sha != source_entry["sha256"]:
            _fail("CITATION_SHA_STALE_OR_MISMATCH")
        states.append("SOURCE_BYTES_VERIFIED")

        if raw_bytes.lstrip().startswith(b"%PDF") and pdf_pages:
            reader = PdfReader(BytesIO(raw_bytes))
            total_pdf_pages = len(reader.pages)
            if any(page > total_pdf_pages for page in pdf_pages):
                _fail("CITATION_PDF_PAGE_OUT_OF_RANGE")
            outline_entries = _get_pdf_outline_entries(reader, actual_sha)
            doc_kind = str(source_entry["document_kind"])
            resolver_pdf_pages: Sequence[int] = pdf_pages
            if len(pdf_pages) > 1:
                # Keep omitted pages in clause-boundary context for every document
                # kind, so a non-contiguous citation cannot erase an intervening
                # section heading or continuation. Excerpt matching below remains
                # limited to explicitly cited pages.
                resolver_pdf_pages = range(pdf_pages[0], pdf_pages[-1] + 1)
            extracted_pages_lines: list[str] = []
            reg_pages_by_pdf = dict(zip(pdf_pages, reg_pages))
            for pdf_p in resolver_pdf_pages:
                if pdf_p < 1 or pdf_p > total_pdf_pages:
                    _fail("CITATION_PDF_PAGE_OUT_OF_RANGE")
                page_txt = reader.pages[pdf_p - 1].extract_text() or ""
                extracted_pages_lines.append(_normalize_preserve_lines(page_txt))
                if pdf_p in reg_pages_by_pdf:
                    if str(reg_pages_by_pdf[pdf_p]) not in page_txt[:300]:
                        _fail("CITATION_PAGE_MISMATCH")

            clause_items, ch_anchors, text_anchors = _extract_clause_anchors(
                clause,
                document_kind=doc_kind,
            )
            resolved_clause_starts: list[int] = []
            if doc_kind == "TEXTBOOK":
                bound_slices, span_bounded, clause_match_mode = _resolve_textbook_clause_slices(
                    clause_items=clause_items,
                    ch_anchors=ch_anchors,
                    text_anchors=text_anchors,
                    extracted_pages_lines=extracted_pages_lines,
                    pdf_pages=pdf_pages,
                    outline_entries=outline_entries,
                )
            else:
                bound_slices, resolved_clause_starts, span_bounded, clause_match_mode = _resolve_regulation_clause_slices(
                    clause_items=clause_items,
                    ch_anchors=ch_anchors,
                    pdf_pages=resolver_pdf_pages,
                    extracted_pages_lines=extracted_pages_lines,
                    outline_entries=outline_entries,
                )

            raw_source = "\n".join(extracted_pages_lines)
            normalized_source = _normalize_ws(raw_source)
            clause_source_spans: list[tuple[int, int]] = []
            if doc_kind == "REGULATION":
                if any(later < earlier for earlier, later in zip(resolved_clause_starts, resolved_clause_starts[1:])):
                    _fail("CITATION_CLAUSE_DOCUMENT_ORDER_MISMATCH")
                for bound_slice, source_start in zip(bound_slices, resolved_clause_starts):
                    normalized_slice = _normalize_ws(bound_slice)
                    normalized_start = len(_normalize_ws(raw_source[:source_start]))
                    source_position = normalized_source.find(normalized_slice, normalized_start)
                    if not normalized_slice or source_position < 0:
                        _fail("CITATION_CLAUSE_DOCUMENT_ORDER_MISMATCH")
                    clause_source_spans.append((source_position, source_position + len(normalized_slice)))
            else:
                source_cursor = 0
                for bound_slice in bound_slices:
                    normalized_slice = _normalize_ws(bound_slice)
                    source_position = normalized_source.find(normalized_slice, source_cursor)
                    if not normalized_slice or source_position < 0:
                        _fail("CITATION_CLAUSE_DOCUMENT_ORDER_MISMATCH")
                    clause_source_spans.append((source_position, source_position + len(normalized_slice)))
                    source_cursor = source_position + len(normalized_slice)

            clause_span_status = "CLAUSE_SPAN_BOUNDED" if span_bounded else "CLAUSE_BOUNDARY_UNBOUNDED"
            states.append("PAGE_VERIFIED")

            excerpt = record.get("verbatim_excerpt")
            if isinstance(excerpt, str) and excerpt.strip() and not is_summary_only:
                segments = [
                    _normalize_ws(seg)
                    for seg in excerpt.split("...")
                    if _normalize_ws(seg)
                ]
                cited_page_spans: list[tuple[int, int]] = []
                normalized_page_cursor = 0
                for pdf_p, page_text in zip(resolver_pdf_pages, extracted_pages_lines):
                    normalized_page = _normalize_ws(page_text)
                    if not normalized_page:
                        continue
                    page_start = normalized_source.find(normalized_page, normalized_page_cursor)
                    if page_start < 0:
                        _fail("CITATION_PAGE_MISMATCH")
                    page_end = page_start + len(normalized_page)
                    if pdf_p in pdf_pages:
                        cited_page_spans.append((page_start, page_end))
                    normalized_page_cursor = page_end

                allowed_spans = sorted(
                    (max(clause_start, page_start), min(clause_end, page_end))
                    for clause_start, clause_end in clause_source_spans
                    for page_start, page_end in cited_page_spans
                    if max(clause_start, page_start) < min(clause_end, page_end)
                )
                merged_allowed_spans: list[tuple[int, int]] = []
                for start, end in allowed_spans:
                    if merged_allowed_spans and start <= merged_allowed_spans[-1][1] + 1:
                        merged_allowed_spans[-1] = (
                            merged_allowed_spans[-1][0], max(merged_allowed_spans[-1][1], end)
                        )
                    else:
                        merged_allowed_spans.append((start, end))
                cursor = 0
                ordered_match = bool(segments and merged_allowed_spans)
                for segment in segments:
                    position = -1
                    for span_start, span_end in merged_allowed_spans:
                        search_start = max(span_start, cursor)
                        if search_start >= span_end:
                            continue
                        candidate = normalized_source.find(segment, search_start, span_end)
                        if candidate >= 0 and candidate + len(segment) <= span_end:
                            position = candidate
                            break
                    if position < 0:
                        ordered_match = False
                        break
                    cursor = position + len(segment)
                if not ordered_match:
                    _fail("CITATION_EXCERPT_CONTENT_MISMATCH")
                if span_bounded:
                    states.append("CLAUSE_CONTENT_VERIFIED")

    if "CLAUSE_CONTENT_VERIFIED" in states and "PAGE_VERIFIED" in states and "SOURCE_BYTES_VERIFIED" in states:
        verification_level = "SOURCE_CONTENT_VERIFIED"
    elif "PAGE_VERIFIED" in states and "SOURCE_BYTES_VERIFIED" in states:
        verification_level = "SOURCE_PAGE_VERIFIED"
    elif "SOURCE_BYTES_VERIFIED" in states:
        verification_level = "SOURCE_BYTES_VERIFIED"
    else:
        verification_level = "MANIFEST_METADATA_ONLY"

    out = deepcopy(dict(record))
    out["verification_states"] = states
    out["verification_level"] = verification_level
    out["clause_span_status"] = clause_span_status
    out["clause_match_mode"] = clause_match_mode
    return out
