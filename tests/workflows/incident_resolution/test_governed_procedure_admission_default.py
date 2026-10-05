from __future__ import annotations

import inspect

import pytest

import src.workflows.incident_resolution.governed_procedure_admission as governed_module

from src.workflows.incident_resolution.procedure_admission import (
    ProcedureNotAdmittedError,
)

from src.workflows.incident_resolution.procedure_governance import (
    ProcedureGovernanceError,
)


MISSING = (
    "F25_DEFAULT_GOVERNED_PROCEDURE_ADMISSION_NOT_IMPLEMENTED"
)


CATALOG_PROCEDURES = (
    (
        "NTTSY-SBX-AZ-VM-001",
        "1.0",
        (
            "Arranque de máquina virtual Azure "
            "en estado Stopped (Allocated)"
        ),
    ),
    (
        "NTTSY-SBX-AZ-VM-002",
        "1.0",
        (
            "Arranque de máquina virtual Azure "
            "en estado Deallocated"
        ),
    ),
    (
        "NTTSY-SBX-AZ-VM-DEMO-001",
        "1.0",
        (
            "Arranque de máquina virtual Azure "
            "(escenario demo synthetic_demo)"
        ),
    ),
)


LEGACY_NAMES = (
    "Alertas AlwaysOn_Rol_Change",
    "SQL AlwaysOn_Rol Change Alerta",
)


def _builder():
    builder = getattr(
        governed_module,
        "build_default_governed_procedure_admission_policy",
        None,
    )

    if builder is None:
        pytest.fail(
            MISSING,
            pytrace=False,
        )

    return builder


def _gate():
    return _builder()()


def test_default_governed_builder_surface_is_missing_red():
    assert hasattr(
        governed_module,
        "build_default_governed_procedure_admission_policy",
    ), MISSING


def test_default_governed_builder_requires_no_arguments():
    signature = inspect.signature(
        _builder()
    )

    assert tuple(
        signature.parameters
    ) == ()


def test_default_builder_returns_governed_policy():
    result = _gate()

    assert isinstance(
        result,
        governed_module.GovernedProcedureAdmissionPolicy,
    )


@pytest.mark.parametrize(
    "procedure_name",
    LEGACY_NAMES,
)
def test_default_empty_governance_preserves_exact_legacy_bridge(
    procedure_name,
):
    result = _gate().admit(
        procedure_id="NTTSY-PRO-016",
        procedure_version="v1.1",
        procedure_name=procedure_name,
    )

    assert result.procedure_id == "NTTSY-PRO-016"
    assert result.procedure_version == "v1.1"
    assert result.procedure_name == procedure_name

    assert (
        result.source
        == "legacy_compatibility"
    )


@pytest.mark.parametrize(
    (
        "procedure_id",
        "procedure_version",
        "procedure_name",
    ),
    CATALOG_PROCEDURES,
)
def test_default_empty_governance_blocks_every_catalog_identity(
    procedure_id,
    procedure_version,
    procedure_name,
):
    with pytest.raises(
        ProcedureGovernanceError
    ):
        _gate().admit(
            procedure_id=procedure_id,
            procedure_version=(
                procedure_version
            ),
            procedure_name=procedure_name,
        )


def test_default_governed_builder_does_not_invent_governance_records_or_manifest():
    source = inspect.getsource(
        governed_module
    )

    assert (
        "ProcedureGovernanceMetadata("
        not in source
    )

    assert (
        "load_procedure_governance("
        not in source
    )

    assert (
        "DEFAULT_PROCEDURE_GOVERNANCE"
        not in source
    )

    assert (
        "procedure_governance.v1.json"
        not in source
    )


def test_default_gate_keeps_unknown_identity_fail_closed():
    with pytest.raises(
        ProcedureNotAdmittedError
    ):
        _gate().admit(
            procedure_id="PROC-UNKNOWN",
            procedure_version="9.9",
            procedure_name="Unknown Procedure",
        )