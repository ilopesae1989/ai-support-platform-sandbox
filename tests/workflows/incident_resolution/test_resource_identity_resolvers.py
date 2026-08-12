import pytest

from src.workflows.incident_resolution.azure_resource_identity import (
    AzureSubscriptionIdentityResolver,
    AzureVirtualMachineIdentityResolver,
)

from src.workflows.incident_resolution.operational_context import (
    OperationalContext,
)

from src.workflows.incident_resolution.resource_identity import (
    ResourceIdentityResolutionError,
)


SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-a9ae-e9e89b5ad172"
)

RESOURCE_GROUP = (
    "rg-icenter-sandbox-vm-demo"
)

VM_NAME = (
    "vm-icenter-sbx-demo-01"
)

VM_RESOURCE_ID = (
    "/subscriptions/"
    f"{SUBSCRIPTION_ID}"
    "/resourceGroups/"
    f"{RESOURCE_GROUP}"
    "/providers/Microsoft.Compute/"
    "virtualMachines/"
    f"{VM_NAME}"
)


def create_vm_context():
    return OperationalContext(
        alert_id="ALT-VM-001",

        affected_resource=(
            VM_NAME
        ),

        resource_type=(
            "Microsoft.Compute/"
            "virtualMachines"
        ),

        subscription_id=(
            SUBSCRIPTION_ID
        ),

        resource_group=(
            RESOURCE_GROUP
        ),

        vm_name=(
            VM_NAME
        ),

        correlation_id=(
            "corr-vm-001"
        ),
    )


def test_vm_resolver_has_generic_contract():
    resolver = (
        AzureVirtualMachineIdentityResolver()
    )

    assert (
        resolver.operation_domain
        == "azure"
    )

    assert (
        resolver.resource_type
        == (
            "Microsoft.Compute/"
            "virtualMachines"
        )
    )

    assert (
        resolver.required_parameters
        == (
            "subscription_id",
            "resource_group",
            "vm_name",
        )
    )


def test_vm_resolver_builds_authoritative_identity():
    resolver = (
        AzureVirtualMachineIdentityResolver()
    )

    identity = resolver.resolve(
        create_vm_context()
    )

    assert (
        identity.canonical_target_resource
        == VM_RESOURCE_ID
    )

    assert (
        identity.allowed_cognitive_targets
        == (
            VM_NAME,
            VM_RESOURCE_ID,
        )
    )


def test_vm_name_is_valid_cognitive_reference():
    resolver = (
        AzureVirtualMachineIdentityResolver()
    )

    identity = resolver.resolve(
        create_vm_context()
    )

    identity.validate_cognitive_target(
        VM_NAME
    )


def test_vm_arm_id_is_valid_cognitive_reference():
    resolver = (
        AzureVirtualMachineIdentityResolver()
    )

    identity = resolver.resolve(
        create_vm_context()
    )

    identity.validate_cognitive_target(
        VM_RESOURCE_ID
    )


def test_vm_resolver_rejects_other_target():
    resolver = (
        AzureVirtualMachineIdentityResolver()
    )

    identity = resolver.resolve(
        create_vm_context()
    )

    with pytest.raises(
        ResourceIdentityResolutionError,
        match="target_resource",
    ):
        identity.validate_cognitive_target(
            "vm-attacker-01"
        )


def test_vm_resolver_rejects_resource_mismatch():
    context = create_vm_context()

    context.affected_resource = (
        "vm-attacker-01"
    )

    with pytest.raises(
        ResourceIdentityResolutionError,
        match="affected_resource",
    ):
        (
            AzureVirtualMachineIdentityResolver()
            .resolve(
                context
            )
        )


def test_subscription_resolver_preserves_existing_semantics():
    context = OperationalContext(
        alert_id="ALT-SUB-001",

        affected_resource=(
            SUBSCRIPTION_ID
        ),

        resource_type=(
            "subscription"
        ),

        subscription_id=(
            SUBSCRIPTION_ID
        ),

        correlation_id=(
            "corr-sub-001"
        ),
    )

    identity = (
        AzureSubscriptionIdentityResolver()
        .resolve(
            context
        )
    )

    assert (
        identity.canonical_target_resource
        == "subscription"
    )

    assert (
        identity.allowed_cognitive_targets
        == (
            "subscription",
            SUBSCRIPTION_ID,
        )
    )


def test_subscription_resolver_rejects_different_target():
    context = OperationalContext(
        alert_id="ALT-SUB-001",

        resource_type="subscription",

        subscription_id=(
            SUBSCRIPTION_ID
        ),
    )

    identity = (
        AzureSubscriptionIdentityResolver()
        .resolve(
            context
        )
    )

    with pytest.raises(
        ResourceIdentityResolutionError,
        match="target_resource",
    ):
        identity.validate_cognitive_target(
            "another-subscription"
        )