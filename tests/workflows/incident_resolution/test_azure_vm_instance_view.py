from __future__ import annotations

from types import (
    SimpleNamespace,
)

import pytest

import src.workflows.incident_resolution.azure_vm_instance_view as module


SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-a9ae-e9e89b5ad172"
)

RESOURCE_GROUP = (
    "rg-icenter-sandbox-vm-demo"
)

VM_NAME = (
    "vm-icenter-sbx-demo-01"
)


class FakeCredential:
    def get_token(
        self,
        *scopes,
        **kwargs,
    ):
        raise AssertionError(
            "Unit test must never request a token."
        )


class FakeVirtualMachinesOperations:
    def __init__(
        self,
        *,
        statuses,
        calls,
    ):
        self._statuses = statuses
        self._calls = calls

    def instance_view(
        self,
        *,
        resource_group_name,
        vm_name,
    ):
        self._calls.append(
            (
                "instance_view",
                resource_group_name,
                vm_name,
            )
        )

        return SimpleNamespace(
            statuses=self._statuses
        )


class FakeComputeClient:
    def __init__(
        self,
        *,
        statuses,
        calls,
    ):
        self.virtual_machines = (
            FakeVirtualMachinesOperations(
                statuses=statuses,
                calls=calls,
            )
        )

        self._calls = calls

    def close(
        self,
    ):
        self._calls.append(
            (
                "close",
            )
        )


def install_fake_client(
    monkeypatch,
    *,
    statuses,
):
    calls = []

    def factory(
        *,
        credential,
        subscription_id,
    ):
        assert isinstance(
            credential,
            FakeCredential,
        )

        calls.append(
            (
                "client",
                subscription_id,
            )
        )

        return FakeComputeClient(
            statuses=statuses,
            calls=calls,
        )

    monkeypatch.setattr(
        module,
        "ComputeManagementClient",
        factory,
    )

    return calls


def test_reader_uses_only_exact_instance_view(
    monkeypatch,
):
    calls = install_fake_client(
        monkeypatch,
        statuses=[
            SimpleNamespace(
                code=(
                    "ProvisioningState/"
                    "succeeded"
                )
            ),
            SimpleNamespace(
                code="PowerState/running"
            ),
        ],
    )

    reader = (
        module
        .AzureSdkVmPowerStateReader(
            credential=FakeCredential()
        )
    )

    result = (
        reader.read_power_state(
            subscription_id=(
                SUBSCRIPTION_ID
            ),
            resource_group=(
                RESOURCE_GROUP
            ),
            vm_name=VM_NAME,
        )
    )

    assert result == "PowerState/running"

    assert calls == [
        (
            "client",
            SUBSCRIPTION_ID,
        ),
        (
            "instance_view",
            RESOURCE_GROUP,
            VM_NAME,
        ),
        (
            "close",
        ),
    ]


@pytest.mark.parametrize(
    (
        "field_name",
        "value",
    ),
    [
        (
            "subscription_id",
            "",
        ),
        (
            "subscription_id",
            " bad ",
        ),
        (
            "resource_group",
            "",
        ),
        (
            "resource_group",
            " bad ",
        ),
        (
            "vm_name",
            "",
        ),
        (
            "vm_name",
            " bad ",
        ),
    ],
)
def test_reader_rejects_non_exact_identity_before_client_creation(
    monkeypatch,
    field_name,
    value,
):
    created = []

    def forbidden_client(
        **kwargs,
    ):
        created.append(
            kwargs
        )

        raise AssertionError(
            "Client must not be created."
        )

    monkeypatch.setattr(
        module,
        "ComputeManagementClient",
        forbidden_client,
    )

    reader = (
        module
        .AzureSdkVmPowerStateReader(
            credential=FakeCredential()
        )
    )

    values = {
        "subscription_id":
            SUBSCRIPTION_ID,
        "resource_group":
            RESOURCE_GROUP,
        "vm_name":
            VM_NAME,
    }

    values[
        field_name
    ] = value

    with pytest.raises(
        ValueError,
    ):
        reader.read_power_state(
            **values
        )

    assert created == []


def test_reader_fails_closed_without_power_state(
    monkeypatch,
):
    calls = install_fake_client(
        monkeypatch,
        statuses=[
            SimpleNamespace(
                code=(
                    "ProvisioningState/"
                    "succeeded"
                )
            ),
        ],
    )

    reader = (
        module
        .AzureSdkVmPowerStateReader(
            credential=FakeCredential()
        )
    )

    with pytest.raises(
        module.AzureVmInstanceViewError,
        match="exactamente un PowerState",
    ):
        reader.read_power_state(
            subscription_id=(
                SUBSCRIPTION_ID
            ),
            resource_group=(
                RESOURCE_GROUP
            ),
            vm_name=VM_NAME,
        )

    assert calls[-1] == (
        "close",
    )


def test_reader_fails_closed_with_multiple_power_states(
    monkeypatch,
):
    calls = install_fake_client(
        monkeypatch,
        statuses=[
            {
                "code":
                    "PowerState/starting",
            },
            {
                "code":
                    "PowerState/running",
            },
        ],
    )

    reader = (
        module
        .AzureSdkVmPowerStateReader(
            credential=FakeCredential()
        )
    )

    with pytest.raises(
        module.AzureVmInstanceViewError,
        match="Encontrados=2",
    ):
        reader.read_power_state(
            subscription_id=(
                SUBSCRIPTION_ID
            ),
            resource_group=(
                RESOURCE_GROUP
            ),
            vm_name=VM_NAME,
        )

    assert calls[-1] == (
        "close",
    )


def test_reader_requires_injected_token_credential():
    with pytest.raises(
        TypeError,
        match="TokenCredential",
    ):
        module.AzureSdkVmPowerStateReader(
            credential=object()
        )


def test_reader_source_contains_no_write_api_surface():
    source = (
        module
        .__file__
    )

    text = open(
        source,
        encoding="utf-8",
    ).read()

    forbidden = {
        ".begin_start(",
        ".begin_restart(",
        ".begin_power_off(",
        ".begin_deallocate(",
        ".begin_delete(",
        ".begin_create_or_update(",
        ".begin_update(",
    }

    for token in forbidden:
        assert token not in text

    assert ".instance_view(" in text
