from __future__ import annotations

import inspect

from dataclasses import fields

import pytest

from src.channels.teams import (
    bootstrap as teams_bootstrap,
)


EXPECTED_APP_FIELDS = (
    "client_id",
    "client_secret",
    "bot_tenant_id",
    "teams_channel_tenant_id",
    "approver_aad_object_id",
    "messaging_endpoint",
)


EXPECTED_LOCAL_FIELDS = (
    "client_id",
    "client_secret",
    "bot_tenant_id",
    "teams_channel_tenant_id",
    "approver_aad_object_id",
    "pending_database_path",
    "checkpoint_path",
    "operation_dispatch_database_path",
    "conversation_binding_database_path",
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


def _app_settings_type():
    settings_type = getattr(
        teams_bootstrap,
        "TeamsHitlAppSettings",
        None,
    )

    assert settings_type is not None

    return settings_type


def _app_settings():
    settings_type = (
        _app_settings_type()
    )

    return settings_type(
        client_id="client-id",
        client_secret="test-client-secret",
        bot_tenant_id="bot-tenant",
        teams_channel_tenant_id=(
            "channel-tenant"
        ),
        approver_aad_object_id=(
            "approver-id"
        ),
    )


def test_app_settings_contract_contains_only_channel_authority():
    settings_type = (
        _app_settings_type()
    )

    actual_fields = tuple(
        field.name
        for field in fields(
            settings_type
        )
    )

    assert (
        actual_fields
        == EXPECTED_APP_FIELDS
    )


def test_app_settings_environment_loader_requires_no_local_persistence_paths(
    monkeypatch,
):
    settings_type = (
        _app_settings_type()
    )

    relevant_names = (
        "CLIENT_ID",
        "CLIENT_SECRET",
        "TENANT_ID",
        "TEAMS_CHANNEL_TENANT_ID",
        "TEAMS_HITL_APPROVER_AAD_OBJECT_ID",
        "TEAMS_HITL_PENDING_DB",
        "TEAMS_HITL_CHECKPOINT_DIR",
        "TEAMS_OPERATION_DISPATCH_DB",
        "TEAMS_CONVERSATION_BINDING_DB",
    )

    for name in relevant_names:
        monkeypatch.delenv(
            name,
            raising=False,
        )

    monkeypatch.setenv(
        "CLIENT_ID",
        "client-id",
    )

    monkeypatch.setenv(
        "CLIENT_SECRET",
        "test-client-secret",
    )

    monkeypatch.setenv(
        "TENANT_ID",
        "bot-tenant",
    )

    monkeypatch.setenv(
        "TEAMS_CHANNEL_TENANT_ID",
        "channel-tenant",
    )

    monkeypatch.setenv(
        "TEAMS_HITL_APPROVER_AAD_OBJECT_ID",
        "approver-id",
    )

    settings = (
        settings_type
        .from_environment()
    )

    assert settings.client_id == "client-id"
    assert settings.client_secret == "test-client-secret"
    assert settings.bot_tenant_id == "bot-tenant"

    assert (
        settings.teams_channel_tenant_id
        == "channel-tenant"
    )

    assert (
        settings.approver_aad_object_id
        == "approver-id"
    )

    assert (
        settings.messaging_endpoint
        == "/api/messages"
    )


def test_injected_persistence_accepts_app_settings_without_local_paths(
    monkeypatch,
):
    settings = _app_settings()

    persistence = (
        teams_bootstrap
        .TeamsHitlPersistence(
            store=object(),
            checkpoint_storage=object(),
            operation_dispatch_ledger=object(),
            continuation_store=object(),
            conversation_store=FakeConversationStore(),
        )
    )

    def forbidden_local_builder(
        settings,
    ):
        raise AssertionError(
            "La configuración de aplicación "
            "con persistence inyectada no debe "
            "construir persistencia local."
        )

    monkeypatch.setattr(
        teams_bootstrap,
        "build_local_teams_hitl_persistence",
        forbidden_local_builder,
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

    monkeypatch.setattr(
        teams_bootstrap,
        "App",
        lambda **kwargs: FakeApp(),
    )

    bootstrap = (
        teams_bootstrap
        .build_teams_hitl_app(
            settings,
            persistence=persistence,
        )
    )

    assert bootstrap.store is persistence.store

    assert (
        bootstrap.checkpoint_storage
        is persistence.checkpoint_storage
    )

    assert (
        bootstrap.operation_dispatch_ledger
        is persistence.operation_dispatch_ledger
    )

    assert (
        bootstrap.continuation_store
        is persistence.continuation_store
    )

    assert (
        bootstrap.conversation_store
        is persistence.conversation_store
    )


def test_app_settings_without_injected_persistence_fails_closed(
    monkeypatch,
):
    settings = _app_settings()

    local_builder_calls = []

    def forbidden_local_builder(
        settings,
    ):
        local_builder_calls.append(
            settings
        )

        raise AssertionError(
            "No debe tratar TeamsHitlAppSettings "
            "como configuración de persistencia local."
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
            settings
        )

    assert local_builder_calls == []


def test_existing_local_settings_and_local_factory_authority_remain_unchanged():
    _app_settings_type()

    actual_fields = tuple(
        field.name
        for field in fields(
            teams_bootstrap
            .TeamsHitlSettings
        )
    )

    assert (
        actual_fields
        == EXPECTED_LOCAL_FIELDS
    )

    local_signature = inspect.signature(
        teams_bootstrap
        .build_local_teams_hitl_persistence
    )

    assert (
        tuple(
            local_signature.parameters
        )
        == (
            "settings",
        )
    )
