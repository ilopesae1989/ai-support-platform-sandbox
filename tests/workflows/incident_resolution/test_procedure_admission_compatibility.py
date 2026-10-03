from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields
import importlib
import inspect
import json
from pathlib import Path

import pytest

TARGET = "src.workflows.incident_resolution.procedure_admission"
MISSING = "F25_PROCEDURE_ADMISSION_NOT_IMPLEMENTED"
LEGACY_ID = "NTTSY-PRO-016"
LEGACY_VERSION = "v1.1"
LEGACY_NAMES = (
    "Alertas AlwaysOn_Rol_Change",
    "SQL AlwaysOn_Rol Change Alerta",
)


def _api():
    try:
        return importlib.import_module(TARGET)
    except ModuleNotFoundError as exc:
        if exc.name != TARGET:
            raise
        pytest.fail(MISSING, pytrace=False)


def test_surface_is_explicit():
    module = _api()
    for name in (
        "PROCEDURE_COMPATIBILITY_SCHEMA_VERSION",
        "DEFAULT_PROCEDURE_COMPATIBILITY_PATH",
        "ProcedureAdmissionError",
        "ProcedureNotAdmittedError",
        "LegacyProcedureCompatibility",
        "ProcedureAdmission",
        "ProcedureAdmissionPolicy",
        "load_procedure_compatibility",
        "build_default_procedure_admission_policy",
    ):
        assert hasattr(module, name)


def test_legacy_definition_is_frozen_and_authority_free():
    module = _api()
    item = module.LegacyProcedureCompatibility(
        procedure_id=LEGACY_ID,
        procedure_version=LEGACY_VERSION,
        accepted_names=LEGACY_NAMES,
    )
    assert tuple(field.name for field in fields(item)) == (
        "procedure_id",
        "procedure_version",
        "accepted_names",
    )
    for forbidden in ("capability_id", "operation_action", "hitl_required"):
        assert not hasattr(item, forbidden)
    with pytest.raises(FrozenInstanceError):
        item.procedure_id = "OTHER"


def test_legacy_definition_requires_exact_identity_and_names():
    module = _api()
    invalid = (
        dict(procedure_id="", procedure_version=LEGACY_VERSION, accepted_names=LEGACY_NAMES),
        dict(procedure_id=" " + LEGACY_ID, procedure_version=LEGACY_VERSION, accepted_names=LEGACY_NAMES),
        dict(procedure_id=LEGACY_ID, procedure_version="", accepted_names=LEGACY_NAMES),
        dict(procedure_id=LEGACY_ID, procedure_version=LEGACY_VERSION + " ", accepted_names=LEGACY_NAMES),
        dict(procedure_id=LEGACY_ID, procedure_version=LEGACY_VERSION, accepted_names=[]),
        dict(procedure_id=LEGACY_ID, procedure_version=LEGACY_VERSION, accepted_names=()),
        dict(procedure_id=LEGACY_ID, procedure_version=LEGACY_VERSION, accepted_names=(" Name",)),
        dict(procedure_id=LEGACY_ID, procedure_version=LEGACY_VERSION, accepted_names=("Name ",)),
        dict(procedure_id=LEGACY_ID, procedure_version=LEGACY_VERSION, accepted_names=("Name", "Name")),
    )
    for kwargs in invalid:
        with pytest.raises(module.ProcedureAdmissionError):
            module.LegacyProcedureCompatibility(**kwargs)


def test_admission_result_is_frozen_and_authority_free():
    module = _api()
    result = module.ProcedureAdmission(
        procedure_id="PROC-A",
        procedure_version="1.0",
        procedure_name="Procedure A",
        source="catalog",
    )
    assert tuple(field.name for field in fields(result)) == (
        "procedure_id",
        "procedure_version",
        "procedure_name",
        "source",
    )
    for forbidden in ("capability_id", "operation_action", "target_resource"):
        assert not hasattr(result, forbidden)
    with pytest.raises(FrozenInstanceError):
        result.source = "legacy_compatibility"


def test_policy_admits_exact_published_catalog_identity():
    module = _api()
    result = module.build_default_procedure_admission_policy().admit(
        procedure_id="NTTSY-SBX-AZ-VM-001",
        procedure_version="1.0",
        procedure_name="Arranque de máquina virtual Azure en estado Stopped (Allocated)",
    )
    assert result.source == "catalog"


def test_policy_admits_only_exact_legacy_name_variants():
    module = _api()
    policy = module.build_default_procedure_admission_policy()
    for name in LEGACY_NAMES:
        result = policy.admit(
            procedure_id=LEGACY_ID,
            procedure_version=LEGACY_VERSION,
            procedure_name=name,
        )
        assert (
            result.procedure_id,
            result.procedure_version,
            result.procedure_name,
            result.source,
        ) == (
            LEGACY_ID,
            LEGACY_VERSION,
            name,
            "legacy_compatibility",
        )


def test_policy_rejects_legacy_identity_drift():
    module = _api()
    policy = module.build_default_procedure_admission_policy()
    invalid = (
        (LEGACY_ID, "v1.0", LEGACY_NAMES[0]),
        (LEGACY_ID, LEGACY_VERSION, LEGACY_NAMES[0].lower()),
        (LEGACY_ID, LEGACY_VERSION, " " + LEGACY_NAMES[0]),
        (LEGACY_ID, LEGACY_VERSION, LEGACY_NAMES[0] + " "),
        (LEGACY_ID.lower(), LEGACY_VERSION, LEGACY_NAMES[0]),
    )
    for procedure_id, version, name in invalid:
        with pytest.raises(module.ProcedureNotAdmittedError):
            policy.admit(
                procedure_id=procedure_id,
                procedure_version=version,
                procedure_name=name,
            )


def test_policy_rejects_unknown_identity():
    module = _api()
    with pytest.raises(module.ProcedureNotAdmittedError):
        module.build_default_procedure_admission_policy().admit(
            procedure_id="NTTSY-PRO-999",
            procedure_version="v9.9",
            procedure_name="Unapproved procedure",
        )


def test_default_compatibility_manifest_is_exact():
    module = _api()
    path = Path(module.DEFAULT_PROCEDURE_COMPATIBILITY_PATH)
    assert path.name == "procedure_compatibility.v1.json"
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": "1.0",
        "procedures": [
            {
                "procedure_id": LEGACY_ID,
                "procedure_version": LEGACY_VERSION,
                "accepted_names": list(LEGACY_NAMES),
            }
        ],
    }


def test_loader_accepts_exact_manifest(tmp_path):
    module = _api()
    path = tmp_path / "compat.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "procedures": [
                    {
                        "procedure_id": LEGACY_ID,
                        "procedure_version": LEGACY_VERSION,
                        "accepted_names": list(LEGACY_NAMES),
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    items = module.load_procedure_compatibility(path)
    assert type(items) is tuple
    assert len(items) == 1
    assert items[0].accepted_names == LEGACY_NAMES


def test_loader_fails_closed_for_invalid_manifests(tmp_path):
    module = _api()
    invalid = (
        {"schema_version": "2.0", "procedures": []},
        {"schema_version": "1.0", "procedures": {}},
        {"schema_version": "1.0", "procedures": [], "unexpected": True},
        {
            "schema_version": "1.0",
            "procedures": [
                {
                    "procedure_id": LEGACY_ID,
                    "procedure_version": LEGACY_VERSION,
                    "accepted_names": list(LEGACY_NAMES),
                    "capability_id": "azure.vm.start",
                }
            ],
        },
    )
    for index, payload in enumerate(invalid):
        path = tmp_path / f"invalid-{index}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(module.ProcedureAdmissionError):
            module.load_procedure_compatibility(path)

    malformed = tmp_path / "malformed.json"
    malformed.write_text('{"schema_version":', encoding="utf-8")
    with pytest.raises(module.ProcedureAdmissionError):
        module.load_procedure_compatibility(malformed)

    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        '{"schema_version":"1.0","schema_version":"1.0","procedures":[]}',
        encoding="utf-8",
    )
    with pytest.raises(module.ProcedureAdmissionError):
        module.load_procedure_compatibility(duplicate)


def test_module_remains_separate_from_operational_authority():
    module = _api()
    for method in ("resolve_capability", "execute", "approve"):
        assert not hasattr(module.ProcedureAdmissionPolicy, method)

    tree = ast.parse(inspect.getsource(module))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            imported.add(node.module or "")

    forbidden = (
        "agent_framework",
        "azure",
        "microsoft_teams",
        "src.agents",
        "src.channels",
        "src.persistence",
        "src.workflows.incident_resolution.procedure_capability_registry",
    )
    assert not any(
        root == prefix or root.startswith(prefix + ".")
        for root in imported
        for prefix in forbidden
    )
