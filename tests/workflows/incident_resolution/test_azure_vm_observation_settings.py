from __future__ import annotations

import importlib
import inspect
import textwrap

from dataclasses import fields

import pytest


TARGET_MODULE = (
    "src.workflows.incident_resolution."
    "azure_vm_observation_settings"
)


USER_ASSIGNED_CLIENT_ID = (
    "a3333333-3333-4333-8333-333333333333"
)


def _module():
    return importlib.import_module(
        TARGET_MODULE
    )


def _base_environment():
    return {}


def test_settings_contract_has_exact_surface():
    module = _module()

    settings_type = getattr(
        module,
        "AzureVmObservationManagedIdentitySettings",
        None,
    )

    builder = getattr(
        module,
        "build_azure_vm_observation_settings",
        None,
    )

    assert settings_type is not None

    assert tuple(
        field.name
        for field in fields(
            settings_type
        )
    ) == (
        "managed_identity_client_id",
    )

    assert callable(
        builder
    )

    signature = inspect.signature(
        builder
    )

    assert tuple(
        signature.parameters
    ) == (
        "environment",
    )


def test_absent_identity_means_system_assigned():
    module = _module()

    settings = (
        module
        .build_azure_vm_observation_settings(
            _base_environment()
        )
    )

    assert (
        settings.managed_identity_client_id
        is None
    )


def test_canonical_user_assigned_client_id_is_accepted():
    module = _module()

    environment = {
        "AZURE_VM_READER_MANAGED_IDENTITY_CLIENT_ID": (
            USER_ASSIGNED_CLIENT_ID
        )
    }

    settings = (
        module
        .build_azure_vm_observation_settings(
            environment
        )
    )

    assert (
        settings.managed_identity_client_id
        == USER_ASSIGNED_CLIENT_ID
    )


def test_invalid_user_assigned_identity_values_fail_closed():
    module = _module()

    invalid_values = (
        "",
        " ",
        "system",
        " System ",
        "not-a-client-id",
        (
            "33333333-3333-4333-8333-"
            "33333333333Z"
        ),
        (
            "33333333-3333-4333-8333-"
            "333333333333 "
        ),
        (
            "a3333333-3333-4333-8333-"
            "333333333333".upper()
        ),
    )

    for invalid_value in invalid_values:
        environment = {
            "AZURE_VM_READER_MANAGED_IDENTITY_CLIENT_ID": (
                invalid_value
            )
        }

        with pytest.raises(
            ValueError
        ):
            module.build_azure_vm_observation_settings(
                environment
            )


def test_unstructured_environment_is_rejected():
    module = _module()

    for invalid_environment in (
        None,
        object(),
        [],
        "KEY=value",
    ):
        with pytest.raises(
            TypeError
        ):
            module.build_azure_vm_observation_settings(
                invalid_environment
            )


def test_environment_mapping_is_not_mutated():
    module = _module()

    environment = {
        "AZURE_VM_READER_MANAGED_IDENTITY_CLIENT_ID": (
            USER_ASSIGNED_CLIENT_ID
        ),
        "UNRELATED": "unchanged",
    }

    before = dict(
        environment
    )

    module.build_azure_vm_observation_settings(
        environment
    )

    assert environment == before


def test_teams_and_sql_identity_values_have_no_authority():
    module = _module()

    environment = {
        "MANAGED_IDENTITY_CLIENT_ID": (
            "11111111-1111-4111-8111-111111111111"
        ),
        "AZURE_SQL_MANAGED_IDENTITY_CLIENT_ID": (
            "22222222-2222-4222-8222-222222222222"
        ),
    }

    settings = (
        module
        .build_azure_vm_observation_settings(
            environment
        )
    )

    assert (
        settings.managed_identity_client_id
        is None
    )


def test_settings_boundary_has_no_hidden_runtime_or_credential_authority():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.lower()

    forbidden_fragments = (
        "os.getenv",
        "os.environ",
        "from_environment",
        "managedidentitycredential",
        "defaultazurecredential",
        "azureclicredential",
        "azure.identity",
        "computemanagementclient",
        "azuresdkvmpowerstatereader",
        "read_power_state(",
        "get_token(",
        ".start(",
        ".run(",
        "asyncio.run",
        "mssql_python",
        "client_secret",
        "sqlite",
        "cosmos",
        "servicebus",
        "foundry",
        "mcp",
    )

    for fragment in forbidden_fragments:
        assert fragment not in lowered
