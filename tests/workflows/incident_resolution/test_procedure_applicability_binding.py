from __future__ import annotations

import ast
import inspect
import textwrap

from dataclasses import (
    FrozenInstanceError,
    is_dataclass,
)

import pytest

import src.workflows.incident_resolution.procedure_capability_registry as registry_module

from src.workflows.incident_resolution.capability_registry import (
    build_default_capability_registry,
)

from src.workflows.incident_resolution.operational_context import (
    OperationalContext,
)


TDD_MARKER = (
    "TDD_PHASE18_PROCEDURE_APPLICABILITY_BINDING_RED"
)


PROCEDURE_ID = (
    "PROC-APPLICABILITY-TEST"
)

VERSION = "1.0"
STEP_ID = "1"


def _applicability_type():
    assert hasattr(
        registry_module,
        "ProcedureApplicability",
    )

    return (
        registry_module
        .ProcedureApplicability
    )


def _context(
    *,
    environment: str = "sandbox",
    incident_origin: str = "observed",
) -> OperationalContext:

    return OperationalContext(
        alert_id=(
            "ALT-APPLICABILITY-001"
        ),

        affected_resource="vm-demo",

        resource_type=(
            "Microsoft.Compute/"
            "virtualMachines"
        ),

        service=(
            "Azure Virtual Machines"
        ),

        environment=environment,

        incident_origin=(
            incident_origin
        ),

        subscription_id="sub-test",

        resource_group="rg-test",

        vm_name="vm-demo",

        tenant_id=None,

        correlation_id=(
            "corr-applicability-001"
        ),
    )


def _applicability(
    *,
    environments=(
        "sandbox",
    ),
    origins=(
        "observed",
    ),
):
    cls = _applicability_type()

    return cls(
        allowed_environments=(
            environments
        ),

        allowed_incident_origins=(
            origins
        ),
    )


def _registry(
    *,
    applicability,
):
    binding = (
        registry_module
        .ProcedureCapabilityBinding(
            procedure_id=(
                PROCEDURE_ID
            ),

            procedure_version=(
                VERSION
            ),

            step_id=(
                STEP_ID
            ),

            capability_id=(
                "azure.vm.start"
            ),

            applicability=(
                applicability
            ),
        )
    )

    return (
        registry_module
        .ProcedureCapabilityRegistry(
            capability_registry=(
                build_default_capability_registry()
            ),

            bindings=[
                binding,
            ],
        )
    )


def test_procedure_applicability_contract_exists_and_is_frozen():
    cls = _applicability_type()

    assert is_dataclass(
        cls
    )

    value = cls(
        allowed_environments=(
            "sandbox",
        ),

        allowed_incident_origins=(
            "observed",
        ),
    )

    assert (
        value.allowed_environments
        == (
            "sandbox",
        )
    )

    assert (
        value.allowed_incident_origins
        == (
            "observed",
        )
    )

    with pytest.raises(
        FrozenInstanceError
    ):
        value.allowed_environments = (
            "production",
        )


def test_binding_requires_explicit_applicability():
    signature = inspect.signature(
        registry_module
        .ProcedureCapabilityBinding
    )

    assert (
        "applicability"
        in signature.parameters
    )

    parameter = (
        signature.parameters[
            "applicability"
        ]
    )

    assert (
        parameter.default
        is inspect.Parameter.empty
    )


@pytest.mark.parametrize(
    (
        "environments",
        "origins",
    ),
    [
        (
            (),
            (
                "observed",
            ),
        ),
        (
            (
                "sandbox",
            ),
            (),
        ),
        (
            (
                "sandbox",
                "sandbox",
            ),
            (
                "observed",
            ),
        ),
        (
            (
                "sandbox",
            ),
            (
                "observed",
                "observed",
            ),
        ),
    ],
)
def test_applicability_rejects_empty_or_duplicate_constraints(
    environments,
    origins,
):
    cls = _applicability_type()

    with pytest.raises(
        ValueError
    ):
        cls(
            allowed_environments=(
                environments
            ),

            allowed_incident_origins=(
                origins
            ),
        )


def test_applicability_rejects_unknown_incident_origin():
    cls = _applicability_type()

    with pytest.raises(
        ValueError,
        match="incident_origin",
    ):
        cls(
            allowed_environments=(
                "sandbox",
            ),

            allowed_incident_origins=(
                "attacker_controlled",
            ),
        )


def test_registry_exposes_context_aware_resolution():
    assert hasattr(
        registry_module
        .ProcedureCapabilityRegistry,
        "resolve_applicable_capability",
    )


def test_context_aware_resolution_accepts_exact_context():
    registry = _registry(
        applicability=(
            _applicability()
        )
    )

    capability = (
        registry
        .resolve_applicable_capability(
            procedure_id=(
                PROCEDURE_ID
            ),

            procedure_version=(
                VERSION
            ),

            step_id=(
                STEP_ID
            ),

            operational_context=(
                _context()
            ),
        )
    )

    assert (
        capability.capability_id
        == "azure.vm.start"
    )


def test_context_aware_resolution_rejects_environment_mismatch():
    registry = _registry(
        applicability=(
            _applicability()
        )
    )

    with pytest.raises(
        ValueError,
        match="environment",
    ):
        registry.resolve_applicable_capability(
            procedure_id=(
                PROCEDURE_ID
            ),

            procedure_version=(
                VERSION
            ),

            step_id=(
                STEP_ID
            ),

            operational_context=(
                _context(
                    environment=(
                        "production"
                    )
                )
            ),
        )


def test_context_aware_resolution_does_not_normalize_environment():
    registry = _registry(
        applicability=(
            _applicability()
        )
    )

    with pytest.raises(
        ValueError,
        match="environment",
    ):
        registry.resolve_applicable_capability(
            procedure_id=(
                PROCEDURE_ID
            ),

            procedure_version=(
                VERSION
            ),

            step_id=(
                STEP_ID
            ),

            operational_context=(
                _context(
                    environment=(
                        "Sandbox"
                    )
                )
            ),
        )


def test_context_aware_resolution_rejects_incident_origin_mismatch():
    registry = _registry(
        applicability=(
            _applicability()
        )
    )

    with pytest.raises(
        ValueError,
        match="incident_origin",
    ):
        registry.resolve_applicable_capability(
            procedure_id=(
                PROCEDURE_ID
            ),

            procedure_version=(
                VERSION
            ),

            step_id=(
                STEP_ID
            ),

            operational_context=(
                _context(
                    incident_origin=(
                        "synthetic_demo"
                    )
                )
            ),
        )


def test_default_real_vm_bindings_are_observed_sandbox_only():
    registry = (
        registry_module
        .build_default_procedure_capability_registry()
    )

    for procedure_id in (
        "NTTSY-SBX-AZ-VM-001",
        "NTTSY-SBX-AZ-VM-002",
    ):
        binding = (
            registry
            .get_binding(
                procedure_id=(
                    procedure_id
                ),

                procedure_version="1.0",

                step_id="1",
            )
        )

        assert (
            binding
            .applicability
            .allowed_environments
            == (
                "sandbox",
            )
        )

        assert (
            binding
            .applicability
            .allowed_incident_origins
            == (
                "observed",
            )
        )


def test_runtime_must_use_context_aware_resolution():
    from src.workflows.incident_resolution.executors.runtime import (
        ProcedureRuntimeExecutor,
    )

    source = inspect.getsource(
        ProcedureRuntimeExecutor
        ._resolve_governed_capability
    )

    tree = ast.parse(
        textwrap.dedent(
            source
        )
    )

    called_methods = [
        node.func.attr
        for node in ast.walk(
            tree
        )
        if isinstance(
            node,
            ast.Call,
        )
        and isinstance(
            node.func,
            ast.Attribute,
        )
    ]

    assert (
        "resolve_applicable_capability"
        in called_methods
    )

    assert (
        "resolve_capability"
        not in called_methods
    )
