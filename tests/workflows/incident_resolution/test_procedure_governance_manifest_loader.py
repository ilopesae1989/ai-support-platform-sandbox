from __future__ import annotations

import inspect
import json

import pytest

import src.workflows.incident_resolution.procedure_governance as governance_module

from src.workflows.incident_resolution.procedure_catalog import (
    ProcedureCatalog,
    ProcedureDefinition,
)


MISSING = (
    "F25_PROCEDURE_GOVERNANCE_MANIFEST_LOADER_NOT_IMPLEMENTED"
)


EXPECTED_RECORD_KEYS = {
    "procedure_id",
    "procedure_version",
    "owner",
    "governance_approval_status",
    "governance_approval_reference",
    "compatible_previous_versions",
    "rollback_version",
}


def _definition(
    *,
    procedure_id="PROC-A",
    procedure_version="1.0",
):
    return ProcedureDefinition(
        procedure_id=procedure_id,
        procedure_version=procedure_version,
        procedure_name=(
            f"Procedure {procedure_id} {procedure_version}"
        ),
        lifecycle="published",
        step_ids=("1",),
    )


def _catalog():
    return ProcedureCatalog(
        definitions=(
            _definition(
                procedure_version="1.0",
            ),
            _definition(
                procedure_version="2.0",
            ),
        )
    )


def _record(
    *,
    procedure_id="PROC-A",
    procedure_version="2.0",
    owner="team-platform",
    governance_approval_status="approved",
    governance_approval_reference="CAB-TEST-001",
    compatible_previous_versions=None,
    rollback_version="1.0",
):
    if compatible_previous_versions is None:
        compatible_previous_versions = [
            "1.0",
        ]

    return {
        "procedure_id": procedure_id,
        "procedure_version": procedure_version,
        "owner": owner,
        "governance_approval_status": (
            governance_approval_status
        ),
        "governance_approval_reference": (
            governance_approval_reference
        ),
        "compatible_previous_versions": (
            compatible_previous_versions
        ),
        "rollback_version": rollback_version,
    }


def _payload(
    *,
    procedures=None,
):
    if procedures is None:
        procedures = [
            _record(),
        ]

    return {
        "schema_version": "1.0",
        "procedures": procedures,
    }


def _loader():
    loader = getattr(
        governance_module,
        "load_procedure_governance",
        None,
    )

    if loader is None:
        pytest.fail(
            MISSING,
            pytrace=False,
        )

    return loader


def _write_json(
    path,
    payload,
):
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_governance_manifest_loader_surface_is_missing_red():
    missing = [
        name
        for name in (
            "PROCEDURE_GOVERNANCE_SCHEMA_VERSION",
            "load_procedure_governance",
        )
        if not hasattr(
            governance_module,
            name,
        )
    ]

    assert not missing, (
        MISSING
        + ": "
        + ",".join(missing)
    )


def test_loader_contract_requires_explicit_catalog_keyword():
    loader = _loader()

    signature = inspect.signature(
        loader
    )

    assert tuple(
        signature.parameters
    ) == (
        "path",
        "catalog",
    )

    catalog_parameter = (
        signature.parameters[
            "catalog"
        ]
    )

    assert (
        catalog_parameter.kind
        is inspect.Parameter.KEYWORD_ONLY
    )

    assert (
        catalog_parameter.default
        is inspect.Parameter.empty
    )


def test_schema_version_is_exact_1_0():
    assert (
        governance_module
        .PROCEDURE_GOVERNANCE_SCHEMA_VERSION
        == "1.0"
    )


def test_loader_builds_registry_from_exact_manifest(
    tmp_path,
):
    path = (
        tmp_path
        / "governance.json"
    )

    _write_json(
        path,
        _payload(),
    )

    registry = _loader()(
        path,
        catalog=_catalog(),
    )

    assert isinstance(
        registry,
        governance_module
        .ProcedureGovernanceRegistry,
    )

    assert registry.count() == 1

    item = registry.get(
        "PROC-A",
        "2.0",
    )

    assert (
        item.procedure_id
        == "PROC-A"
    )
    assert (
        item.procedure_version
        == "2.0"
    )
    assert (
        item.owner
        == "team-platform"
    )
    assert (
        item.governance_approval_status
        == "approved"
    )
    assert (
        item.governance_approval_reference
        == "CAB-TEST-001"
    )
    assert (
        item.compatible_previous_versions
        == (
            "1.0",
        )
    )
    assert (
        item.rollback_version
        == "1.0"
    )


@pytest.mark.parametrize(
    "payload",
    (
        {
            "schema_version": "1.0",
        },
        {
            "procedures": [],
        },
        {
            "schema_version": "1.0",
            "procedures": [],
            "unexpected": True,
        },
    ),
)
def test_loader_requires_exact_root_members(
    tmp_path,
    payload,
):
    path = (
        tmp_path
        / "governance.json"
    )

    _write_json(
        path,
        payload,
    )

    with pytest.raises(
        governance_module
        .ProcedureGovernanceError
    ):
        _loader()(
            path,
            catalog=_catalog(),
        )


def test_loader_rejects_unsupported_schema_version(
    tmp_path,
):
    path = (
        tmp_path
        / "governance.json"
    )

    payload = _payload()
    payload[
        "schema_version"
    ] = "2.0"

    _write_json(
        path,
        payload,
    )

    with pytest.raises(
        governance_module
        .ProcedureGovernanceError
    ):
        _loader()(
            path,
            catalog=_catalog(),
        )


def test_loader_requires_procedures_json_array(
    tmp_path,
):
    path = (
        tmp_path
        / "governance.json"
    )

    payload = _payload()
    payload[
        "procedures"
    ] = {}

    _write_json(
        path,
        payload,
    )

    with pytest.raises(
        governance_module
        .ProcedureGovernanceError
    ):
        _loader()(
            path,
            catalog=_catalog(),
        )


def test_loader_requires_exact_record_members(
    tmp_path,
):
    valid = _record()

    assert set(
        valid
    ) == EXPECTED_RECORD_KEYS

    unknown = dict(
        valid
    )
    unknown[
        "capability_id"
    ] = "azure.vm.start"

    missing = dict(
        valid
    )
    del missing[
        "owner"
    ]

    for record in (
        unknown,
        missing,
    ):
        path = (
            tmp_path
            / (
                "governance-"
                + str(
                    len(record)
                )
                + ".json"
            )
        )

        _write_json(
            path,
            _payload(
                procedures=[
                    record,
                ]
            ),
        )

        with pytest.raises(
            governance_module
            .ProcedureGovernanceError
        ):
            _loader()(
                path,
                catalog=_catalog(),
            )


def test_loader_rejects_duplicate_json_members(
    tmp_path,
):
    path = (
        tmp_path
        / "duplicate.json"
    )

    path.write_text(
        (
            '{"schema_version":"1.0",'
            '"schema_version":"1.0",'
            '"procedures":[]}'
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        governance_module
        .ProcedureGovernanceError
    ):
        _loader()(
            path,
            catalog=_catalog(),
        )


def test_loader_fails_closed_for_malformed_unicode_and_io(
    tmp_path,
):
    malformed = (
        tmp_path
        / "malformed.json"
    )

    malformed.write_text(
        '{"schema_version":',
        encoding="utf-8",
    )

    invalid_unicode = (
        tmp_path
        / "unicode.json"
    )

    invalid_unicode.write_bytes(
        b"\xff\xfe\xff"
    )

    missing = (
        tmp_path
        / "missing.json"
    )

    for path in (
        malformed,
        invalid_unicode,
        missing,
    ):
        with pytest.raises(
            governance_module
            .ProcedureGovernanceError
        ):
            _loader()(
                path,
                catalog=_catalog(),
            )


def test_loader_delegates_metadata_validation_fail_closed(
    tmp_path,
):
    path = (
        tmp_path
        / "governance.json"
    )

    invalid = _record(
        governance_approval_status="pending",
        governance_approval_reference=(
            "MUST-NOT-EXIST"
        ),
        rollback_version=None,
    )

    _write_json(
        path,
        _payload(
            procedures=[
                invalid,
            ]
        ),
    )

    with pytest.raises(
        governance_module
        .ProcedureGovernanceError
    ):
        _loader()(
            path,
            catalog=_catalog(),
        )


def test_loader_delegates_exact_catalog_binding_fail_closed(
    tmp_path,
):
    unknown_current = (
        tmp_path
        / "unknown-current.json"
    )

    _write_json(
        unknown_current,
        _payload(
            procedures=[
                _record(
                    procedure_version="9.0",
                    compatible_previous_versions=[],
                    rollback_version=None,
                ),
            ]
        ),
    )

    with pytest.raises(
        governance_module
        .ProcedureGovernanceError
    ):
        _loader()(
            unknown_current,
            catalog=_catalog(),
        )

    unknown_previous = (
        tmp_path
        / "unknown-previous.json"
    )

    _write_json(
        unknown_previous,
        _payload(
            procedures=[
                _record(
                    compatible_previous_versions=[
                        "0.9",
                    ],
                    rollback_version="0.9",
                ),
            ]
        ),
    )

    with pytest.raises(
        governance_module
        .ProcedureGovernanceError
    ):
        _loader()(
            unknown_previous,
            catalog=_catalog(),
        )


def test_loader_rejects_duplicate_exact_governance_identity(
    tmp_path,
):
    path = (
        tmp_path
        / "duplicate-identity.json"
    )

    _write_json(
        path,
        _payload(
            procedures=[
                _record(),
                _record(
                    owner="team-other",
                    governance_approval_reference=(
                        "CAB-TEST-002"
                    ),
                ),
            ]
        ),
    )

    with pytest.raises(
        governance_module
        .ProcedureGovernanceError
    ):
        _loader()(
            path,
            catalog=_catalog(),
        )


def test_loader_rejects_invalid_catalog_dependency(
    tmp_path,
):
    path = (
        tmp_path
        / "governance.json"
    )

    _write_json(
        path,
        _payload(),
    )

    with pytest.raises(
        governance_module
        .ProcedureGovernanceError
    ):
        _loader()(
            path,
            catalog=None,
        )