from __future__ import annotations

import pytest

import src.workflows.incident_resolution.procedure_governance as governance_module

from src.workflows.incident_resolution.procedure_catalog import (
    ProcedureCatalog,
    ProcedureDefinition,
)


MISSING = (
    "F25_PROCEDURE_GOVERNANCE_CATALOG_BINDING_NOT_IMPLEMENTED"
)


def _definition(
    *,
    procedure_id="PROC-A",
    procedure_version="1.0",
    lifecycle="published",
):
    return ProcedureDefinition(
        procedure_id=procedure_id,
        procedure_version=procedure_version,
        procedure_name=(
            f"Procedure {procedure_id} {procedure_version}"
        ),
        lifecycle=lifecycle,
        step_ids=("1",),
    )


def _metadata(
    *,
    procedure_id="PROC-A",
    procedure_version="2.0",
    owner="team-platform",
    governance_approval_status="approved",
    governance_approval_reference="CAB-TEST-001",
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
    *,
    catalog,
    metadata,
):
    registry_type = getattr(
        governance_module,
        "ProcedureGovernanceRegistry",
        None,
    )

    if registry_type is None:
        pytest.fail(
            MISSING,
            pytrace=False,
        )

    return registry_type(
        catalog=catalog,
        metadata=metadata,
    )


def test_governance_registry_surface_is_missing_red():
    assert hasattr(
        governance_module,
        "ProcedureGovernanceRegistry",
    ), MISSING


def test_registry_binds_exact_metadata_to_catalog_identity():
    previous = _definition(
        procedure_version="1.0",
    )
    current = _definition(
        procedure_version="2.0",
    )
    item = _metadata()

    registry = _registry(
        catalog=ProcedureCatalog(
            definitions=(
                previous,
                current,
            )
        ),
        metadata=(item,),
    )

    assert registry.count() == 1
    assert registry.contains(
        "PROC-A",
        "2.0",
    ) is True
    assert registry.get(
        "PROC-A",
        "2.0",
    ) is item


def test_registry_rejects_metadata_for_unknown_catalog_identity():
    catalog = ProcedureCatalog(
        definitions=(
            _definition(
                procedure_version="1.0",
            ),
        )
    )

    with pytest.raises(
        governance_module.ProcedureGovernanceError
    ):
        _registry(
            catalog=catalog,
            metadata=(
                _metadata(),
            ),
        )


def test_registry_rejects_missing_compatible_previous_version():
    catalog = ProcedureCatalog(
        definitions=(
            _definition(
                procedure_version="2.0",
            ),
        )
    )

    with pytest.raises(
        governance_module.ProcedureGovernanceError
    ):
        _registry(
            catalog=catalog,
            metadata=(
                _metadata(),
            ),
        )


def test_compatible_version_must_exist_for_same_procedure_id():
    catalog = ProcedureCatalog(
        definitions=(
            _definition(
                procedure_id="PROC-A",
                procedure_version="2.0",
            ),
            _definition(
                procedure_id="PROC-B",
                procedure_version="1.0",
            ),
        )
    )

    with pytest.raises(
        governance_module.ProcedureGovernanceError
    ):
        _registry(
            catalog=catalog,
            metadata=(
                _metadata(),
            ),
        )


def test_registry_rejects_duplicate_exact_governance_identity():
    catalog = ProcedureCatalog(
        definitions=(
            _definition(
                procedure_version="1.0",
            ),
            _definition(
                procedure_version="2.0",
            ),
        )
    )

    with pytest.raises(
        governance_module.ProcedureGovernanceError
    ):
        _registry(
            catalog=catalog,
            metadata=(
                _metadata(
                    owner="team-platform",
                ),
                _metadata(
                    owner="team-other",
                    governance_approval_reference=(
                        "CAB-TEST-002"
                    ),
                ),
            ),
        )


def test_lookup_is_exact_without_normalization_or_version_fallback():
    registry = _registry(
        catalog=ProcedureCatalog(
            definitions=(
                _definition(
                    procedure_version="1.0",
                ),
                _definition(
                    procedure_version="2.0",
                ),
            )
        ),
        metadata=(
            _metadata(),
        ),
    )

    for procedure_id, version in (
        ("proc-a", "2.0"),
        (" PROC-A", "2.0"),
        ("PROC-A ", "2.0"),
        ("PROC-A", "2"),
        ("PROC-A", "2.0 "),
        ("PROC-A", "1.0"),
    ):
        assert registry.contains(
            procedure_id,
            version,
        ) is False

        with pytest.raises(
            governance_module.ProcedureGovernanceError
        ):
            registry.get(
                procedure_id,
                version,
            )


def test_binding_is_configuration_only_and_does_not_require_published_lifecycle():
    item = _metadata(
        procedure_version="1.0",
        governance_approval_status="pending",
        governance_approval_reference=None,
        compatible_previous_versions=(),
        rollback_version=None,
    )

    registry = _registry(
        catalog=ProcedureCatalog(
            definitions=(
                _definition(
                    procedure_version="1.0",
                    lifecycle="draft",
                ),
            )
        ),
        metadata=(item,),
    )

    assert registry.get(
        "PROC-A",
        "1.0",
    ) is item

    for forbidden in (
        "register",
        "add",
        "update",
        "remove",
        "resolve_capability",
        "resolve_applicable_capability",
        "execute",
        "approve",
    ):
        assert not hasattr(
            registry,
            forbidden,
        )