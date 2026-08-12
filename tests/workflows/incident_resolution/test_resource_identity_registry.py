import pytest

from src.workflows.incident_resolution.azure_resource_identity import (
    AzureSubscriptionIdentityResolver,
    AzureVirtualMachineIdentityResolver,
)

from src.workflows.incident_resolution.resource_identity_registry import (
    DuplicateResourceIdentityResolverError,
    ResourceIdentityResolverNotFoundError,
    ResourceIdentityRegistry,
    build_default_resource_identity_registry,
)


AZURE_VM_RESOURCE_TYPE = (
    "Microsoft.Compute/"
    "virtualMachines"
)


def test_default_registry_contains_vm_identity_resolver():
    registry = (
        build_default_resource_identity_registry()
    )

    resolver = (
        registry.get_resolver(
            operation_domain="azure",
            resource_type=(
                AZURE_VM_RESOURCE_TYPE
            ),
        )
    )

    assert isinstance(
        resolver,
        AzureVirtualMachineIdentityResolver,
    )


def test_default_registry_contains_subscription_resolver():
    registry = (
        build_default_resource_identity_registry()
    )

    resolver = (
        registry.get_resolver(
            operation_domain="azure",
            resource_type="subscription",
        )
    )

    assert isinstance(
        resolver,
        AzureSubscriptionIdentityResolver,
    )


def test_default_registry_contains_only_current_identity_adapters():
    registry = (
        build_default_resource_identity_registry()
    )

    assert registry.count() == 2


def test_unknown_resource_type_fails_closed():
    registry = (
        build_default_resource_identity_registry()
    )

    with pytest.raises(
        ResourceIdentityResolverNotFoundError,
    ):
        registry.get_resolver(
            operation_domain="azure",
            resource_type=(
                "Microsoft.Storage/"
                "storageAccounts"
            ),
        )


def test_wrong_domain_fails_closed():
    registry = (
        build_default_resource_identity_registry()
    )

    with pytest.raises(
        ResourceIdentityResolverNotFoundError,
    ):
        registry.get_resolver(
            operation_domain="database",
            resource_type=(
                AZURE_VM_RESOURCE_TYPE
            ),
        )


def test_registry_does_not_normalize_domain():
    registry = (
        build_default_resource_identity_registry()
    )

    with pytest.raises(
        ResourceIdentityResolverNotFoundError,
    ):
        registry.get_resolver(
            operation_domain="Azure",
            resource_type=(
                AZURE_VM_RESOURCE_TYPE
            ),
        )


def test_registry_does_not_normalize_resource_type():
    registry = (
        build_default_resource_identity_registry()
    )

    with pytest.raises(
        ResourceIdentityResolverNotFoundError,
    ):
        registry.get_resolver(
            operation_domain="azure",
            resource_type=(
                "microsoft.compute/"
                "virtualmachines"
            ),
        )


def test_duplicate_resolver_registration_is_rejected():
    with pytest.raises(
        DuplicateResourceIdentityResolverError,
    ):
        ResourceIdentityRegistry(
            resolvers=[
                AzureVirtualMachineIdentityResolver(),
                AzureVirtualMachineIdentityResolver(),
            ]
        )