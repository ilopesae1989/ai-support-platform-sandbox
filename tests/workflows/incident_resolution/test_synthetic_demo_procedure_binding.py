from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from src.workflows.incident_resolution.operational_context import (
    OperationalContext,
)

from src.workflows.incident_resolution.procedure_capability_binding import (
    ProcedureCapabilityBindingError,
)

from src.workflows.incident_resolution.procedure_capability_registry import (
    build_default_procedure_capability_registry,
)

from src.workflows.incident_resolution.executors.runtime import (
    ProcedureRuntimeExecutor,
)


TDD_MARKER = (
    "TDD_PHASE18_SYNTHETIC_DEMO_PROCEDURE_BINDING_RED"
)


DEMO_PROCEDURE_ID = (
    "NTTSY-SBX-AZ-VM-DEMO-001"
)

REAL_PROCEDURES = (
    "NTTSY-SBX-AZ-VM-001",
    "NTTSY-SBX-AZ-VM-002",
)


def _context(
    *,
    environment: str = "sandbox",
    incident_origin: str = "synthetic_demo",
) -> OperationalContext:

    return OperationalContext(
        alert_id="demo-binding-test",

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
            "corr-demo-binding"
        ),
    )


def test_default_registry_contains_demo_binding():
    registry = (
        build_default_procedure_capability_registry()
    )

    assert registry.contains_binding(
        procedure_id=(
            DEMO_PROCEDURE_ID
        ),

        procedure_version="1.0",

        step_id="1",
    )


def test_default_registry_now_contains_exactly_three_bindings():
    registry = (
        build_default_procedure_capability_registry()
    )

    assert registry.count() == 3


def test_demo_binding_is_sandbox_synthetic_only():
    registry = (
        build_default_procedure_capability_registry()
    )

    binding = registry.get_binding(
        procedure_id=(
            DEMO_PROCEDURE_ID
        ),

        procedure_version="1.0",

        step_id="1",
    )

    assert (
        binding.applicability
        .allowed_environments
        == (
            "sandbox",
        )
    )

    assert (
        binding.applicability
        .allowed_incident_origins
        == (
            "synthetic_demo",
        )
    )


def test_demo_binding_reuses_governed_vm_start_capability():
    registry = (
        build_default_procedure_capability_registry()
    )

    capability = (
        registry
        .resolve_capability(
            procedure_id=(
                DEMO_PROCEDURE_ID
            ),

            procedure_version="1.0",

            step_id="1",
        )
    )

    assert (
        capability.capability_id
        == "azure.vm.start"
    )

    assert (
        capability.hitl_required
        is True
    )


def test_demo_binding_accepts_synthetic_sandbox():
    registry = (
        build_default_procedure_capability_registry()
    )

    capability = (
        registry
        .resolve_applicable_capability(
            procedure_id=(
                DEMO_PROCEDURE_ID
            ),

            procedure_version="1.0",

            step_id="1",

            operational_context=(
                _context()
            ),
        )
    )

    assert (
        capability.capability_id
        == "azure.vm.start"
    )


def test_demo_binding_rejects_observed_incident():
    registry = (
        build_default_procedure_capability_registry()
    )

    with pytest.raises(
        ProcedureCapabilityBindingError,
        match="incident_origin",
    ):
        registry.resolve_applicable_capability(
            procedure_id=(
                DEMO_PROCEDURE_ID
            ),

            procedure_version="1.0",

            step_id="1",

            operational_context=(
                _context(
                    incident_origin=(
                        "observed"
                    )
                )
            ),
        )


def test_demo_binding_rejects_non_sandbox_environment():
    registry = (
        build_default_procedure_capability_registry()
    )

    with pytest.raises(
        ProcedureCapabilityBindingError,
        match="environment",
    ):
        registry.resolve_applicable_capability(
            procedure_id=(
                DEMO_PROCEDURE_ID
            ),

            procedure_version="1.0",

            step_id="1",

            operational_context=(
                _context(
                    environment=(
                        "production"
                    )
                )
            ),
        )


def test_real_vm_bindings_remain_observed_only():
    registry = (
        build_default_procedure_capability_registry()
    )

    for procedure_id in REAL_PROCEDURES:
        binding = registry.get_binding(
            procedure_id=(
                procedure_id
            ),

            procedure_version="1.0",

            step_id="1",
        )

        assert (
            binding.applicability
            .allowed_environments
            == (
                "sandbox",
            )
        )

        assert (
            binding.applicability
            .allowed_incident_origins
            == (
                "observed",
            )
        )

        with pytest.raises(
            ProcedureCapabilityBindingError,
            match="incident_origin",
        ):
            registry.resolve_applicable_capability(
                procedure_id=(
                    procedure_id
                ),

                procedure_version="1.0",

                step_id="1",

                operational_context=(
                    _context()
                ),
            )


def test_runtime_remains_procedure_agnostic():
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

    for procedure_id in (
        *REAL_PROCEDURES,
        DEMO_PROCEDURE_ID,
    ):
        assert procedure_id not in source