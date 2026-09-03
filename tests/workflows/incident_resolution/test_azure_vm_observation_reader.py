from __future__ import annotations

import importlib
import inspect
import textwrap

import pytest

from src.workflows.incident_resolution.azure_vm_observation_settings import (
    AzureVmObservationManagedIdentitySettings,
)


TARGET_MODULE = (
    "src.workflows.incident_resolution."
    "azure_vm_observation_reader"
)


USER_ASSIGNED_CLIENT_ID = (
    "a3333333-3333-4333-8333-333333333333"
)


def _module():
    return importlib.import_module(
        TARGET_MODULE
    )


def test_reader_factory_has_exact_surface():
    module = _module()

    factory = getattr(
        module,
        "build_azure_vm_observation_reader",
        None,
    )

    assert callable(
        factory
    )

    signature = inspect.signature(
        factory
    )

    assert tuple(
        signature.parameters
    ) == (
        "settings",
    )


def test_reader_factory_rejects_wrong_settings_type():
    module = _module()

    for invalid_settings in (
        None,
        object(),
        {},
        "system",
    ):
        with pytest.raises(
            TypeError
        ):
            module.build_azure_vm_observation_reader(
                invalid_settings
            )


def test_system_assigned_composes_credential_then_reader(
    monkeypatch,
):
    module = _module()

    credential = object()
    reader = object()

    credential_calls = []
    reader_calls = []

    def fake_credential_factory(
        settings,
    ):
        credential_calls.append(
            settings
        )

        return credential

    def fake_reader(
        *,
        credential,
    ):
        reader_calls.append(
            credential
        )

        return reader

    monkeypatch.setattr(
        module,
        "build_azure_vm_observation_credential",
        fake_credential_factory,
    )

    monkeypatch.setattr(
        module,
        "AzureSdkVmPowerStateReader",
        fake_reader,
    )

    settings = (
        AzureVmObservationManagedIdentitySettings()
    )

    actual = (
        module
        .build_azure_vm_observation_reader(
            settings
        )
    )

    assert actual is reader

    assert credential_calls == [
        settings,
    ]

    assert reader_calls == [
        credential,
    ]


def test_user_assigned_settings_are_preserved_exactly(
    monkeypatch,
):
    module = _module()

    credential = object()
    reader = object()

    credential_calls = []
    reader_calls = []

    def fake_credential_factory(
        settings,
    ):
        credential_calls.append(
            settings
        )

        return credential

    def fake_reader(
        *,
        credential,
    ):
        reader_calls.append(
            credential
        )

        return reader

    monkeypatch.setattr(
        module,
        "build_azure_vm_observation_credential",
        fake_credential_factory,
    )

    monkeypatch.setattr(
        module,
        "AzureSdkVmPowerStateReader",
        fake_reader,
    )

    settings = (
        AzureVmObservationManagedIdentitySettings(
            managed_identity_client_id=(
                USER_ASSIGNED_CLIENT_ID
            )
        )
    )

    actual = (
        module
        .build_azure_vm_observation_reader(
            settings
        )
    )

    assert actual is reader

    assert credential_calls == [
        settings,
    ]

    assert (
        credential_calls[0]
        .managed_identity_client_id
        == USER_ASSIGNED_CLIENT_ID
    )

    assert reader_calls == [
        credential,
    ]


def test_composition_does_not_request_token_or_read_power_state(
    monkeypatch,
):
    module = _module()

    class FakeCredential:
        def get_token(
            self,
            *args,
            **kwargs,
        ):
            raise AssertionError(
                "get_token no debe ejecutarse "
                "durante reader composition."
            )

    class FakeReader:
        def __init__(
            self,
            *,
            credential,
        ):
            self.credential = credential

        def read_power_state(
            self,
            *,
            subscription_id,
            resource_group,
            vm_name,
        ):
            raise AssertionError(
                "read_power_state no debe ejecutarse "
                "durante reader composition."
            )

    credential = FakeCredential()

    monkeypatch.setattr(
        module,
        "build_azure_vm_observation_credential",
        lambda settings: credential,
    )

    monkeypatch.setattr(
        module,
        "AzureSdkVmPowerStateReader",
        FakeReader,
    )

    reader = (
        module
        .build_azure_vm_observation_reader(
            AzureVmObservationManagedIdentitySettings()
        )
    )

    assert isinstance(
        reader,
        FakeReader,
    )

    assert reader.credential is credential


def test_reader_composition_has_no_hidden_runtime_or_environment_authority():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.lower()

    required = (
        "build_azure_vm_observation_credential",
        "azuresdkvmpowerstatereader",
        "azurevmobservationmanagedidentitysettings",
    )

    for fragment in required:
        assert fragment in lowered

    forbidden = (
        "os.getenv",
        "os.environ",
        "from_environment",
        "managedidentitycredential(",
        "defaultazurecredential",
        "azureclicredential",
        "environmentcredential",
        "clientsecretcredential",
        "get_token(",
        "computemanagementclient",
        "read_power_state(",
        "virtual_machines",
        "instance_view(",
        "asyncio.run",
        ".start(",
        ".run(",
        "client_secret",
        "mssql_python",
        "sqlite",
        "cosmos",
        "servicebus",
        "foundry",
        "mcp",
    )

    for fragment in forbidden:
        assert fragment not in lowered
