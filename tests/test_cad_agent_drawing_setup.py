from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256, read_contract
from cad_agent.cli import main
from cad_agent.drawing_setup import DrawingSetupError, create_setup_plan
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
