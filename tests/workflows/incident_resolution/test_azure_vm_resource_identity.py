import pytest

from src.workflows.incident_resolution.azure_resource_identity import (
    AzureResourceIdentityError,
    build_azure_vm_resource_id,
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

EXPECTED_RESOURCE_ID = (
    "/subscriptions/"
    f"{SUBSCRIPTION_ID}"
    "/resourceGroups/"
    f"{RESOURCE_GROUP}"
    "/providers/Microsoft.Compute/"
    "virtualMachines/"
    f"{VM_NAME}"
)


def test_builds_exact_vm_resource_id():
    resource_id = (
        build_azure_vm_resource_id(
            subscription_id=SUBSCRIPTION_ID,
            resource_group=RESOURCE_GROUP,
            vm_name=VM_NAME,
        )
    )

    assert (
        resource_id
        == EXPECTED_RESOURCE_ID
    )


def test_vm_resource_id_is_deterministic():
    first = (
        build_azure_vm_resource_id(
            subscription_id=SUBSCRIPTION_ID,
            resource_group=RESOURCE_GROUP,
            vm_name=VM_NAME,
        )
    )

    second = (
        build_azure_vm_resource_id(
            subscription_id=SUBSCRIPTION_ID,
            resource_group=RESOURCE_GROUP,
            vm_name=VM_NAME,
        )
    )

    assert first == second


@pytest.mark.parametrize(
    "field_name",
    [
        "subscription_id",
        "resource_group",
        "vm_name",
    ],
)
def test_rejects_empty_identity_segment(
    field_name,
):
    values = {
        "subscription_id":
            SUBSCRIPTION_ID,

        "resource_group":
            RESOURCE_GROUP,

        "vm_name":
            VM_NAME,
    }

    values[field_name] = ""

    with pytest.raises(
        AzureResourceIdentityError,
    ):
        build_azure_vm_resource_id(
            **values
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "subscription_id",
        "resource_group",
        "vm_name",
    ],
)
def test_rejects_surrounding_whitespace(
    field_name,
):
    values = {
        "subscription_id":
            SUBSCRIPTION_ID,

        "resource_group":
            RESOURCE_GROUP,

        "vm_name":
            VM_NAME,
    }

    values[field_name] = (
        " " + values[field_name]
    )

    with pytest.raises(
        AzureResourceIdentityError,
    ):
        build_azure_vm_resource_id(
            **values
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "subscription_id",
        "resource_group",
        "vm_name",
    ],
)
@pytest.mark.parametrize(
    "separator",
    [
        "/",
        "\\",
    ],
)
def test_rejects_path_injection(
    field_name,
    separator,
):
    values = {
        "subscription_id":
            SUBSCRIPTION_ID,

        "resource_group":
            RESOURCE_GROUP,

        "vm_name":
            VM_NAME,
    }

    values[field_name] = (
        values[field_name]
        + separator
        + "attacker"
    )

    with pytest.raises(
        AzureResourceIdentityError,
    ):
        build_azure_vm_resource_id(
            **values
        )


def test_does_not_normalize_vm_name():
    mixed_case_name = (
        "VM-iCenter-SBX-Demo-01"
    )

    resource_id = (
        build_azure_vm_resource_id(
            subscription_id=SUBSCRIPTION_ID,
            resource_group=RESOURCE_GROUP,
            vm_name=mixed_case_name,
        )
    )

    assert resource_id.endswith(
        "/virtualMachines/"
        + mixed_case_name
    )