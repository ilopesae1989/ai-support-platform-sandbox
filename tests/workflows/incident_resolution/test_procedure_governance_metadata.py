from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields
import importlib
import inspect

import pytest


TARGET = (
    "src.workflows.incident_resolution."
    "procedure_governance"
)

MISSING = (
    "F25_PROCEDURE_GOVERNANCE_METADATA_"
    "NOT_IMPLEMENTED"
)

BASE = {
    "procedure_id": "PROC-001",
    "procedure_version": "2.0",
    "owner": "team-database",
    "governance_approval_status": "approved",
    "governance_approval_reference": "CAB-2026-001",
    "compatible_previous_versions": (
        "1.0",
        "1.1",
    ),
    "rollback_version": "1.1",
}


def _api():
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


def test_governance_metadata_surface_is_explicit():
    module = _api()

    assert hasattr(
        module,
        "ProcedureGovernanceError",
    )

    assert hasattr(
        module,
        "ProcedureGovernanceMetadata",
    )


def test_governance_metadata_is_frozen_and_has_exact_fields():
    module = _api()

    item = module.ProcedureGovernanceMetadata(
        **BASE
    )

    assert tuple(
        field.name
        for field in fields(item)
    ) == (
        "procedure_id",
        "procedure_version",
        "owner",
        "governance_approval_status",
        "governance_approval_reference",
        "compatible_previous_versions",
        "rollback_version",
    )

    with pytest.raises(
        FrozenInstanceError
    ):
        item.owner = "team-other"


def test_governance_metadata_accepts_explicit_approved_record():
    module = _api()

    item = module.ProcedureGovernanceMetadata(
        **BASE
    )

    assert item.procedure_id == "PROC-001"
    assert item.procedure_version == "2.0"
    assert item.owner == "team-database"

    assert (
        item.governance_approval_status
        == "approved"
    )

    assert (
        item.governance_approval_reference
        == "CAB-2026-001"
    )

    assert (
        item.compatible_previous_versions
        == (
            "1.0",
            "1.1",
        )
    )

    assert item.rollback_version == "1.1"


def test_initial_version_can_have_no_compatibility_or_rollback():
    module = _api()

    payload = dict(BASE)

    payload[
        "procedure_version"
    ] = "1.0"

    payload[
        "compatible_previous_versions"
    ] = ()

    payload[
        "rollback_version"
    ] = None

    item = module.ProcedureGovernanceMetadata(
        **payload
    )

    assert (
        item.compatible_previous_versions
        == ()
    )

    assert item.rollback_version is None


def test_pending_governance_requires_no_approval_reference():
    module = _api()

    payload = dict(BASE)

    payload[
        "governance_approval_status"
    ] = "pending"

    payload[
        "governance_approval_reference"
    ] = None

    payload[
        "rollback_version"
    ] = None

    item = module.ProcedureGovernanceMetadata(
        **payload
    )

    assert (
        item.governance_approval_status
        == "pending"
    )

    assert (
        item.governance_approval_reference
        is None
    )


@pytest.mark.parametrize(
    (
        "field_name",
        "value",
    ),
    (
        (
            "procedure_id",
            "",
        ),
        (
            "procedure_id",
            " PROC-001",
        ),
        (
            "procedure_version",
            "",
        ),
        (
            "procedure_version",
            "2.0 ",
        ),
        (
            "owner",
            "",
        ),
        (
            "owner",
            " team-database",
        ),
    ),
)
def test_identity_and_owner_are_exact_nonblank_strings(
    field_name,
    value,
):
    module = _api()

    payload = dict(BASE)
    payload[field_name] = value

    with pytest.raises(
        module.ProcedureGovernanceError
    ):
        module.ProcedureGovernanceMetadata(
            **payload
        )


@pytest.mark.parametrize(
    "status",
    (
        "APPROVED",
        " approved",
        "approved ",
        "",
        "unknown",
    ),
)
def test_governance_approval_status_is_exact(
    status,
):
    module = _api()

    payload = dict(BASE)

    payload[
        "governance_approval_status"
    ] = status

    with pytest.raises(
        module.ProcedureGovernanceError
    ):
        module.ProcedureGovernanceMetadata(
            **payload
        )


def test_governance_approval_reference_rules_are_fail_closed():
    module = _api()

    invalid = (
        {
            **BASE,
            "governance_approval_status":
                "approved",
            "governance_approval_reference":
                None,
        },
        {
            **BASE,
            "governance_approval_status":
                "rejected",
            "governance_approval_reference":
                "",
        },
        {
            **BASE,
            "governance_approval_status":
                "approved",
            "governance_approval_reference":
                " CAB-2026-001",
        },
        {
            **BASE,
            "governance_approval_status":
                "pending",
            "governance_approval_reference":
                "CAB-2026-001",
        },
    )

    for payload in invalid:
        with pytest.raises(
            module.ProcedureGovernanceError
        ):
            module.ProcedureGovernanceMetadata(
                **payload
            )


def test_compatible_previous_versions_are_exact_unique_and_never_self():
    module = _api()

    invalid = (
        [],
        (
            "1.0",
            "1.0",
        ),
        (
            "2.0",
        ),
        (
            " 1.0",
        ),
        (
            "1.0 ",
        ),
        (
            "",
        ),
    )

    for versions in invalid:
        payload = dict(BASE)

        payload[
            "compatible_previous_versions"
        ] = versions

        with pytest.raises(
            module.ProcedureGovernanceError
        ):
            module.ProcedureGovernanceMetadata(
                **payload
            )


def test_rollback_version_is_optional_exact_compatible_and_never_self():
    module = _api()

    payload = dict(BASE)

    payload[
        "rollback_version"
    ] = None

    without_rollback = (
        module.ProcedureGovernanceMetadata(
            **payload
        )
    )

    assert (
        without_rollback.rollback_version
        is None
    )

    for rollback_version in (
        "",
        " 1.1",
        "1.1 ",
        "2.0",
        "0.9",
    ):
        payload = dict(BASE)

        payload[
            "rollback_version"
        ] = rollback_version

        with pytest.raises(
            module.ProcedureGovernanceError
        ):
            module.ProcedureGovernanceMetadata(
                **payload
            )


def test_governance_metadata_contains_no_operational_authority():
    module = _api()

    item = module.ProcedureGovernanceMetadata(
        **BASE
    )

    for forbidden in (
        "capability_id",
        "hitl_required",
        "approved",
        "operation_action",
        "operation_kind",
        "target_resource",
        "resolved_parameters",
    ):
        assert not hasattr(
            item,
            forbidden,
        )

    source = inspect.getsource(
        module
    )

    tree = ast.parse(
        source
    )

    imported_roots = set()

    for node in ast.walk(tree):
        if isinstance(
            node,
            ast.Import,
        ):
            imported_roots.update(
                alias.name
                for alias in node.names
            )

        elif (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.level == 0
        ):
            imported_roots.add(
                node.module or ""
            )

    forbidden_imports = (
        "agent_framework",
        "azure",
        "src.agents",
        "src.channels",
        "src.runtime.procedure",
        (
            "src.workflows.incident_resolution."
            "procedure_capability_registry"
        ),
    )

    assert not any(
        root == prefix
        or root.startswith(
            prefix + "."
        )
        for root in imported_roots
        for prefix in forbidden_imports
    )
