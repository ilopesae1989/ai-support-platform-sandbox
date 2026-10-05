from __future__ import annotations

import importlib
import inspect

import pytest

from src.workflows.incident_resolution.procedure_admission import (
    LegacyProcedureCompatibility,
    ProcedureAdmissionPolicy,
    ProcedureNotAdmittedError,
)

from src.workflows.incident_resolution.procedure_catalog import (
    ProcedureCatalog,
    ProcedureDefinition,
)

from src.workflows.incident_resolution.procedure_governance import (
    ProcedureGovernanceApprovalPolicy,
    ProcedureGovernanceError,
    ProcedureGovernanceMetadata,
    ProcedureGovernanceRegistry,
)


TARGET = (
    "src.workflows.incident_resolution."
    "governed_procedure_admission"
)

MISSING = (
    "F25_GOVERNED_PROCEDURE_ADMISSION_NOT_IMPLEMENTED"
)


CATALOG_ID = "PROC-CAT"
CATALOG_VERSION = "2.0"
CATALOG_NAME = "Catalog Procedure"

LEGACY_ID = "PROC-LEGACY"
LEGACY_VERSION = "v1.1"
LEGACY_NAME = "Legacy Procedure"


def _module():
    try:
        return importlib.import_module(
            TARGET
        )
    except ModuleNotFoundError as exc:
        if exc.name != TARGET:
            raise

        pytest.fail(
            MISSING,
            pytrace=False,
        )


def _catalog():
    return ProcedureCatalog(
        definitions=(
            ProcedureDefinition(
                procedure_id=CATALOG_ID,
                procedure_version=(
                    CATALOG_VERSION
                ),
                procedure_name=CATALOG_NAME,
                lifecycle="published",
                step_ids=("1",),
            ),
        )
    )


def _admission_policy():
    return ProcedureAdmissionPolicy(
        catalog=_catalog(),
        legacy_compatibility=(
            LegacyProcedureCompatibility(
                procedure_id=LEGACY_ID,
                procedure_version=(
                    LEGACY_VERSION
                ),
                accepted_names=(
                    LEGACY_NAME,
                ),
            ),
        ),
    )


def _governance_policy(
    *,
    status="approved",
):
    reference = (
        "GOV-CAT-001"
        if status != "pending"
        else None
    )

    registry = ProcedureGovernanceRegistry(
        catalog=_catalog(),
        metadata=(
            ProcedureGovernanceMetadata(
                procedure_id=CATALOG_ID,
                procedure_version=(
                    CATALOG_VERSION
                ),
                owner="team-platform",
                governance_approval_status=(
                    status
                ),
                governance_approval_reference=(
                    reference
                ),
                compatible_previous_versions=(),
                rollback_version=None,
            ),
        ),
    )

    return ProcedureGovernanceApprovalPolicy(
        registry=registry,
    )


def _gate(
    *,
    governance_status="approved",
):
    module = _module()

    gate_type = getattr(
        module,
        "GovernedProcedureAdmissionPolicy",
        None,
    )

    if gate_type is None:
        pytest.fail(
            MISSING,
            pytrace=False,
        )

    return gate_type(
        admission_policy=(
            _admission_policy()
        ),
        governance_policy=(
            _governance_policy(
                status=governance_status,
            )
        ),
    )


def test_governed_admission_surface_is_missing_red():
    module = _module()

    assert hasattr(
        module,
        "GovernedProcedureAdmissionPolicy",
    ), MISSING


def test_constructor_requires_both_policies_as_keywords():
    module = _module()

    gate_type = (
        module
        .GovernedProcedureAdmissionPolicy
    )

    signature = inspect.signature(
        gate_type
    )

    assert tuple(
        signature.parameters
    ) == (
        "admission_policy",
        "governance_policy",
    )

    for parameter in (
        signature.parameters.values()
    ):
        assert (
            parameter.kind
            is inspect.Parameter.KEYWORD_ONLY
        )

        assert (
            parameter.default
            is inspect.Parameter.empty
        )


@pytest.mark.parametrize(
    (
        "admission_policy",
        "governance_policy",
    ),
    (
        (
            None,
            None,
        ),
        (
            None,
            "valid",
        ),
        (
            "valid",
            None,
        ),
    ),
)
def test_constructor_fails_closed_for_missing_dependencies(
    admission_policy,
    governance_policy,
):
    module = _module()

    actual_admission = (
        _admission_policy()
        if admission_policy == "valid"
        else admission_policy
    )

    actual_governance = (
        _governance_policy()
        if governance_policy == "valid"
        else governance_policy
    )

    with pytest.raises(
        TypeError
    ):
        module.GovernedProcedureAdmissionPolicy(
            admission_policy=(
                actual_admission
            ),
            governance_policy=(
                actual_governance
            ),
        )


def test_catalog_admission_requires_approved_governance():
    gate = _gate()

    result = gate.admit(
        procedure_id=CATALOG_ID,
        procedure_version=(
            CATALOG_VERSION
        ),
        procedure_name=CATALOG_NAME,
    )

    assert result.procedure_id == CATALOG_ID
    assert (
        result.procedure_version
        == CATALOG_VERSION
    )
    assert (
        result.procedure_name
        == CATALOG_NAME
    )
    assert result.source == "catalog"


@pytest.mark.parametrize(
    "status",
    (
        "pending",
        "rejected",
    ),
)
def test_catalog_admission_fails_when_governance_not_approved(
    status,
):
    gate = _gate(
        governance_status=status,
    )

    with pytest.raises(
        ProcedureGovernanceError
    ):
        gate.admit(
            procedure_id=CATALOG_ID,
            procedure_version=(
                CATALOG_VERSION
            ),
            procedure_name=CATALOG_NAME,
        )


def test_legacy_bridge_remains_explicit_and_does_not_become_catalog():
    gate = _gate(
        governance_status="rejected",
    )

    result = gate.admit(
        procedure_id=LEGACY_ID,
        procedure_version=(
            LEGACY_VERSION
        ),
        procedure_name=LEGACY_NAME,
    )

    assert result.procedure_id == LEGACY_ID
    assert (
        result.procedure_version
        == LEGACY_VERSION
    )
    assert (
        result.procedure_name
        == LEGACY_NAME
    )
    assert (
        result.source
        == "legacy_compatibility"
    )


def test_unknown_identity_fails_in_admission_before_governance():
    gate = _gate()

    with pytest.raises(
        ProcedureNotAdmittedError
    ):
        gate.admit(
            procedure_id="PROC-UNKNOWN",
            procedure_version="9.9",
            procedure_name="Unknown",
        )


@pytest.mark.parametrize(
    (
        "procedure_id",
        "procedure_version",
        "procedure_name",
    ),
    (
        (
            "proc-cat",
            CATALOG_VERSION,
            CATALOG_NAME,
        ),
        (
            CATALOG_ID,
            "2",
            CATALOG_NAME,
        ),
        (
            CATALOG_ID,
            CATALOG_VERSION,
            "catalog procedure",
        ),
        (
            "proc-legacy",
            LEGACY_VERSION,
            LEGACY_NAME,
        ),
        (
            LEGACY_ID,
            "v1",
            LEGACY_NAME,
        ),
        (
            LEGACY_ID,
            LEGACY_VERSION,
            "legacy procedure",
        ),
    ),
)
def test_gate_preserves_exact_admission_semantics(
    procedure_id,
    procedure_version,
    procedure_name,
):
    gate = _gate()

    with pytest.raises(
        ProcedureNotAdmittedError
    ):
        gate.admit(
            procedure_id=procedure_id,
            procedure_version=(
                procedure_version
            ),
            procedure_name=procedure_name,
        )


def test_gate_exposes_only_admission_behavior():
    gate = _gate()

    public_callables = {
        name
        for name in dir(gate)
        if not name.startswith("_")
        and callable(
            getattr(
                gate,
                name,
            )
        )
    }

    assert public_callables == {
        "admit",
    }


def test_gate_has_no_operational_authority():
    gate = _gate()

    for forbidden in (
        "execute",
        "approve",
        "resolve_capability",
        "resolve_applicable_capability",
        "create_approval",
        "create_approval_id",
        "resolve_owner",
        "resolve_operator",
        "rollback",
        "execute_rollback",
        "switch_version",
        "target_resource",
        "resolved_parameters",
    ):
        assert not hasattr(
            gate,
            forbidden,
        )