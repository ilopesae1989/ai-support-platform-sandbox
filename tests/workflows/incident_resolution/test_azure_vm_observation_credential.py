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
    "azure_vm_observation_credential"
)


USER_ASSIGNED_CLIENT_ID = (
    "a3333333-3333-4333-8333-333333333333"
)


def _module():
    return importlib.import_module(
        TARGET_MODULE
    )


def test_credential_factory_has_exact_surface():
    module = _module()

    factory = getattr(
        module,
        "build_azure_vm_observation_credential",
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


def test_credential_factory_rejects_wrong_settings_type():
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
            module.build_azure_vm_observation_credential(
                invalid_settings
            )


def test_system_assigned_constructs_managed_identity_without_client_id(
    monkeypatch,
):
    module = _module()

    calls = []

    sentinel = object()

    def fake_credential(
        **kwargs,
    ):
        calls.append(
            kwargs
        )
        return sentinel

    monkeypatch.setattr(
        module,
        "ManagedIdentityCredential",
        fake_credential,
    )

    settings = (
        AzureVmObservationManagedIdentitySettings()
    )

    credential = (
        module
        .build_azure_vm_observation_credential(
            settings
        )
    )

    assert credential is sentinel

    assert calls == [
        {},
    ]


def test_user_assigned_constructs_managed_identity_with_exact_client_id(
    monkeypatch,
):
    module = _module()

    calls = []

    sentinel = object()

    def fake_credential(
        **kwargs,
    ):
        calls.append(
            kwargs
        )
        return sentinel

    monkeypatch.setattr(
        module,
        "ManagedIdentityCredential",
        fake_credential,
    )

    settings = (
        AzureVmObservationManagedIdentitySettings(
            managed_identity_client_id=(
                USER_ASSIGNED_CLIENT_ID
            )
        )
    )

    credential = (
        module
        .build_azure_vm_observation_credential(
            settings
        )
    )

    assert credential is sentinel

    assert calls == [
        {
            "client_id": (
                USER_ASSIGNED_CLIENT_ID
            )
        }
    ]


def test_factory_does_not_request_token_during_construction(
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
                "durante credential composition."
            )

    constructor_calls = []

    def fake_credential(
        **kwargs,
    ):
        constructor_calls.append(
            kwargs
        )
        return FakeCredential()

    monkeypatch.setattr(
        module,
        "ManagedIdentityCredential",
        fake_credential,
    )

    credential = (
        module
        .build_azure_vm_observation_credential(
            AzureVmObservationManagedIdentitySettings()
        )
    )

    assert isinstance(
        credential,
        FakeCredential,
    )

    assert constructor_calls == [
        {},
    ]


def test_factory_does_not_construct_reader_or_compute_runtime():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.lower()

    forbidden = (
        "azuresdkvmpowerstatereader",
        "computemanagementclient",
        "read_power_state(",
        "virtual_machines",
        "instance_view(",
    )

    for fragment in forbidden:
        assert fragment not in lowered


def test_factory_has_no_environment_fallback_or_secret_authority():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.lower()

    required = (
        "managedidentitycredential",
        "azurevmobservationmanagedidentitysettings",
    )

    for fragment in required:
        assert fragment in lowered

    forbidden = (
        "os.getenv",
        "os.environ",
        "from_environment",
        "defaultazurecredential",
        "azureclicredential",
        "environmentcredential",
        "clientsecretcredential",
        "client_secret",
        "get_token(",
        "asyncio.run",
        ".start(",
        ".run(",
        "mssql_python",
        "sqlite",
        "cosmos",
        "servicebus",
        "foundry",
        "mcp",
    )

    for fragment in forbidden:
        assert fragment not in lowered
