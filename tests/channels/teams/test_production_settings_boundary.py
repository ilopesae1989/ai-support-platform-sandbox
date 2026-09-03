from __future__ import annotations

import importlib
import inspect
import textwrap

from dataclasses import fields

import pytest

from src.channels.teams.bootstrap import (
    TeamsManagedIdentityAppSettings,
)

from src.persistence.azure_sql.connection_provider import (
    AzureSqlManagedIdentitySettings,
)


TARGET_MODULE = (
    "src.channels.teams.production_settings"
)


TEAMS_USER_ASSIGNED_CLIENT_ID = (
    "11111111-1111-4111-8111-111111111111"
)

SQL_USER_ASSIGNED_CLIENT_ID = (
    "22222222-2222-4222-8222-222222222222"
)


REQUIRED_ENVIRONMENT_NAMES = (
    "CLIENT_ID",
    "MANAGED_IDENTITY_CLIENT_ID",
    "TENANT_ID",
    "TEAMS_CHANNEL_TENANT_ID",
    "TEAMS_HITL_APPROVER_AAD_OBJECT_ID",
    "AZURE_SQL_SERVER",
    "AZURE_SQL_DATABASE",
)


LOCAL_PERSISTENCE_NAMES = (
    "TEAMS_HITL_PENDING_DB",
    "TEAMS_HITL_CHECKPOINT_DIR",
    "TEAMS_OPERATION_DISPATCH_DB",
    "TEAMS_CONVERSATION_BINDING_DB",
)


def _module():
    return importlib.import_module(
        TARGET_MODULE
    )


def _base_environment():
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


def test_production_host_settings_contract_has_exact_surface():
    module = _module()

    settings_type = getattr(
        module,
        "TeamsProductionHostSettings",
        None,
    )

    builder = getattr(
        module,
        "build_production_teams_host_settings",
        None,
    )

    assert settings_type is not None

    assert tuple(
        field.name
        for field in fields(
            settings_type
        )
    ) == (
        "app_settings",
        "azure_sql_settings",
    )

    assert callable(
        builder
    )

    signature = inspect.signature(
        builder
    )

    assert (
        tuple(
            signature.parameters
        )
        == (
            "environment",
        )
    )


def test_system_assigned_host_settings_are_structured_without_secrets():
    module = _module()

    settings = (
        module
        .build_production_teams_host_settings(
            _base_environment()
        )
    )

    assert isinstance(
        settings.app_settings,
        TeamsManagedIdentityAppSettings,
    )

    assert (
        settings.app_settings.client_id
        == "teams-app-client-id"
    )

    assert (
        settings
        .app_settings
        .managed_identity_client_id
        == "system"
    )

    assert (
        settings.app_settings.bot_tenant_id
        == "bot-tenant-id"
    )

    assert (
        settings
        .app_settings
        .teams_channel_tenant_id
        == "channel-tenant-id"
    )

    assert (
        settings
        .app_settings
        .approver_aad_object_id
        == "approver-object-id"
    )

    assert (
        settings.app_settings.messaging_endpoint
        == "/api/messages"
    )

    assert isinstance(
        settings.azure_sql_settings,
        AzureSqlManagedIdentitySettings,
    )

    assert (
        settings.azure_sql_settings.server
        == (
            "ai-support-platform-sbx"
            ".database.windows.net"
        )
    )

    assert (
        settings.azure_sql_settings.database
        == "ai_support_platform_sbx"
    )

    assert (
        settings
        .azure_sql_settings
        .managed_identity_client_id
        is None
    )

    assert not hasattr(
        settings.app_settings,
        "client_secret",
    )


def test_user_assigned_teams_and_sql_identities_are_independent():
    module = _module()

    environment = (
        _base_environment()
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

    settings = (
        module
        .build_production_teams_host_settings(
            environment
        )
    )

    assert (
        settings
        .app_settings
        .managed_identity_client_id
        == TEAMS_USER_ASSIGNED_CLIENT_ID
    )

    assert (
        settings
        .azure_sql_settings
        .managed_identity_client_id
        == SQL_USER_ASSIGNED_CLIENT_ID
    )


def test_client_secret_is_forbidden_even_when_empty():
    module = _module()

    for secret_value in (
        "",
        "forbidden-secret",
    ):
        environment = (
            _base_environment()
        )

        environment[
            "CLIENT_SECRET"
        ] = secret_value

        with pytest.raises(
            module
            .TeamsProductionHostConfigurationError
        ):
            module.build_production_teams_host_settings(
                environment
            )


def test_missing_required_environment_values_fail_closed():
    module = _module()

    for missing_name in (
        REQUIRED_ENVIRONMENT_NAMES
    ):
        environment = (
            _base_environment()
        )

        environment.pop(
            missing_name
        )

        with pytest.raises(
            module
            .TeamsProductionHostConfigurationError
        ):
            module.build_production_teams_host_settings(
                environment
            )


def test_unstructured_environment_is_rejected():
    module = _module()

    for invalid_environment in (
        None,
        object(),
        [],
        "CLIENT_ID=value",
    ):
        with pytest.raises(
            TypeError
        ):
            module.build_production_teams_host_settings(
                invalid_environment
            )


def test_local_persistence_environment_values_have_no_authority():
    module = _module()

    baseline = (
        module
        .build_production_teams_host_settings(
            _base_environment()
        )
    )

    environment = (
        _base_environment()
    )

    for name in (
        LOCAL_PERSISTENCE_NAMES
    ):
        environment[name] = (
            "C:/forbidden/local/path"
        )

    with_local_values = (
        module
        .build_production_teams_host_settings(
            environment
        )
    )

    assert (
        with_local_values
        == baseline
    )


def test_invalid_structured_values_fail_closed():
    module = _module()

    invalid_environments = []

    invalid_teams_identity = (
        _base_environment()
    )

    invalid_teams_identity[
        "MANAGED_IDENTITY_CLIENT_ID"
    ] = "not-a-client-id"

    invalid_environments.append(
        invalid_teams_identity
    )

    invalid_sql_server = (
        _base_environment()
    )

    invalid_sql_server[
        "AZURE_SQL_SERVER"
    ] = "localhost"

    invalid_environments.append(
        invalid_sql_server
    )

    invalid_sql_identity = (
        _base_environment()
    )

    invalid_sql_identity[
        "AZURE_SQL_MANAGED_IDENTITY_CLIENT_ID"
    ] = "not-a-client-id"

    invalid_environments.append(
        invalid_sql_identity
    )

    for environment in (
        invalid_environments
    ):
        with pytest.raises(
            ValueError
        ):
            module.build_production_teams_host_settings(
                environment
            )


def test_environment_mapping_is_not_mutated():
    module = _module()

    environment = (
        _base_environment()
    )

    environment[
        "AZURE_SQL_MANAGED_IDENTITY_CLIENT_ID"
    ] = (
        SQL_USER_ASSIGNED_CLIENT_ID
    )

    before = dict(
        environment
    )

    module.build_production_teams_host_settings(
        environment
    )

    assert environment == before


def test_settings_boundary_has_no_hidden_environment_runtime_or_credential_side_effects():
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
        "client_secret=",
        "build_production_teams_hitl_app",
        "build_azure_sql_teams_hitl_persistence",
        "build_teams_hitl_app",
        "managedidentitycredential",
        "defaultazurecredential",
        "azureclicredential",
        "azure.identity",
        "mssql_python.connect",
        ".start(",
        ".run(",
        "asyncio.run",
        "sqlite",
        "servicebus",
        "cosmos",
    )

    for fragment in (
        forbidden_fragments
    ):
        assert (
            fragment
            not in lowered
        )
