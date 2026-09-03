from __future__ import annotations

import importlib
import inspect
import textwrap

import pytest

from src.channels.teams.bootstrap import (
    TeamsManagedIdentityAppSettings,
)

from src.channels.teams.production_settings import (
    TeamsProductionHostSettings,
)

from src.persistence.azure_sql.connection_provider import (
    AzureSqlManagedIdentitySettings,
)

from src.workflows.incident_resolution.azure_vm_observation_settings import (
    AzureVmObservationManagedIdentitySettings,
)


TARGET_MODULE = (
    "src.channels.teams.production_composition"
)


TEAMS_USER_ASSIGNED_CLIENT_ID = (
    "11111111-1111-4111-8111-111111111111"
)

SQL_USER_ASSIGNED_CLIENT_ID = (
    "22222222-2222-4222-8222-222222222222"
)

VM_USER_ASSIGNED_CLIENT_ID = (
    "a3333333-3333-4333-8333-333333333333"
)


def _module():
    return importlib.import_module(
        TARGET_MODULE
    )


def _environment():
    return {
        "CLIENT_ID": (
            "teams-app-client-id"
        ),
        "MANAGED_IDENTITY_CLIENT_ID": (
            "system"
        ),
        "TENANT_ID": (
            "bot-tenant-id"
        ),
        "TEAMS_CHANNEL_TENANT_ID": (
            "channel-tenant-id"
        ),
        "TEAMS_HITL_APPROVER_AAD_OBJECT_ID": (
            "approver-object-id"
        ),
        "AZURE_SQL_SERVER": (
            "ai-support-platform-sbx"
            ".database.windows.net"
        ),
        "AZURE_SQL_DATABASE": (
            "ai_support_platform_sbx"
        ),
    }


def _host_settings():
    return TeamsProductionHostSettings(
        app_settings=(
            TeamsManagedIdentityAppSettings(
                client_id=(
                    "teams-app-client-id"
                ),
                managed_identity_client_id=(
                    "system"
                ),
                bot_tenant_id=(
                    "bot-tenant-id"
                ),
                teams_channel_tenant_id=(
                    "channel-tenant-id"
                ),
                approver_aad_object_id=(
                    "approver-object-id"
                ),
            )
        ),
        azure_sql_settings=(
            AzureSqlManagedIdentitySettings(
                server=(
                    "ai-support-platform-sbx"
                    ".database.windows.net"
                ),
                database=(
                    "ai_support_platform_sbx"
                ),
            )
        ),
    )


def test_production_composition_has_exact_surface():
    module = _module()

    factory = getattr(
        module,
        "build_production_teams_host",
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
        "environment",
    )


def test_production_composition_rejects_unstructured_environment():
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
            module.build_production_teams_host(
                invalid_environment
            )


def test_composition_delegates_exact_boundaries(
    monkeypatch,
):
    module = _module()

    environment = (
        _environment()
    )

    host_settings = (
        _host_settings()
    )

    observation_settings = (
        AzureVmObservationManagedIdentitySettings()
    )

    reader = object()
    bootstrap = object()

    calls = []

    def fake_host_settings_builder(
        actual_environment,
    ):
        calls.append(
            (
                "host_settings",
                actual_environment,
            )
        )

        return host_settings

    def fake_observation_settings_builder(
        actual_environment,
    ):
        calls.append(
            (
                "observation_settings",
                actual_environment,
            )
        )

        return observation_settings

    def fake_reader_builder(
        actual_settings,
    ):
        calls.append(
            (
                "reader",
                actual_settings,
            )
        )

        return reader

    def fake_bootstrap_builder(
        app_settings,
        azure_sql_settings,
        *,
        azure_vm_power_state_reader,
    ):
        calls.append(
            (
                "bootstrap",
                app_settings,
                azure_sql_settings,
                azure_vm_power_state_reader,
            )
        )

        return bootstrap

    monkeypatch.setattr(
        module,
        "build_production_teams_host_settings",
        fake_host_settings_builder,
    )

    monkeypatch.setattr(
        module,
        "build_azure_vm_observation_settings",
        fake_observation_settings_builder,
    )

    monkeypatch.setattr(
        module,
        "build_azure_vm_observation_reader",
        fake_reader_builder,
    )

    monkeypatch.setattr(
        module,
        "build_production_teams_hitl_app",
        fake_bootstrap_builder,
    )

    actual = (
        module
        .build_production_teams_host(
            environment
        )
    )

    assert actual is bootstrap

    assert calls == [
        (
            "host_settings",
            environment,
        ),
        (
            "observation_settings",
            environment,
        ),
        (
            "reader",
            observation_settings,
        ),
        (
            "bootstrap",
            host_settings.app_settings,
            host_settings.azure_sql_settings,
            reader,
        ),
    ]


def test_three_managed_identity_boundaries_remain_independent(
    monkeypatch,
):
    module = _module()

    environment = (
        _environment()
    )

    environment[
        "MANAGED_IDENTITY_CLIENT_ID"
    ] = (
        TEAMS_USER_ASSIGNED_CLIENT_ID
    )

    environment[
        "AZURE_SQL_MANAGED_IDENTITY_CLIENT_ID"
    ] = (
        SQL_USER_ASSIGNED_CLIENT_ID
    )

    environment[
        "AZURE_VM_READER_MANAGED_IDENTITY_CLIENT_ID"
    ] = (
        VM_USER_ASSIGNED_CLIENT_ID
    )

    captured = {}

    reader = object()
    bootstrap = object()

    def fake_reader_builder(
        settings,
    ):
        captured[
            "vm_identity"
        ] = (
            settings
            .managed_identity_client_id
        )

        return reader

    def fake_bootstrap_builder(
        app_settings,
        azure_sql_settings,
        *,
        azure_vm_power_state_reader,
    ):
        captured[
            "teams_identity"
        ] = (
            app_settings
            .managed_identity_client_id
        )

        captured[
            "sql_identity"
        ] = (
            azure_sql_settings
            .managed_identity_client_id
        )

        captured[
            "reader"
        ] = (
            azure_vm_power_state_reader
        )

        return bootstrap

    monkeypatch.setattr(
        module,
        "build_azure_vm_observation_reader",
        fake_reader_builder,
    )

    monkeypatch.setattr(
        module,
        "build_production_teams_hitl_app",
        fake_bootstrap_builder,
    )

    actual = (
        module
        .build_production_teams_host(
            environment
        )
    )

    assert actual is bootstrap

    assert captured == {
        "teams_identity": (
            TEAMS_USER_ASSIGNED_CLIENT_ID
        ),
        "sql_identity": (
            SQL_USER_ASSIGNED_CLIENT_ID
        ),
        "vm_identity": (
            VM_USER_ASSIGNED_CLIENT_ID
        ),
        "reader": reader,
    }


def test_environment_mapping_is_not_mutated(
    monkeypatch,
):
    module = _module()

    environment = (
        _environment()
    )

    before = dict(
        environment
    )

    monkeypatch.setattr(
        module,
        "build_production_teams_hitl_app",
        lambda *args, **kwargs: object(),
    )

    monkeypatch.setattr(
        module,
        "build_azure_vm_observation_reader",
        lambda settings: object(),
    )

    module.build_production_teams_host(
        environment
    )

    assert environment == before


def test_client_secret_policy_is_preserved_end_to_end():
    module = _module()

    environment = (
        _environment()
    )

    environment[
        "CLIENT_SECRET"
    ] = "forbidden"

    with pytest.raises(
        ValueError
    ):
        module.build_production_teams_host(
            environment
        )


def test_composition_has_no_hidden_runtime_or_direct_resource_authority():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.lower()

    required = (
        "build_production_teams_host_settings",
        "build_azure_vm_observation_settings",
        "build_azure_vm_observation_reader",
        "build_production_teams_hitl_app",
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
        "build_azure_vm_observation_credential",
        "azuresdkvmpowerstatereader(",
        "get_token(",
        "read_power_state(",
        "computemanagementclient",
        "virtual_machines",
        "instance_view(",
        "build_azure_sql_teams_hitl_persistence",
        "build_teams_hitl_app",
        "mssql_python.connect",
        "asyncio.run",
        ".start(",
        ".run(",
        "client_secret",
        "sqlite",
        "cosmos",
        "servicebus",
        "foundry",
        "mcp",
    )

    for fragment in forbidden:
        assert fragment not in lowered
