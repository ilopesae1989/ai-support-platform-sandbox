from __future__ import annotations

import inspect

from dataclasses import fields

import pytest

from src.channels.teams import (
    bootstrap as teams_bootstrap,
)


CANONICAL_USER_ASSIGNED_CLIENT_ID = (
    "11111111-1111-4111-8111-111111111111"
)


EXPECTED_MANAGED_IDENTITY_FIELDS = (
    "client_id",
    "managed_identity_client_id",
    "bot_tenant_id",
    "teams_channel_tenant_id",
    "approver_aad_object_id",
    "messaging_endpoint",
)


class FakeApp:
    async def send(
        self,
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "send() no debe ejecutarse "
            "durante bootstrap."
        )


class FakeConversationStore:
    def upsert(
        self,
        binding,
    ) -> None:
        raise AssertionError(
            "upsert() no debe ejecutarse "
            "durante bootstrap."
        )

    def get_exact(
        self,
        *,
        tenant_id,
        conversation_id,
    ):
        raise AssertionError(
            "get_exact() no debe ejecutarse "
            "durante bootstrap."
        )


class FakePowerStateReader:
    def read_power_state(
        self,
        *,
        subscription_id,
        resource_group,
        vm_name,
    ):
        raise AssertionError(
            "El reader no debe ejecutarse "
            "durante bootstrap."
        )


def _managed_identity_settings_type():
    settings_type = getattr(
        teams_bootstrap,
        "TeamsManagedIdentityAppSettings",
        None,
    )

    assert settings_type is not None

    return settings_type


def _managed_identity_settings(
    managed_identity_client_id="system",
):
    settings_type = (
        _managed_identity_settings_type()
    )

    return settings_type(
        client_id=(
            "teams-app-client-id"
        ),
        managed_identity_client_id=(
            managed_identity_client_id
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


def _persistence():
    return (
        teams_bootstrap
        .TeamsHitlPersistence(
            store=object(),
            checkpoint_storage=object(),
            operation_dispatch_ledger=object(),
            continuation_store=object(),
            conversation_store=(
                FakeConversationStore()
            ),
        )
    )


def _configure_bootstrap_mocks(
    monkeypatch,
):
    app_calls = []

    def fake_app(
        **kwargs,
    ):
        app_calls.append(
            kwargs
        )

        return FakeApp()

    monkeypatch.setattr(
        teams_bootstrap,
        "App",
        fake_app,
    )

    monkeypatch.setattr(
        teams_bootstrap,
        "register_teams_approval_handler",
        lambda **kwargs: None,
    )

    monkeypatch.setattr(
        teams_bootstrap,
        "register_teams_conversation_handler",
        lambda **kwargs: None,
    )

    return app_calls


def test_managed_identity_settings_have_exact_secretless_surface():
    settings_type = (
        _managed_identity_settings_type()
    )

    actual_fields = tuple(
        field.name
        for field in fields(
            settings_type
        )
    )

    assert (
        actual_fields
        == EXPECTED_MANAGED_IDENTITY_FIELDS
    )

    assert (
        "client_secret"
        not in actual_fields
    )


def test_managed_identity_settings_are_pure_and_do_not_read_environment():
    settings_type = (
        _managed_identity_settings_type()
    )

    source = inspect.getsource(
        settings_type
    )

    assert (
        "from_environment"
        not in source
    )

    assert (
        "getenv"
        not in source
    )

    assert (
        "environ"
        not in source
    )


def test_managed_identity_settings_accept_system_assigned_identity():
    settings = (
        _managed_identity_settings(
            "system"
        )
    )

    assert (
        settings.managed_identity_client_id
        == "system"
    )


def test_managed_identity_settings_accept_canonical_user_assigned_client_id():
    settings = (
        _managed_identity_settings(
            CANONICAL_USER_ASSIGNED_CLIENT_ID
        )
    )

    assert (
        settings.managed_identity_client_id
        == CANONICAL_USER_ASSIGNED_CLIENT_ID
    )


def test_managed_identity_settings_reject_invalid_identity_identifiers():
    settings_type = (
        _managed_identity_settings_type()
    )

    invalid_values = (
        "",
        " ",
        " system ",
        "System",
        "not-a-client-id",
        (
            "11111111-1111-4111-8111-"
            "11111111111Z"
        ),
        (
            "11111111-1111-4111-8111-"
            "111111111111 "
        ),
    )

    for invalid_value in invalid_values:
        with pytest.raises(
            ValueError
        ):
            settings_type(
                client_id=(
                    "teams-app-client-id"
                ),
                managed_identity_client_id=(
                    invalid_value
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


def test_local_persistence_factory_rejects_managed_identity_app_settings():
    settings = (
        _managed_identity_settings()
    )

    with pytest.raises(
        TypeError
    ):
        teams_bootstrap.build_local_teams_hitl_persistence(
            settings
        )


def test_managed_identity_app_settings_require_injected_persistence(
    monkeypatch,
):
    settings = (
        _managed_identity_settings()
    )

    local_builder_calls = []

    def forbidden_local_builder(
        settings,
    ):
        local_builder_calls.append(
            settings
        )

        raise AssertionError(
            "Managed Identity app settings "
            "no deben activar persistencia local."
        )

    monkeypatch.setattr(
        teams_bootstrap,
        "build_local_teams_hitl_persistence",
        forbidden_local_builder,
    )

    with pytest.raises(
        teams_bootstrap
        .TeamsHitlConfigurationError
    ):
        teams_bootstrap.build_teams_hitl_app(
            settings,
            azure_vm_power_state_reader=(
                FakePowerStateReader()
            ),
        )

    assert local_builder_calls == []


def test_system_assigned_managed_identity_is_passed_to_teams_without_secret(
    monkeypatch,
):
    settings = (
        _managed_identity_settings(
            "system"
        )
    )

    app_calls = (
        _configure_bootstrap_mocks(
            monkeypatch
        )
    )

    teams_bootstrap.build_teams_hitl_app(
        settings,
        persistence=_persistence(),
        azure_vm_power_state_reader=(
            FakePowerStateReader()
        ),
    )

    assert (
        app_calls
        == [
            {
                "client_id": (
                    "teams-app-client-id"
                ),
                "managed_identity_client_id": (
                    "system"
                ),
                "tenant_id": (
                    "bot-tenant-id"
                ),
                "messaging_endpoint": (
                    "/api/messages"
                ),
            }
        ]
    )

    assert (
        "client_secret"
        not in app_calls[0]
    )


def test_user_assigned_managed_identity_is_passed_to_teams_without_secret(
    monkeypatch,
):
    settings = (
        _managed_identity_settings(
            CANONICAL_USER_ASSIGNED_CLIENT_ID
        )
    )

    app_calls = (
        _configure_bootstrap_mocks(
            monkeypatch
        )
    )

    teams_bootstrap.build_teams_hitl_app(
        settings,
        persistence=_persistence(),
        azure_vm_power_state_reader=(
            FakePowerStateReader()
        ),
    )

    assert (
        app_calls
        == [
            {
                "client_id": (
                    "teams-app-client-id"
                ),
                "managed_identity_client_id": (
                    CANONICAL_USER_ASSIGNED_CLIENT_ID
                ),
                "tenant_id": (
                    "bot-tenant-id"
                ),
                "messaging_endpoint": (
                    "/api/messages"
                ),
            }
        ]
    )

    assert (
        "client_secret"
        not in app_calls[0]
    )


def test_existing_client_secret_app_settings_path_remains_unchanged(
    monkeypatch,
):
    _managed_identity_settings_type()

    settings = (
        teams_bootstrap
        .TeamsHitlAppSettings(
            client_id=(
                "teams-app-client-id"
            ),
            client_secret=(
                "existing-test-secret"
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
    )

    app_calls = (
        _configure_bootstrap_mocks(
            monkeypatch
        )
    )

    teams_bootstrap.build_teams_hitl_app(
        settings,
        persistence=_persistence(),
        azure_vm_power_state_reader=(
            FakePowerStateReader()
        ),
    )

    assert (
        app_calls
        == [
            {
                "client_id": (
                    "teams-app-client-id"
                ),
                "client_secret": (
                    "existing-test-secret"
                ),
                "tenant_id": (
                    "bot-tenant-id"
                ),
                "messaging_endpoint": (
                    "/api/messages"
                ),
            }
        ]
    )

    assert (
        "managed_identity_client_id"
        not in app_calls[0]
    )


def test_bootstrap_does_not_select_azure_managed_identity_credential():
    _managed_identity_settings_type()

    source = inspect.getsource(
        teams_bootstrap
    )

    forbidden_fragments = (
        "ManagedIdentityCredential",
        "DefaultAzureCredential",
        "AzureCliCredential",
        "azure.identity",
        "get_token(",
    )

    for fragment in forbidden_fragments:
        assert fragment not in source


def test_production_composition_accepts_managed_identity_app_settings(
    monkeypatch,
):
    from src.channels.teams import (
        production_bootstrap,
    )

    from src.persistence.azure_sql.connection_provider import (
        AzureSqlManagedIdentitySettings,
    )

    settings = (
        _managed_identity_settings(
            "system"
        )
    )

    azure_sql_settings = (
        AzureSqlManagedIdentitySettings(
            server=(
                "ai-support-platform-sbx"
                ".database.windows.net"
            ),
            database=(
                "ai_support_platform_sbx"
            ),
        )
    )

    reader = FakePowerStateReader()

    persistence = object()
    bootstrap = object()

    persistence_calls = []
    teams_calls = []

    def fake_build_persistence(
        settings,
    ):
        persistence_calls.append(
            settings
        )

        return persistence

    def fake_build_teams(
        app_settings,
        *,
        persistence,
        azure_vm_power_state_reader,
    ):
        teams_calls.append(
            {
                "app_settings": (
                    app_settings
                ),
                "persistence": (
                    persistence
                ),
                "azure_vm_power_state_reader": (
                    azure_vm_power_state_reader
                ),
            }
        )

        return bootstrap

    monkeypatch.setattr(
        production_bootstrap,
        "build_azure_sql_teams_hitl_persistence",
        fake_build_persistence,
    )

    monkeypatch.setattr(
        production_bootstrap,
        "build_teams_hitl_app",
        fake_build_teams,
    )

    result = (
        production_bootstrap
        .build_production_teams_hitl_app(
            settings,
            azure_sql_settings,
            azure_vm_power_state_reader=(
                reader
            ),
        )
    )

    assert result is bootstrap

    assert (
        persistence_calls
        == [
            azure_sql_settings
        ]
    )

    assert (
        teams_calls
        == [
            {
                "app_settings": (
                    settings
                ),
                "persistence": (
                    persistence
                ),
                "azure_vm_power_state_reader": (
                    reader
                ),
            }
        ]
    )
