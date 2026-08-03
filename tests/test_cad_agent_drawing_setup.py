from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from cad_agent.cli import main
from cad_agent.drawing_contracts import canonical_json_sha256, read_contract
from cad_agent.drawing_setup import DrawingSetupError, create_setup_audit, create_setup_plan
from cad_agent.manifest import sha256_file
from drawing_setup_fixtures import (
    approved_setup_plan,
    matching_setup_ipc_result,
    write_approved_setup_inputs,
)
from mcp_integration_lib.dotnet_ipc import DotNetIPCClient, DotNetIPCResultError


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


def test_drawing_setup_plan_cli_writes_valid_pending_plan(tmp_path: Path) -> None:
    inputs = write_approved_setup_inputs(tmp_path)
    output = tmp_path / "drawing-setup-plan.json"

    assert main([
        "drawing-setup-plan",
        "--run-id", "RUN-20260803-CLI",
        "--definition", str(inputs.definition),
        "--profile", str(inputs.profile),
        "--domain-pack", str(inputs.domain_pack),
        "--template-manifest", str(inputs.template_manifest),
        "--template-file", str(inputs.template_file),
        "--output", str(output),
    ]) == 0

    plan = read_contract(output, contract="drawing_setup_plan")
    assert plan["run_id"] == "RUN-20260803-CLI"
    assert plan["state"] == "SETUP_PENDING"


def test_drawing_setup_plan_cli_refuses_invalid_contract_without_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    inputs = write_approved_setup_inputs(tmp_path)
    profile = json.loads(inputs.profile.read_text(encoding="utf-8"))
    profile["status"] = "DRAFT"
    inputs.profile.write_text(json.dumps(profile), encoding="utf-8")
    output = tmp_path / "drawing-setup-plan.json"

    assert main([
        "drawing-setup-plan",
        "--run-id", "RUN-20260803-INVALID",
        "--definition", str(inputs.definition),
        "--profile", str(inputs.profile),
        "--domain-pack", str(inputs.domain_pack),
        "--template-manifest", str(inputs.template_manifest),
        "--template-file", str(inputs.template_file),
        "--output", str(output),
    ]) == 2

    assert "APPROVED" in capsys.readouterr().err
    assert not output.exists()


def test_create_setup_audit_copies_only_strict_fields_without_mutating_result(
    tmp_path: Path,
) -> None:
    drawing = tmp_path / "setup-lite.dwg"
    drawing.write_bytes(b"synthetic-dwg")
    drawing_hash = sha256_file(drawing)
    result = matching_setup_ipc_result(approved_setup_plan(), str(drawing.resolve()))
    result["payload"]["ignored_future_field"] = "not copied"
    original = copy.deepcopy(result)

    audit = create_setup_audit(drawing, drawing_hash, result)

    assert result == original
    assert set(audit) == {
        "schema_version",
        "drawing_full_path",
        "drawing_sha256",
        "changed",
        "dbmod_before",
        "dbmod_after",
        "variables",
        "current_layer",
        "custom_properties",
        "layers",
        "styles",
        "layouts",
        "font_report",
    }
    assert audit["drawing_full_path"] == str(drawing.resolve())
    assert audit["drawing_sha256"] == drawing_hash
    assert "ignored_future_field" not in audit
    output = tmp_path / "normalized-audit.json"
    output.write_text(json.dumps(audit), encoding="utf-8")
    assert read_contract(output, contract="drawing_setup_audit") == audit


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("success", False, "successful"),
        ("changed", True, "read-only"),
        ("entity_handles", ["2F"], "read-only"),
    ],
)
def test_create_setup_audit_rejects_unsafe_ipc_envelopes(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    drawing = tmp_path / "setup-lite.dwg"
    drawing.write_bytes(b"synthetic-dwg")
    result = matching_setup_ipc_result(approved_setup_plan(), str(drawing.resolve()))
    result[field] = value

    with pytest.raises(DrawingSetupError, match=message):
        create_setup_audit(drawing, sha256_file(drawing), result)


@pytest.mark.parametrize("digest", [None, "bad", "A" * 64])
def test_create_setup_audit_rejects_noncanonical_drawing_hash(
    tmp_path: Path, digest: object
) -> None:
    drawing = tmp_path / "setup-lite.dwg"
    drawing.write_bytes(b"synthetic-dwg")
    result = matching_setup_ipc_result(approved_setup_plan(), str(drawing.resolve()))

    with pytest.raises(DrawingSetupError, match="SHA-256"):
        create_setup_audit(drawing, digest, result)  # type: ignore[arg-type]


def test_drawing_setup_audit_cli_writes_a_hash_bound_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drawing = tmp_path / "setup-lite.dwg"
    drawing.write_bytes(b"synthetic-dwg")
    output = tmp_path / "drawing-setup-audit.json"
    observed: dict[str, object] = {}

    def audit(
        _self: DotNetIPCClient,
        drawing_full_path: str | Path,
        *,
        drawing_sha256: str,
        request_id: str | None = None,
    ) -> dict[str, object]:
        observed["path"] = Path(drawing_full_path)
        observed["sha256"] = drawing_sha256
        return matching_setup_ipc_result(
            approved_setup_plan(), str(Path(drawing_full_path).resolve())
        )

    monkeypatch.setattr(DotNetIPCClient, "drawing_setup_audit", audit)

    assert main([
        "drawing-setup-audit",
        "--drawing", str(drawing),
        "--hwnd", "123",
        "--ipc-dir", str(tmp_path / "ipc"),
        "--output", str(output),
    ]) == 0

    artifact = read_contract(output, contract="drawing_setup_audit")
    assert observed == {"path": drawing.resolve(), "sha256": sha256_file(drawing)}
    assert artifact["drawing_sha256"] == sha256_file(drawing)
    assert artifact["drawing_full_path"] == str(drawing.resolve())


def test_drawing_setup_audit_cli_refuses_when_drawing_hash_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    drawing = tmp_path / "setup-lite.dwg"
    drawing.write_bytes(b"before")
    output = tmp_path / "audit.json"

    def mutate_and_return(*_args: object, **_kwargs: object) -> dict[str, object]:
        drawing.write_bytes(b"after")
        return matching_setup_ipc_result(approved_setup_plan(), str(drawing.resolve()))

    monkeypatch.setattr(DotNetIPCClient, "drawing_setup_audit", mutate_and_return)

    assert main([
        "drawing-setup-audit",
        "--drawing", str(drawing),
        "--hwnd", "123",
        "--ipc-dir", str(tmp_path),
        "--output", str(output),
    ]) == 2
    assert "source_changed" in capsys.readouterr().err
    assert not output.exists()


def test_drawing_setup_audit_cli_reports_ipc_failure_without_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    drawing = tmp_path / "setup-lite.dwg"
    drawing.write_bytes(b"synthetic-dwg")
    output = tmp_path / "audit.json"

    def fail(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise DotNetIPCResultError("active drawing mismatch")

    monkeypatch.setattr(DotNetIPCClient, "drawing_setup_audit", fail)

    assert main([
        "drawing-setup-audit",
        "--drawing", str(drawing),
        "--hwnd", "123",
        "--ipc-dir", str(tmp_path),
        "--output", str(output),
    ]) == 2
    assert "active drawing mismatch" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize("output_kind", ["drawing", "existing_json"])
def test_drawing_setup_audit_cli_never_overwrites_an_existing_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_kind: str,
) -> None:
    drawing = tmp_path / "setup-lite.dwg"
    drawing.write_bytes(b"original-drawing")
    output = drawing if output_kind == "drawing" else tmp_path / "audit.json"
    if output_kind == "existing_json":
        output.write_bytes(b"original-audit")
    original = output.read_bytes()

    def unexpected_call(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("IPC must not run for an unsafe output path")

    monkeypatch.setattr(DotNetIPCClient, "drawing_setup_audit", unexpected_call)

    assert main([
        "drawing-setup-audit",
        "--drawing", str(drawing),
        "--hwnd", "123",
        "--ipc-dir", str(tmp_path),
        "--output", str(output),
    ]) == 2
    assert output.read_bytes() == original


@pytest.mark.parametrize("kind", ["missing", "directory", "wrong_extension"])
def test_drawing_setup_audit_cli_requires_a_regular_dwg_or_dxf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    drawing = tmp_path / ("setup-lite.txt" if kind == "wrong_extension" else "setup-lite.dwg")
    if kind == "directory":
        drawing.mkdir()
    elif kind == "wrong_extension":
        drawing.write_bytes(b"not-a-drawing")
    output = tmp_path / "audit.json"

    def unexpected_call(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("IPC must not run for an invalid drawing path")

    monkeypatch.setattr(DotNetIPCClient, "drawing_setup_audit", unexpected_call)

    assert main([
        "drawing-setup-audit",
        "--drawing", str(drawing),
        "--hwnd", "123",
        "--ipc-dir", str(tmp_path),
        "--output", str(output),
    ]) == 2
    assert not output.exists()


def test_deferred_drawing_setup_cli_boundaries_fail_explicitly_without_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    arguments = [
        "drawing-setup-verify",
        "--plan", "plan.json",
        "--audit", "audit.json",
        "--verified-by", "ENGINEER",
        "--approval-reference", "M2-001",
        "--output", "evidence.json",
    ]
    resolved = [str(tmp_path / value) if value.endswith((".dwg", ".json")) or value == "ipc" else value for value in arguments]
    output = Path(resolved[resolved.index("--output") + 1])

    assert main(resolved) == 2
    assert "unsupported_operation" in capsys.readouterr().err
    assert not output.exists()
