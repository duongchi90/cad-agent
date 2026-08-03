from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256, read_contract
from cad_agent.cli import main
from cad_agent.drawing_setup import (
    DrawingSetupError,
    create_setup_plan,
    evaluate_setup_plan,
    require_setup_verified,
)
from cad_agent.manifest import sha256_file
from drawing_setup_fixtures import write_approved_setup_inputs


def _approved_mappings(root: Path) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object], Path]:
    inputs = write_approved_setup_inputs(root)
    return (
        read_contract(inputs.definition, contract="drawing_definition"),
        read_contract(inputs.profile, contract="drawing_profile"),
        read_contract(inputs.domain_pack, contract="domain_pack"),
        read_contract(inputs.template_manifest, contract="template_manifest"),
        inputs.template_file,
    )


def _create_plan(
    *,
    run_id: str,
    definition: dict[str, object],
    profile: dict[str, object],
    domain_pack: dict[str, object],
    template_manifest: dict[str, object],
    template_file: Path,
) -> dict[str, object]:
    return create_setup_plan(
        run_id=run_id,
        definition=definition,
        profile=profile,
        domain_pack=domain_pack,
        template_manifest=template_manifest,
        template_file=template_file,
    )


def test_create_setup_plan_has_only_the_approved_keyword_api() -> None:
    signature = inspect.signature(create_setup_plan)
    assert list(signature.parameters) == [
        "run_id",
        "definition",
        "profile",
        "domain_pack",
        "template_manifest",
        "template_file",
    ]
    assert all(parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in signature.parameters.values())


def test_create_setup_plan_binds_shared_fixture_mappings_and_deep_copies_expectations(tmp_path: Path) -> None:
    definition, profile, domain_pack, template_manifest, template_file = _approved_mappings(tmp_path)

    plan = _create_plan(
        run_id="RUN-20260803-001",
        definition=definition,
        profile=profile,
        domain_pack=domain_pack,
        template_manifest=template_manifest,
        template_file=template_file,
    )

    assert plan["schema_version"] == "drawing-setup-plan-1.0"
    assert plan["state"] == "SETUP_PENDING"
    assert plan["definition"] == {
        "id": definition["id"],
        "sha256": canonical_json_sha256(definition),
    }
    assert plan["drawing_profile"]["sha256"] == canonical_json_sha256(profile)
    assert plan["domain_pack"]["sha256"] == canonical_json_sha256(domain_pack)
    assert plan["template"]["embedded_settings_sha256"] == canonical_json_sha256(profile["setup_expectations"])
    json.dumps(plan)
    plan_path = tmp_path / "drawing-setup-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    assert read_contract(plan_path, contract="drawing_setup_plan") == json.loads(plan_path.read_text(encoding="utf-8"))
    profile["setup_expectations"]["current_layer"] = "MUTATED"
    assert plan["setup_expectations"]["current_layer"] == "0"
    with pytest.raises(TypeError, match="immutable"):
        plan["setup_expectations"]["current_layer"] = "MUTATED"


def test_create_setup_plan_rejects_invalid_mapping_input(tmp_path: Path) -> None:
    definition, profile, domain_pack, template_manifest, template_file = _approved_mappings(tmp_path)
    profile["status"] = "DRAFT"

    with pytest.raises(DrawingSetupError, match="APPROVED"):
        _create_plan(
            run_id="RUN-20260803-002",
            definition=definition,
            profile=profile,
            domain_pack=domain_pack,
            template_manifest=template_manifest,
            template_file=template_file,
        )


@pytest.mark.parametrize("input_name", ["definition", "profile", "domain_pack", "template_manifest"])
def test_create_setup_plan_requires_approved_input_statuses(tmp_path: Path, input_name: str) -> None:
    definition, profile, domain_pack, template_manifest, template_file = _approved_mappings(tmp_path)
    inputs: dict[str, dict[str, object]] = {
        "definition": definition,
        "profile": profile,
        "domain_pack": domain_pack,
        "template_manifest": template_manifest,
    }
    inputs[input_name]["status"] = "DRAFT"

    with pytest.raises(DrawingSetupError, match="APPROVED"):
        _create_plan(run_id="RUN-20260803-003", template_file=template_file, **inputs)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda definition, profile, domain_pack: definition.__setitem__("domain", "OTHER"), "domain"),
        (lambda definition, profile, domain_pack: domain_pack.__setitem__("domains", ["OTHER"]), "domain"),
        (lambda definition, profile, domain_pack: definition.__setitem__("drawing_type", "DETAIL"), "drawing type"),
        (lambda definition, profile, domain_pack: profile.__setitem__("supported_drawing_types", ["DETAIL"]), "drawing type"),
    ],
)
def test_create_setup_plan_requires_domain_and_type_compatibility(
    tmp_path: Path, mutation: Any, message: str
) -> None:
    definition, profile, domain_pack, template_manifest, template_file = _approved_mappings(tmp_path)
    mutation(definition, profile, domain_pack)

    with pytest.raises(DrawingSetupError, match=message):
        _create_plan(
            run_id="RUN-20260803-004",
            definition=definition,
            profile=profile,
            domain_pack=domain_pack,
            template_manifest=template_manifest,
            template_file=template_file,
        )


@pytest.mark.parametrize("run_id", ["", "RUN WITH SPACE", 7])
def test_create_setup_plan_rejects_invalid_run_id(tmp_path: Path, run_id: object) -> None:
    definition, profile, domain_pack, template_manifest, template_file = _approved_mappings(tmp_path)

    with pytest.raises(DrawingSetupError, match="run ID"):
        _create_plan(  # type: ignore[arg-type]
            run_id=run_id,
            definition=definition,
            profile=profile,
            domain_pack=domain_pack,
            template_manifest=template_manifest,
            template_file=template_file,
        )


@pytest.mark.parametrize("release_profile", ["DRAFT", "", None, [], {}])
def test_create_setup_plan_requires_an_accepted_release_profile(
    tmp_path: Path, release_profile: object
) -> None:
    definition, profile, domain_pack, template_manifest, template_file = _approved_mappings(tmp_path)
    definition["release_profile"] = release_profile

    with pytest.raises(DrawingSetupError, match="release profile"):
        _create_plan(
            run_id="RUN-20260803-005",
            definition=definition,
            profile=profile,
            domain_pack=domain_pack,
            template_manifest=template_manifest,
            template_file=template_file,
        )


def test_create_setup_plan_rejects_missing_non_regular_and_wrong_extension_template(tmp_path: Path) -> None:
    definition, profile, domain_pack, template_manifest, template_file = _approved_mappings(tmp_path)
    template_file.unlink()
    with pytest.raises(DrawingSetupError, match="regular file"):
        _create_plan(run_id="RUN-20260803-006", definition=definition, profile=profile, domain_pack=domain_pack, template_manifest=template_manifest, template_file=template_file)

    template_file.mkdir()
    with pytest.raises(DrawingSetupError, match="regular file"):
        _create_plan(run_id="RUN-20260803-007", definition=definition, profile=profile, domain_pack=domain_pack, template_manifest=template_manifest, template_file=template_file)

    wrong_extension = tmp_path / "template.dwg"
    wrong_extension.write_bytes(b"synthetic-dwt-fixture")
    with pytest.raises(DrawingSetupError, match=r"\.dwt"):
        _create_plan(run_id="RUN-20260803-008", definition=definition, profile=profile, domain_pack=domain_pack, template_manifest=template_manifest, template_file=wrong_extension)


def test_create_setup_plan_rejects_symlinked_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    definition, profile, domain_pack, template_manifest, template_file = _approved_mappings(tmp_path)
    monkeypatch.setattr(Path, "is_symlink", lambda _: True)

    with pytest.raises(DrawingSetupError, match="regular file"):
        _create_plan(run_id="RUN-20260803-009", definition=definition, profile=profile, domain_pack=domain_pack, template_manifest=template_manifest, template_file=template_file)


@pytest.mark.parametrize("field", ["file_sha256", "drawing_profile_sha256", "embedded_settings_sha256"])
def test_create_setup_plan_requires_matching_manifest_digests(tmp_path: Path, field: str) -> None:
    definition, profile, domain_pack, template_manifest, template_file = _approved_mappings(tmp_path)
    template_manifest[field] = "0" * 64

    with pytest.raises(DrawingSetupError, match="SHA-256"):
        _create_plan(run_id="RUN-20260803-010", definition=definition, profile=profile, domain_pack=domain_pack, template_manifest=template_manifest, template_file=template_file)


def test_create_setup_plan_surfaces_malformed_prevalidated_mapping_values(tmp_path: Path) -> None:
    definition, profile, domain_pack, template_manifest, template_file = _approved_mappings(tmp_path)
    del profile["setup_expectations"]

    with pytest.raises(DrawingSetupError, match="profile"):
        _create_plan(run_id="RUN-20260803-011", definition=definition, profile=profile, domain_pack=domain_pack, template_manifest=template_manifest, template_file=template_file)


def test_drawing_setup_plan_cli_writes_pending_plan(tmp_path: Path) -> None:
    paths = write_approved_setup_inputs(tmp_path)
    output = tmp_path / "drawing-setup-plan.json"

    assert main([
        "drawing-setup-plan",
        "--run-id", "RUN-20260802-001",
        "--definition", str(paths.definition),
        "--profile", str(paths.profile),
        "--domain-pack", str(paths.domain_pack),
        "--template-manifest", str(paths.template_manifest),
        "--template-file", str(paths.template_file),
        "--output", str(output),
    ]) == 0

    assert json.loads(output.read_text(encoding="utf-8"))["state"] == "SETUP_PENDING"


def test_drawing_setup_audit_cli_writes_hash_bound_normalized_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drawing = tmp_path / "setup.dwg"
    drawing.write_bytes(b"synthetic drawing")
    output = tmp_path / "drawing-setup-audit.json"
    calls: list[dict[str, object]] = []

    class FakeSetupClient:
        def __init__(self, **kwargs: object) -> None:
            calls.append({"init": kwargs})

        def drawing_setup_audit(
            self,
            drawing_full_path: str,
            *,
            drawing_sha256: str,
            request_id: str | None = None,
        ) -> dict[str, object]:
            calls.append(
                {
                    "drawing_full_path": drawing_full_path,
                    "drawing_sha256": drawing_sha256,
                    "request_id": request_id,
                }
            )
            return {
                "request_id": "setup-001",
                "success": True,
                "operation": "drawing_setup_audit",
                "drawing_full_path": drawing_full_path,
                "changed": False,
                "entity_handles": [],
                "warnings": [],
                "errors": [],
                "started_at": "2026-08-01T00:00:00Z",
                "completed_at": "2026-08-01T00:00:01Z",
                "payload": {
                    "drawing_full_path": drawing_full_path,
                    "dbmod_before": 0,
                    "dbmod_after": 0,
                    "changed": False,
                    "variables": {
                        "INSUNITS": 4,
                        "MEASUREMENT": 1,
                        "LTSCALE": 100.0,
                        "CELTSCALE": 1.0,
                        "PSLTSCALE": 1,
                        "MSLTSCALE": 1,
                        "DIMASSOC": 2,
                        "ANNOALLVISIBLE": 0,
                    },
                    "current_layer": "0",
                    "custom_properties": {"CAD_AGENT_SETTINGS_SHA256": "b" * 64},
                    "layers": [
                        {
                            "name": "0",
                            "linetype": "Continuous",
                            "plottable": True,
                            "color_index": 7,
                        }
                    ],
                    "styles": {
                        "text": ["VX_TEXT"],
                        "dimension": ["VX_DIM_20"],
                        "mleader": ["VX_MLEADER"],
                        "table": ["VX_TABLE"],
                    },
                    "layouts": [
                        {
                            "name": "A1-01",
                            "viewports": [{"handle": "1A", "custom_scale": 0.05, "locked": True}],
                        }
                    ],
                },
            }

    monkeypatch.setattr(
        "mcp_integration_lib.dotnet_ipc.DotNetIPCClient", FakeSetupClient
    )
    monkeypatch.setattr(
        "mcp_integration_lib.dotnet_ipc.make_windows_dotnet_dispatch_trigger",
        lambda _hwnd: lambda: None,
    )

    assert main([
        "drawing-setup-audit",
        "--drawing", str(drawing),
        "--hwnd", "1234",
        "--ipc-dir", str(tmp_path / "ipc"),
        "--output", str(output),
    ]) == 0

    audit = read_contract(output, contract="drawing_setup_audit")
    assert audit["schema_version"] == "drawing-setup-audit-1.0"
    assert audit["drawing_sha256"] == sha256_file(drawing)
    assert audit["layers"] == [{"name": "0", "linetype": "Continuous", "plottable": True}]
    assert audit["layouts"] == [{"name": "A1-01", "viewport_scales": [0.05], "locked": True}]
    assert calls[1]["drawing_sha256"] == sha256_file(drawing)


def test_drawing_setup_audit_cli_refuses_source_changed_during_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drawing = tmp_path / "setup.dwg"
    drawing.write_bytes(b"before")

    class MutatingSetupClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def drawing_setup_audit(self, drawing_full_path: str, **_kwargs: object) -> dict[str, object]:
            Path(drawing_full_path).write_bytes(b"after")
            return {"success": True}

    monkeypatch.setattr(
        "mcp_integration_lib.dotnet_ipc.DotNetIPCClient", MutatingSetupClient
    )
    monkeypatch.setattr(
        "mcp_integration_lib.dotnet_ipc.make_windows_dotnet_dispatch_trigger",
        lambda _hwnd: lambda: None,
    )

    assert main([
        "drawing-setup-audit",
        "--drawing", str(drawing),
        "--hwnd", "1234",
        "--ipc-dir", str(tmp_path / "ipc"),
        "--output", str(tmp_path / "audit.json"),
    ]) == 2
    assert not (tmp_path / "audit.json").exists()


def test_matching_audit_becomes_setup_verified() -> None:
    from drawing_setup_fixtures import approved_setup_plan, matching_setup_audit

    plan = approved_setup_plan()
    evidence = evaluate_setup_plan(
        plan,
        matching_setup_audit(plan),
        verified_by="ENGINEER",
        approval_reference="M2-LIVE-001",
    )

    assert evidence["status"] == "SETUP_VERIFIED"
    assert evidence["blockers"] == []
    require_setup_verified(
        evidence,
        setup_plan_sha256=canonical_json_sha256(plan),
        drawing_profile_sha256=plan["drawing_profile"]["sha256"],
        template_file_sha256=plan["template"]["file_sha256"],
    )


def test_require_setup_verified_rejects_stale_bound_hash() -> None:
    from drawing_setup_fixtures import approved_setup_plan, matching_setup_audit

    plan = approved_setup_plan()
    evidence = evaluate_setup_plan(
        plan,
        matching_setup_audit(plan),
        verified_by="ENGINEER",
        approval_reference="M2-LIVE-001",
    )
    evidence["setup_plan_sha256"] = "0" * 64

    with pytest.raises(DrawingSetupError, match="setup_plan_sha256"):
        require_setup_verified(
            evidence,
            setup_plan_sha256=canonical_json_sha256(plan),
            drawing_profile_sha256=plan["drawing_profile"]["sha256"],
            template_file_sha256=plan["template"]["file_sha256"],
        )


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (("variables", "INSUNITS", 0), "setup_incomplete"),
        (("styles", "dimstyle", "Standard"), "profile_hash_mismatch"),
        (("viewports", "SIDE", False), "viewport_scale_mismatch"),
        (("custom_properties", "CAD_AGENT_SETTINGS_SHA256", "bad"), "template_hash_mismatch"),
    ],
)
def test_setup_mismatch_returns_needs_review(mutation: tuple[str, str, object], code: str) -> None:
    from drawing_setup_fixtures import apply_test_mutation, approved_setup_plan, matching_setup_audit

    plan = approved_setup_plan()
    audit = matching_setup_audit(plan)
    apply_test_mutation(audit, mutation)

    evidence = evaluate_setup_plan(
        plan,
        audit,
        verified_by="ENGINEER",
        approval_reference="M2-LIVE-001",
    )

    assert evidence["status"] == "NEEDS_REVIEW"
    assert code in {item["code"] for item in evidence["blockers"]}


def test_drawing_setup_verify_cli_writes_verified_evidence(tmp_path: Path) -> None:
    from drawing_setup_fixtures import approved_setup_plan, matching_setup_audit

    plan = approved_setup_plan()
    audit = matching_setup_audit(plan)
    plan_path = tmp_path / "plan.json"
    audit_path = tmp_path / "audit.json"
    output = tmp_path / "evidence.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    audit_path.write_text(json.dumps(audit), encoding="utf-8")

    assert main([
        "drawing-setup-verify",
        "--plan", str(plan_path),
        "--audit", str(audit_path),
        "--verified-by", "ENGINEER",
        "--approval-reference", "M2-LIVE-001",
        "--output", str(output),
    ]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "SETUP_VERIFIED"


def test_drawing_setup_verify_cli_persists_needs_review_evidence(tmp_path: Path) -> None:
    from drawing_setup_fixtures import approved_setup_plan, matching_setup_audit

    plan = approved_setup_plan()
    audit = matching_setup_audit(plan)
    audit["dbmod_after"] = 1
    plan_path = tmp_path / "plan.json"
    audit_path = tmp_path / "audit.json"
    output = tmp_path / "evidence.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    audit_path.write_text(json.dumps(audit), encoding="utf-8")

    assert main([
        "drawing-setup-verify",
        "--plan", str(plan_path),
        "--audit", str(audit_path),
        "--verified-by", "ENGINEER",
        "--approval-reference", "M2-LIVE-001",
        "--output", str(output),
    ]) == 2
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["status"] == "NEEDS_REVIEW"
    assert any(item["code"] == "source_changed" for item in evidence["blockers"])
