from dataclasses import (
    FrozenInstanceError,
)

import pytest

from src.runtime.procedure.models import (
    OperationAction,
    OperationKind,
)

from src.workflows.incident_resolution.capability_registry import (
    CapabilityNotFoundError,
    CapabilityRegistryError,
    CapabilityRegistry,
    DuplicateCapabilityError,
    DuplicateCapabilitySignatureError,
    build_default_capability_registry,
)

from src.workflows.incident_resolution.operational_capability import (
    OperationalCapability,
    OperationalCapabilityError,
)


def create_vm_start_capability(
    *,
    capability_id=(
        "azure.vm.start"
    ),
):
    return OperationalCapability(
        capability_id=capability_id,

        operation_domain="azure",

        resource_type=(
            "Microsoft.Compute/"
            "virtualMachines"
        ),

        operation_kind=(
            OperationKind.WRITE
        ),

        operation_action=(
            OperationAction.VM_START
        ),

        required_parameters=(
            "subscription_id",
            "resource_group",
            "vm_name",
        ),

        hitl_required=True,

        executor_id=(
            "azure_operations"
        ),
    )


def test_default_registry_contains_vm_start():
    registry = (
        build_default_capability_registry()
    )

    capability = registry.get(
        "azure.vm.start"
    )

    assert (
        capability.operation_domain
        == "azure"
    )

    assert (
        capability.resource_type
        == (
            "Microsoft.Compute/"
            "virtualMachines"
        )
    )

    assert (
        capability.operation_kind
        == OperationKind.WRITE
    )

    assert (
        capability.operation_action
        == OperationAction.VM_START
    )

    assert (
        capability.required_parameters
        == (
            "subscription_id",
            "resource_group",
            "vm_name",
        )
    )

    assert (
        capability.hitl_required
        is True
    )

    assert (
        capability.executor_id
        == "azure_operations"
    )


def test_default_registry_contains_only_installed_capabilities():
    registry = (
        build_default_capability_registry()
    )

    assert registry.count() == 1


def test_unknown_capability_fails_closed():
    registry = (
        build_default_capability_registry()
    )

    with pytest.raises(
        CapabilityNotFoundError,
    ):
        registry.get(
            "azure.vm.restart"
        )


def test_registry_does_not_normalize_capability_id():
    registry = (
        build_default_capability_registry()
    )

    with pytest.raises(
        CapabilityNotFoundError,
    ):
        registry.get(
            "Azure.VM.Start"
        )


def test_duplicate_capability_id_is_rejected():
    capability = (
        create_vm_start_capability()
    )

    with pytest.raises(
        DuplicateCapabilityError,
    ):
        CapabilityRegistry(
            capabilities=[
                capability,
                capability,
            ]
        )


def test_duplicate_operational_signature_is_rejected():
    first = (
        create_vm_start_capability(
            capability_id=(
                "azure.vm.start"
            )
        )
    )

    second = (
        create_vm_start_capability(
            capability_id=(
                "azure.vm.power_on"
            )
        )
    )

    with pytest.raises(
        DuplicateCapabilitySignatureError,
    ):
        CapabilityRegistry(
            capabilities=[
                first,
                second,
            ]
        )


def test_write_capability_cannot_disable_hitl():
    with pytest.raises(
        OperationalCapabilityError,
        match="hitl_required",
    ):
        OperationalCapability(
            capability_id=(
                "azure.vm.start"
            ),

            operation_domain="azure",

            resource_type=(
                "Microsoft.Compute/"
                "virtualMachines"
            ),

            operation_kind=(
                OperationKind.WRITE
            ),

            operation_action=(
                OperationAction.VM_START
            ),

            required_parameters=(
                "subscription_id",
                "resource_group",
                "vm_name",
            ),

            hitl_required=False,

            executor_id=(
                "azure_operations"
            ),
        )


def test_duplicate_required_parameters_are_rejected():
    with pytest.raises(
        OperationalCapabilityError,
        match="duplicados",
    ):
        OperationalCapability(
            capability_id=(
                "azure.vm.start"
            ),

            operation_domain="azure",

            resource_type=(
                "Microsoft.Compute/"
                "virtualMachines"
            ),

            operation_kind=(
                OperationKind.WRITE
            ),

            operation_action=(
                OperationAction.VM_START
            ),

            required_parameters=(
                "subscription_id",
                "vm_name",
                "vm_name",
            ),

            hitl_required=True,

            executor_id=(
                "azure_operations"
            ),
        )


def test_operation_kind_requires_exact_enum():
    with pytest.raises(
        OperationalCapabilityError,
        match="operation_kind",
    ):
        OperationalCapability(
            capability_id=(
                "azure.vm.start"
            ),

            operation_domain="azure",

            resource_type=(
                "Microsoft.Compute/"
                "virtualMachines"
            ),

            operation_kind="write",

            operation_action=(
                OperationAction.VM_START
            ),

            required_parameters=(
                "subscription_id",
                "resource_group",
                "vm_name",
            ),

            hitl_required=True,

            executor_id=(
                "azure_operations"
            ),
        )


def test_operation_action_requires_exact_enum():
    with pytest.raises(
        OperationalCapabilityError,
        match="operation_action",
    ):
        OperationalCapability(
            capability_id=(
                "azure.vm.start"
            ),

            operation_domain="azure",

            resource_type=(
                "Microsoft.Compute/"
                "virtualMachines"
            ),

            operation_kind=(
                OperationKind.WRITE
            ),

            operation_action="vm_start",

            required_parameters=(
                "subscription_id",
                "resource_group",
                "vm_name",
            ),

            hitl_required=True,

            executor_id=(
                "azure_operations"
            ),
        )


def test_required_parameters_must_be_immutable_tuple():
    with pytest.raises(
        OperationalCapabilityError,
        match="tuple",
    ):
        OperationalCapability(
            capability_id=(
                "azure.vm.start"
            ),

            operation_domain="azure",

            resource_type=(
                "Microsoft.Compute/"
                "virtualMachines"
            ),

            operation_kind=(
                OperationKind.WRITE
            ),

            operation_action=(
                OperationAction.VM_START
            ),

            required_parameters=[
                "subscription_id",
                "resource_group",
                "vm_name",
            ],

            hitl_required=True,

            executor_id=(
                "azure_operations"
            ),
        )


def test_hitl_required_must_be_bool():
    with pytest.raises(
        OperationalCapabilityError,
        match="hitl_required",
    ):
        OperationalCapability(
            capability_id=(
                "azure.vm.start"
            ),

            operation_domain="azure",

            resource_type=(
                "Microsoft.Compute/"
                "virtualMachines"
            ),

            operation_kind=(
                OperationKind.WRITE
            ),

            operation_action=(
                OperationAction.VM_START
            ),

            required_parameters=(
                "subscription_id",
                "resource_group",
                "vm_name",
            ),

            hitl_required="true",

            executor_id=(
                "azure_operations"
            ),
        )


def test_registered_capability_is_immutable():
    registry = (
        build_default_capability_registry()
    )

    capability = registry.get(
        "azure.vm.start"
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        capability.capability_id = (
            "azure.vm.restart"
        )


def test_registry_rejects_non_capability_object():
    class FakeCapability:
        capability_id = (
            "azure.vm.start"
        )

        operation_domain = (
            "azure"
        )

        resource_type = (
            "Microsoft.Compute/"
            "virtualMachines"
        )

        operation_kind = (
            OperationKind.WRITE
        )

        operation_action = (
            OperationAction.VM_START
        )

    with pytest.raises(
        CapabilityRegistryError,
    ):
        CapabilityRegistry(
            capabilities=[
                FakeCapability(),
            ]
        )