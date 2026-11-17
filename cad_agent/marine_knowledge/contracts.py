"""Fail-closed contract validators for Marine Knowledge Pack V0.

Reuses canonical JSON hashing and identifier discipline from
``cad_agent.drawing_contracts`` without adding runtime dependencies or altering
``CAD Core`` approval semantics.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import re
from typing import Any

from cad_agent.drawing_contracts import canonical_json_sha256

SOURCE_MANIFEST_SCHEMA_VERSION = "marine-source-manifest-1.0"
MARINE_PACK_SCHEMA_VERSION = "marine-knowledge-pack-1.0"
MARINE_CHECK_RESULT_SCHEMA_VERSION = "marine-check-result-1.0"

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_ALLOWED_DRAFT_STATUSES = frozenset({"CANDIDATE_UNAPPROVED", "DRAFT_REVIEW_ONLY"})
_ALLOWED_RESULT_PACK_STATUSES = _ALLOWED_DRAFT_STATUSES | frozenset({"DISABLED"})
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


def _validate_term(raw_term: object, known_sources: set[str]) -> str:
    term = _require_mapping(raw_term, "TERM_SCHEMA_INVALID")
    if set(term) != _TERM_FIELDS:
        _fail("TERM_SCHEMA_INVALID")
    tid = _require_id(term["term_id"], "TERM_ID_INVALID")
    _require_non_empty_str(term["canonical_name_vi"], "TERM_NAME_INVALID")
    _require_non_empty_str(term["canonical_name_en"], "TERM_NAME_INVALID")
    _require_str_list(term["aliases"], "TERM_ALIASES_INVALID", min_items=1)
    _require_non_empty_str(term["category"], "TERM_CATEGORY_INVALID")
    sid = _require_id(term["source_id"], "TERM_SOURCE_ID_INVALID")
    if sid not in known_sources:
        _fail("TERM_UNKNOWN_SOURCE_ID")
    _require_non_empty_str(term["source_version"], "TERM_SOURCE_VERSION_INVALID")
    _require_non_empty_str(term["clause"], "TERM_CLAUSE_INVALID")
    _require_pos_int_list(term["pdf_page"], "TERM_PDF_PAGE_INVALID", min_items=1)
    _require_pos_int_list(term["reg_page"], "TERM_REG_PAGE_INVALID", min_items=0)
    _require_non_empty_str(term["verbatim_excerpt"], "TERM_EXCERPT_INVALID")
    _require_str_list(term["applicable_drawing_types"], "TERM_DRAWING_TYPES_INVALID", min_items=1)
    if term["approval_status"] not in _ALLOWED_DRAFT_STATUSES:
        _fail("TERM_UNAPPROVED_ESCALATION_FORBIDDEN")
    return tid


def _validate_rule(raw_rule: object, known_sources: set[str]) -> str:
    rule = _require_mapping(raw_rule, "RULE_SCHEMA_INVALID")
    if set(rule) != _RULE_FIELDS:
        _fail("RULE_SCHEMA_INVALID")
    rid = _require_id(rule["rule_id"], "RULE_ID_INVALID")
    _require_non_empty_str(rule["title"], "RULE_TITLE_INVALID")
    sid = _require_id(rule["source_id"], "RULE_SOURCE_ID_INVALID")
    if sid not in known_sources:
        _fail("RULE_UNKNOWN_SOURCE_ID")
    _require_non_empty_str(rule["source_version"], "RULE_SOURCE_VERSION_INVALID")
    _require_non_empty_str(rule["clause"], "RULE_CLAUSE_INVALID")
    _require_pos_int_list(rule["pdf_page"], "RULE_PDF_PAGE_INVALID", min_items=1)
    _require_pos_int_list(rule["reg_page"], "RULE_REG_PAGE_INVALID", min_items=0)
    _require_str_list(rule["applicable_domains"], "RULE_DOMAINS_INVALID", min_items=1)
    _require_str_list(rule["applicable_drawing_types"], "RULE_DRAWING_TYPES_INVALID", min_items=1)
    _require_str_list(rule["conditions"], "RULE_CONDITIONS_INVALID", min_items=1)
    _require_str_list(rule["exceptions"], "RULE_EXCEPTIONS_INVALID", min_items=0)
    _require_non_empty_str(rule["verbatim_excerpt"], "RULE_EXCERPT_INVALID")
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
    known_sources = {
        src["source_id"]
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
        tid = _validate_term(term, known_sources)
        if tid in seen_terms:
            _fail("PACK_DUPLICATE_TERM_ID")
        seen_terms.add(tid)

    rules = data["rules"]
    if not isinstance(rules, list) or len(rules) < 8:
        _fail("PACK_RULES_BELOW_MINIMUM")
    seen_rules: set[str] = set()
    for rule in rules:
        rid = _validate_rule(rule, known_sources)
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
    if data["pack_sha256"] is not None:
        _require_sha256(data["pack_sha256"], "RESULT_PACK_SHA_INVALID")
    if data["pack_status"] not in _ALLOWED_RESULT_PACK_STATUSES:
        _fail("RESULT_PACK_STATUS_INVALID")
    if data["cad_mutation"] is not False:
        _fail("RESULT_CAD_MUTATION_FORBIDDEN")
    if data["regulatory_compliance_proven"] is not False:
        _fail("RESULT_REGULATORY_PROOF_FORBIDDEN")
    if data["status"] not in _ALLOWED_RESULT_STATUSES:
        _fail("RESULT_STATUS_INVALID")
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
    if not isinstance(proposals, list) or any(not isinstance(item, Mapping) for item in proposals):
        _fail("RESULT_PROPOSALS_INVALID")
    return deepcopy(data)


SUPPORTED_REGULATIONS = frozenset({"QCVN_72_2025_BGTVT"})


def verify_source_citation(
    citation: Mapping[str, object],
    manifest: Mapping[str, object],
    *,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Fail-closed citation verification against SHA-256 manifest, clause, and explicit pagination basis."""
    valid_manifest = validate_source_manifest(manifest)
    sources = {src["source_id"]: src for src in valid_manifest["sources"]}
    record = _require_mapping(citation, "CITATION_INVALID")
    source_id = _require_non_empty_str(record.get("source_id"), "CITATION_SOURCE_MISSING")
    source_entry = sources.get(source_id)
    if source_entry is None or source_entry["usage_status"] == "EXCLUDED_NON_MARINE":
        _fail("CITATION_SOURCE_UNSUPPORTED")
    _require_non_empty_str(record.get("clause"), "CITATION_CLAUSE_MISSING")
    pdf_pages = _require_pos_int_list(record.get("pdf_page", []), "CITATION_PDF_PAGE_INVALID")
    reg_pages = _require_pos_int_list(record.get("reg_page", []), "CITATION_REG_PAGE_INVALID")
    if not pdf_pages and not reg_pages:
        _fail("CITATION_PAGE_MISSING")
    page_count = source_entry.get("page_count")
    if isinstance(page_count, int) and any(p > page_count for p in pdf_pages):
        _fail("CITATION_PDF_PAGE_OUT_OF_RANGE")
    cited_sha = _require_sha256(record.get("source_sha256"), "CITATION_SHA_MISSING")
    if cited_sha != source_entry["sha256"]:
        _fail("CITATION_SHA_STALE_OR_MISMATCH")
    if expected_sha256 is not None and _require_sha256(expected_sha256, "CITATION_EXPECTED_SHA_INVALID") != cited_sha:
        _fail("CITATION_SHA_STALE_OR_MISMATCH")
    return deepcopy(dict(record))
