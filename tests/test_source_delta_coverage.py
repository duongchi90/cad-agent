"""Coverage must reject incomplete source obligations, not roundtrip success.

Own synthetic #488 fixture: shortened composite, glyph-only revision and
adjacent KEEP. Evidence verdicts are supplied by the independent fixture oracle;
the composition must never infer engineering truth from its hashes.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from itertools import product

import ezdxf
from PIL import Image, ImageDraw
import pytest

from cad_agent import source_fusion_proposal as owner
from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.source_bundle import build_source_bundle

COMPLETE = "SOURCE_DELTA_COVERAGE_COMPLETE"
UNRESOLVED = "SOURCE_DELTA_COVERAGE_UNRESOLVED"


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _context(tmp_path, *, geometry_new=True, text_new=True, keep_same=True):
    source = Image.new("L", (240, 160), 255)
    draw = ImageDraw.Draw(source)
    draw.rectangle((20, 20, 80, 100), outline=0)
    for y in (40, 60, 80):
        draw.line((20, y, 80, y), fill=0)
    draw.rectangle((150, 20, 180, 50), outline=0)
    # REV-B as source-visible strokes, no embedded text or text extraction.
    glyphs = [
        [[(0, 12), (0, 0), (7, 0), (8, 1), (8, 5), (7, 6), (0, 6)], [(4, 6), (8, 12)]],
        [[(8, 0), (0, 0), (0, 12), (8, 12)], [(0, 6), (7, 6)]],
        [[(0, 0), (4, 12), (8, 0)]],
        [[(1, 6), (7, 6)]],
        [[(0, 12), (0, 0), (7, 0), (8, 1), (8, 5), (7, 6), (0, 6),
          (7, 6), (8, 7), (8, 11), (7, 12), (0, 12)]],
    ]
    for index, character in enumerate(glyphs):
        for stroke in character:
            draw.line([(20 + 11 * index + x, 125 + y) for x, y in stroke], fill=0)
    source_path = tmp_path / "source.png"
    source.save(source_path)
    source_sha = _sha(source_path.read_bytes())

    def component(right):
        return [((20, 20), (right, 20)), ((right, 20), (right, 100)),
                ((right, 100), (20, 100)), ((20, 100), (20, 20)),
                *[((20, y), (right, y)) for y in (40, 60, 80)]]

    keep = [((150, 20), (180, 20)), ((180, 20), (180, 50)),
            ((180, 50), (150, 50)), ((150, 50), (150, 20))]
    base = ezdxf.new("R2018")
    block = base.blocks.new("SYNTHETIC_COMPOSITE")
    for start, end in component(100):
        block.add_line(start, end)
    base.modelspace().add_blockref(block.name, (0, 0))
    for start, end in keep:
        base.modelspace().add_line(start, end)
    base.modelspace().add_text("REV-A", dxfattribs={"height": 10, "insert": (20, 125)})
    base_path = tmp_path / "base.dxf"
    base.saveas(base_path)
    base_sha = _sha(base_path.read_bytes())
    candidate = ezdxf.readfile(base_path)
    candidate_block = candidate.blocks.get(block.name)
    for entity in list(candidate_block):
        candidate_block.delete_entity(entity)
    for start, end in component(80 if geometry_new else 100):
        candidate_block.add_line(start, end)
    if not keep_same:
        for entity in candidate.modelspace().query("LINE"):
            entity.translate(5, 0, 0)
    next(iter(candidate.modelspace().query("TEXT"))).dxf.text = "REV-B" if text_new else "REV-A"
    candidate_path = tmp_path / "candidate.dxf"
    candidate.saveas(candidate_path)
    persisted = ezdxf.readfile(candidate_path)
    actual_component = [(tuple(e.dxf.start)[:2], tuple(e.dxf.end)[:2])
                        for e in persisted.blocks.get(block.name).query("LINE")]
    actual_keep = [(tuple(e.dxf.start)[:2], tuple(e.dxf.end)[:2])
                   for e in persisted.modelspace().query("LINE")]
    actual_revision = next(iter(persisted.modelspace().query("TEXT"))).dxf.text
    verdicts = {"composite": actual_component == component(80),
                "revision": actual_revision == "REV-B", "keep": actual_keep == keep}
    assert _sha(base_path.read_bytes()) == base_sha
    with Image.open(source_path) as opened:
        assert not opened.info

    bundle = build_source_bundle(
        bundle_id="fixture-bundle", run_id="fixture-run", created_at_utc="2026-10-07T00:00:00Z",
        items=[{"source_id": "modified", "kind": "IMAGE", "role": "OVERALL",
                "relative_path": "source.png", "sha256": source_sha, "media_type": "image/png",
                "page_ids": [], "region_ids": ["composite", "keep", "revision"],
                "captured_at_utc": None, "quality": {"distortion": "NONE", "legibility": "GOOD"}}],
    )
    regions = []
    for region_id, aspect, roi in [("composite", "geometry", [20, 20, 100, 100]),
                                   ("keep", "protection", [145, 15, 185, 55]),
                                   ("revision", "text", [20, 125, 74, 139])]:
        regions.append({"source_id": "modified", "region_id": region_id,
                        "source_binding": {"source_sha256": source_sha, "page_index": 0,
                                           "source_render_sha256": source_sha, "roi_bbox_px": roi},
                        "aspects": [aspect]})
    scope = {"source_bundle_sha256": canonical_json_sha256(bundle),
             "regions": regions, "exclusions": []}
    # Thin projections of caller-owned current candidate facts, not fake R4/live attestation.
    current = {"candidate_revision_sha256": canonical_json_sha256({"artifact": _sha(candidate_path.read_bytes())}),
               "candidate_state_sha256": canonical_json_sha256({"selected": _sha(candidate_path.read_bytes())}),
               "latest_mutation_sha256": canonical_json_sha256({"base": base_sha, "candidate": _sha(candidate_path.read_bytes())})}
    obligations = []
    for region in regions:
        source_evidence_sha = _sha(source.crop(region["source_binding"]["roi_bbox_px"]).tobytes())
        evidence = {"source_id": region["source_id"], "region_id": region["region_id"],
                    "aspect": region["aspects"][0], "source_binding": deepcopy(region["source_binding"]),
                    "source_evidence_sha256": source_evidence_sha, "candidate_binding": deepcopy(current),
                    "evidence_kind": "PROTECTED_STATE" if region["region_id"] == "keep" else "APPLIED_CHANGE",
                    "status": "VERIFIED" if verdicts[region["region_id"]] else "UNRESOLVED"}
        evidence["evidence_sha256"] = canonical_json_sha256(evidence)
        obligations.append({"source_id": region["source_id"], "region_id": region["region_id"],
                            "aspect": region["aspects"][0], "source_binding": deepcopy(region["source_binding"]),
                            "source_evidence_sha256": source_evidence_sha,
                            "disposition": "KEEP" if region["region_id"] == "keep" else "CHANGE",
                            "scope_status": "IN_SCOPE", "candidate_evidence": evidence})
    return {"source_bundle": bundle, "declared_scope": scope,
            "admitted_scope_sha256": canonical_json_sha256(scope),
            "current_candidate": current, "obligations": obligations}


def _compose(context):
    function = getattr(owner, "compose_source_delta_coverage", None)
    assert callable(function), "SOURCE_DELTA_COVERAGE_V1 capability is missing"
    return function(**context)


@pytest.mark.parametrize("geometry_new,text_new,keep_same", list(product([False, True], repeat=3)))
def test_488_matrix_only_complete_native_source_evidence_covers_scope(
    tmp_path, geometry_new, text_new, keep_same
):
    context = _context(tmp_path, geometry_new=geometry_new, text_new=text_new, keep_same=keep_same)
    result = _compose(context)
    assert result["status"] == (COMPLETE if geometry_new and text_new and keep_same else UNRESOLVED)
    assert len(result["covered"]) == sum((geometry_new, text_new, keep_same))
    assert len(result["unresolved"]) == 3 - sum((geometry_new, text_new, keep_same))
    assert "PRODUCT_PASS" not in result and "product_pass" not in result


def test_missing_declared_aspect_stays_unresolved_even_with_other_coverage(tmp_path):
    context = _context(tmp_path)
    context["obligations"].pop()
    result = _compose(context)
    assert result["status"] == UNRESOLVED
    assert any(item["region_id"] == "revision" for item in result["unresolved"])


@pytest.mark.parametrize("conflicting", [False, True])
def test_duplicate_obligation_never_silently_collapses_to_covered(tmp_path, conflicting):
    context = _context(tmp_path)
    duplicate = deepcopy(context["obligations"][0])
    if conflicting:
        duplicate["disposition"] = "KEEP"
    context["obligations"].append(duplicate)
    assert _compose(context)["status"] == UNRESOLVED


@pytest.mark.parametrize("disposition", ["AMBIGUOUS", "INSUFFICIENT_SOURCE_EVIDENCE"])
def test_inside_scope_unknown_source_never_becomes_keep(tmp_path, disposition):
    context = _context(tmp_path)
    context["obligations"][0].update(disposition=disposition, candidate_evidence=None)
    result = _compose(context)
    assert result["status"] == UNRESOLVED
    assert not any(item["region_id"] == "composite" for item in result["covered"])


def _exclude_composite(context):
    context["declared_scope"]["exclusions"] = [{"source_id": "modified", "region_id": "composite",
                                               "aspect": "geometry", "reason": "Unproven manufacturing scope excluded before mutation",
                                               "evidence_sha256": _sha(b"own scope exclusion decision")}]
    context["obligations"][0].update(disposition="AMBIGUOUS", scope_status="EXCLUDED", candidate_evidence=None)


def test_before_mutation_excluded_ambiguity_reports_truthfully_narrowed_claim(tmp_path):
    context = _context(tmp_path)
    _exclude_composite(context)
    context["admitted_scope_sha256"] = canonical_json_sha256(context["declared_scope"])
    result = _compose(context)
    assert result["status"] == COMPLETE
    assert [item["region_id"] for item in result["claim_scope"]] == ["keep", "revision"]
    assert len(result["excluded"]) == 1
    assert result["excluded"][0]["disposition"] == "AMBIGUOUS"


def test_late_exclusion_cannot_rewrite_admitted_scope(tmp_path):
    context = _context(tmp_path)
    _exclude_composite(context)
    assert _compose(context)["status"] == UNRESOLVED


@pytest.mark.parametrize("field", ["candidate_revision_sha256", "candidate_state_sha256", "latest_mutation_sha256"])
def test_bound_proof_from_other_candidate_epoch_stays_unresolved(tmp_path, field):
    context = _context(tmp_path)
    evidence = context["obligations"][0]["candidate_evidence"]
    evidence["candidate_binding"][field] = _sha(b"different candidate epoch")
    _seal_evidence(evidence)
    assert _compose(context)["status"] == UNRESOLVED


def _seal_evidence(evidence):
    evidence.pop("evidence_sha256", None)
    evidence["evidence_sha256"] = canonical_json_sha256(evidence)


@pytest.mark.parametrize("field", ["source_sha256", "source_render_sha256", "page_index", "roi_bbox_px"])
def test_stale_source_page_render_or_roi_never_covers_declared_region(tmp_path, field):
    context = _context(tmp_path)
    binding = context["obligations"][0]["source_binding"]
    binding[field] = 1 if field == "page_index" else [21, 20, 100, 100] if field == "roi_bbox_px" else _sha(b"other source")
    assert _compose(context)["status"] == UNRESOLVED


@pytest.mark.parametrize("target", ["source_evidence_sha256", "region_id", "aspect"])
def test_candidate_proof_cannot_be_reused_for_different_source_obligation(tmp_path, target):
    context = _context(tmp_path)
    proof = context["obligations"][0]["candidate_evidence"]
    proof[target] = _sha(b"other fact") if target.endswith("sha256") else "other"
    _seal_evidence(proof)
    assert _compose(context)["status"] == UNRESOLVED


def test_mutated_proof_status_with_old_checksum_cannot_turn_failure_green(tmp_path):
    context = _context(tmp_path, geometry_new=False)
    context["obligations"][0]["candidate_evidence"]["status"] = "VERIFIED"
    assert _compose(context)["status"] == UNRESOLVED


@pytest.mark.parametrize("region_index", [0, 1])
def test_missing_change_or_protected_candidate_proof_is_unresolved(tmp_path, region_index):
    context = _context(tmp_path)
    context["obligations"][region_index]["candidate_evidence"] = None
    assert _compose(context)["status"] == UNRESOLVED


def test_roundtrip_pass_is_not_source_change_or_protected_state_evidence(tmp_path):
    context = _context(tmp_path)
    proof = context["obligations"][0]["candidate_evidence"]
    proof["evidence_kind"] = "ROUNDTRIP"
    _seal_evidence(proof)
    assert _compose(context)["status"] == UNRESOLVED


def test_no_distinct_delta_needs_bound_protection_evidence(tmp_path):
    context = _context(tmp_path)
    context["obligations"][1]["disposition"] = "NO_DISTINCT_DELTA"
    assert _compose(context)["status"] == COMPLETE
    context["obligations"][1]["candidate_evidence"] = None
    assert _compose(context)["status"] == UNRESOLVED


def test_planned_change_is_only_coverage_evidence_not_execution_authority(tmp_path):
    context = _context(tmp_path)
    proof = context["obligations"][0]["candidate_evidence"]
    proof["evidence_kind"] = "PLANNED_CHANGE"
    _seal_evidence(proof)
    result = _compose(context)
    assert result["status"] == COMPLETE
    assert any(item.get("evidence_kind") == "PLANNED_CHANGE" for item in result["covered"])
    assert "cad_mutation" not in result and "PRODUCT_PASS" not in result


@pytest.mark.parametrize("mutate", [
    lambda c: c["declared_scope"]["regions"].pop(),
    lambda c: c["declared_scope"]["regions"][0]["aspects"].append("another-aspect"),
    lambda c: c["declared_scope"].update(source_bundle_sha256=_sha(b"old bundle")),
    lambda c: c["source_bundle"]["items"][0].update(sha256=_sha(b"new source")),
])
def test_changed_scope_or_source_bundle_is_not_the_admitted_scope(tmp_path, mutate):
    context = _context(tmp_path)
    mutate(context)
    assert _compose(context)["status"] == UNRESOLVED


def test_foreign_unlisted_obligation_is_not_ignored(tmp_path):
    context = _context(tmp_path)
    record = deepcopy(context["obligations"][0])
    record["region_id"] = "unlisted"
    context["obligations"].append(record)
    assert _compose(context)["status"] == UNRESOLVED


def test_empty_scope_is_not_a_silent_complete_success(tmp_path):
    context = _context(tmp_path)
    context["declared_scope"]["regions"] = []
    context["obligations"] = []
    context["admitted_scope_sha256"] = canonical_json_sha256(context["declared_scope"])
    assert _compose(context)["status"] == UNRESOLVED


@pytest.mark.parametrize("field,value", [("obligations", None), ("declared_scope", {}),
                                        ("source_bundle", {}), ("current_candidate", {}),
                                        ("admitted_scope_sha256", True)])
def test_malformed_top_level_inputs_return_unresolved_not_complete(tmp_path, field, value):
    context = _context(tmp_path)
    context[field] = value
    assert _compose(context)["status"] == UNRESOLVED


def test_order_independent_output_and_hash_without_mutating_caller_records(tmp_path):
    context = _context(tmp_path)
    before = deepcopy(context)
    first = _compose(context)
    assert context == before
    reordered = deepcopy(context)
    reordered["obligations"].reverse()
    reordered["declared_scope"]["regions"].reverse()
    second = _compose(reordered)
    assert first == second
    unsigned = {key: value for key, value in first.items() if key != "coverage_sha256"}
    assert first["coverage_sha256"] == canonical_json_sha256(unsigned)


def test_stale_composite_hypothesis_still_rejected_by_existing_source_support(tmp_path):
    _context(tmp_path)
    source = (tmp_path / "source.png").read_bytes()
    binding = {"source_sha256": _sha(source), "page_index": 0,
               "source_render_sha256": _sha(source), "roi_bbox_px": [0, 0, 239, 159]}
    proposal = {"schema_version": "external-visual-object-proposal-1.0",
                "proposal_source": "external_ai", **binding, "view_role_proposal": "FRONT",
                "primitive_hypotheses": [{"id": "top", "type": "LINE", "start_px": [20, 20],
                                          "end_px": [100, 20]}],
                "object_groups": [{"group_id": "composite", "proposed_label": "UNKNOWN_BOUNDARY",
                                   "primitive_hypothesis_ids": ["top"]}], "excluded_memberships": []}
    request = owner.compile_external_visual_object_proposal(proposal=proposal, expected_binding=binding)
    from cad_agent.source_support_verifier import verify_external_visual_proposal_source_support

    with pytest.raises(ValueError, match="PRIMITIVE_SOURCE_SUPPORT_INSUFFICIENT"):
        verify_external_visual_proposal_source_support(verification_request=request,
                                                      source_render_bytes=source)
    proposal["primitive_hypotheses"][0]["end_px"] = [80, 20]
    request = owner.compile_external_visual_object_proposal(proposal=proposal, expected_binding=binding)
    assert verify_external_visual_proposal_source_support(
        verification_request=request, source_render_bytes=source
    )["status"] == "VERIFIED"


def test_all_excluded_regions_do_not_claim_complete_for_empty_scope(tmp_path):
    context = _context(tmp_path)
    for record in context["obligations"]:
        context["declared_scope"]["exclusions"].append({
            "source_id": record["source_id"], "region_id": record["region_id"],
            "aspect": record["aspect"], "reason": "excluded before mutation",
            "evidence_sha256": _sha(record["region_id"].encode()),
        })
        record.update(disposition="AMBIGUOUS", scope_status="EXCLUDED", candidate_evidence=None)
    context["admitted_scope_sha256"] = canonical_json_sha256(context["declared_scope"])
    assert _compose(context)["status"] == UNRESOLVED


def test_duplicate_declared_region_is_not_a_second_independent_obligation(tmp_path):
    context = _context(tmp_path)
    context["declared_scope"]["regions"].append(deepcopy(context["declared_scope"]["regions"][0]))
    context["admitted_scope_sha256"] = canonical_json_sha256(context["declared_scope"])
    assert _compose(context)["status"] == UNRESOLVED


def test_new_declared_aspect_requires_its_own_disposition(tmp_path):
    context = _context(tmp_path)
    context["declared_scope"]["regions"][0]["aspects"].append("second-aspect")
    context["admitted_scope_sha256"] = canonical_json_sha256(context["declared_scope"])
    result = _compose(context)
    assert result["status"] == UNRESOLVED
    assert any(item.get("aspect") == "second-aspect" for item in result["unresolved"])
