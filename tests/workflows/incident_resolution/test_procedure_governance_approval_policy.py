from __future__ import annotations

import inspect

import pytest

import src.workflows.incident_resolution.procedure_governance as governance_module

from src.workflows.incident_resolution.procedure_catalog import (
    ProcedureCatalog,
    ProcedureDefinition,
)


MISSING = (
    "F25_PROCEDURE_GOVERNANCE_APPROVAL_POLICY_NOT_IMPLEMENTED"
)


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


def _metadata(
    *,
    procedure_id="PROC-A",
    procedure_version="2.0",
    owner="team-platform",
    governance_approval_status="approved",
    governance_approval_reference="GOV-TEST-001",
    compatible_previous_versions=("1.0",),
    rollback_version="1.0",
):
    return governance_module.ProcedureGovernanceMetadata(
        procedure_id=procedure_id,
        procedure_version=procedure_version,
        owner=owner,
        governance_approval_status=(
            governance_approval_status
        ),
        governance_approval_reference=(
            governance_approval_reference
        ),
        compatible_previous_versions=(
            compatible_previous_versions
        ),
        rollback_version=rollback_version,
    )


def _registry(
    *items,
):
    return governance_module.ProcedureGovernanceRegistry(
        catalog=_catalog(),
        metadata=items,
    )


def _policy(
    registry,
):
    policy_type = getattr(
        governance_module,
        "ProcedureGovernanceApprovalPolicy",
        None,
    )

    if policy_type is None:
        pytest.fail(
            MISSING,
            pytrace=False,
        )

    return policy_type(
        registry=registry,
    )


def test_governance_approval_policy_surface_is_missing_red():
    assert hasattr(
        governance_module,
        "ProcedureGovernanceApprovalPolicy",
    ), MISSING


def test_policy_constructor_requires_explicit_registry_keyword():
    policy_type = getattr(
        governance_module,
        "ProcedureGovernanceApprovalPolicy",
        None,
    )

    if policy_type is None:
        pytest.fail(
            MISSING,
            pytrace=False,
        )

    signature = inspect.signature(
        policy_type
    )

    assert tuple(
        signature.parameters
    ) == (
        "registry",
    )

    parameter = signature.parameters[
        "registry"
    ]

    assert (
        parameter.kind
        is inspect.Parameter.KEYWORD_ONLY
    )

    assert (
        parameter.default
        is inspect.Parameter.empty
    )


def test_policy_rejects_none_registry():
    policy_type = getattr(
        governance_module,
        "ProcedureGovernanceApprovalPolicy",
        None,
    )

    if policy_type is None:
        pytest.fail(
            MISSING,
            pytrace=False,
        )

    with pytest.raises(
        governance_module.ProcedureGovernanceError
    ):
        policy_type(
            registry=None,
        )


def test_policy_returns_exact_approved_governance_metadata():
    item = _metadata()

    policy = _policy(
        _registry(
            item,
        )
    )

    result = (
        policy
        .require_governance_approval(
            procedure_id="PROC-A",
            procedure_version="2.0",
        )
    )

    assert result is item

    assert (
        result.governance_approval_status
        == "approved"
    )

    assert (
        result.governance_approval_reference
        == "GOV-TEST-001"
    )

    assert (
        result.owner
        == "team-platform"
    )


@pytest.mark.parametrize(
    (
        "status",
        "reference",
    ),
    (
        (
            "pending",
            None,
        ),
        (
            "rejected",
            "GOV-TEST-REJECTED",
        ),
    ),
)
def test_policy_fails_closed_when_governance_is_not_approved(
    status,
    reference,
):
    item = _metadata(
        governance_approval_status=status,
        governance_approval_reference=reference,
        rollback_version=None,
    )

    policy = _policy(
        _registry(
            item,
        )
    )

    with pytest.raises(
        governance_module.ProcedureGovernanceError
    ):
        policy.require_governance_approval(
            procedure_id="PROC-A",
            procedure_version="2.0",
        )


def test_policy_fails_closed_when_exact_governance_identity_is_missing():
    policy = _policy(
        _registry()
    )

    with pytest.raises(
        governance_module.ProcedureGovernanceError
    ):
        policy.require_governance_approval(
            procedure_id="PROC-A",
            procedure_version="2.0",
        )


@pytest.mark.parametrize(
    (
        "procedure_id",
        "procedure_version",
    ),
    (
        (
            "proc-a",
            "2.0",
        ),
        (
            " PROC-A",
            "2.0",
        ),
        (
            "PROC-A ",
            "2.0",
        ),
        (
            "PROC-A",
            "2",
        ),
        (
            "PROC-A",
            "2.0 ",
        ),
    ),
)
def test_policy_lookup_is_exact_without_normalization(
    procedure_id,
    procedure_version,
):
    policy = _policy(
        _registry(
            _metadata(),
        )
    )

    with pytest.raises(
        governance_module.ProcedureGovernanceError
    ):
        policy.require_governance_approval(
            procedure_id=procedure_id,
            procedure_version=procedure_version,
        )


def test_compatible_previous_version_never_becomes_implicit_governance_fallback():
    policy = _policy(
        _registry(
            _metadata(
                procedure_version="2.0",
                compatible_previous_versions=(
                    "1.0",
                ),
                rollback_version="1.0",
            ),
        )
    )

    with pytest.raises(
        governance_module.ProcedureGovernanceError
    ):
        policy.require_governance_approval(
            procedure_id="PROC-A",
            procedure_version="1.0",
        )


def test_policy_does_not_resolve_owner_or_execute_rollback():
    policy = _policy(
        _registry(
            _metadata(),
        )
    )

    for forbidden in (
        "resolve_owner",
        "resolve_operator",
        "rollback",
        "execute_rollback",
        "switch_version",
    ):
        assert not hasattr(
            policy,
            forbidden,
        )


def test_policy_has_no_operational_or_hitl_authority():
    policy = _policy(
        _registry(
            _metadata(),
        )
    )

    for forbidden in (
        "approve",
        "execute",
        "resolve_capability",
        "resolve_applicable_capability",
        "create_approval",
        "create_approval_id",
        "target_resource",
        "resolved_parameters",
    ):
        assert not hasattr(
            policy,
            forbidden,
        )


def test_policy_exposes_only_governance_gate_behavior():
    policy = _policy(
        _registry(
            _metadata(),
        )
    )

    public_callables = {
        name
        for name in dir(policy)
        if not name.startswith("_")
        and callable(
            getattr(
                policy,
                name,
            )
        )
    }

    assert public_callables == {
        "require_governance_approval",
    }