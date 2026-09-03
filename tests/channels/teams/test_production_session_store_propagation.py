from __future__ import annotations

import dataclasses
import importlib
import inspect
import textwrap

from dataclasses import fields

from src.channels.teams.azure_sql_persistence import (
    AzureSqlTeamsHitlPersistence,
)

from src.channels.teams.bootstrap import (
    TeamsHitlAppSettings,
    TeamsHitlBootstrap,
)

from src.persistence.azure_sql.connection_provider import (
    AzureSqlManagedIdentitySettings,
)


TARGET_MODULE = (
    "src.channels.teams.production_bootstrap"
)


BASE_FIELD_NAMES = tuple(
    field.name
    for field in fields(
        TeamsHitlBootstrap
    )
)


PRODUCTION_FIELD_NAMES = (
    *BASE_FIELD_NAMES,
    "session_store",
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
            "durante composición."
        )


def _module():
    return importlib.import_module(
        TARGET_MODULE
    )


def _app_settings():
    return TeamsHitlAppSettings(
        client_id="teams-app-client-id",
        client_secret="test-client-secret",
        bot_tenant_id="bot-tenant-id",
        teams_channel_tenant_id=(
            "channel-tenant-id"
        ),
        approver_aad_object_id=(
            "approver-object-id"
        ),
    )

def _settings():
    return AzureSqlManagedIdentitySettings(
        server=(
            "ai-support-platform-sbx"
            ".database.windows.net"
        ),
        database=(
            "ai_support_platform_sbx"
        ),
    )


def _reader():
    return FakePowerStateReader()


def _base_bootstrap():
    bootstrap = object.__new__(
        TeamsHitlBootstrap
    )

    for index, field in enumerate(
        fields(
            TeamsHitlBootstrap
        )
    ):
        object.__setattr__(
            bootstrap,
            field.name,
            (
                "base-field",
                index,
                field.name,
            ),
        )

    return bootstrap


def _productive_persistence(
    *,
    session_store,
):
    persistence = object.__new__(
        AzureSqlTeamsHitlPersistence
    )

    object.__setattr__(
        persistence,
        "session_store",
        session_store,
    )

    return persistence


def _production_bootstrap_type():
    module = _module()

    bootstrap_type = getattr(
        module,
        "ProductionTeamsHitlBootstrap",
        None,
    )

    assert bootstrap_type is not None

    return bootstrap_type


def test_productive_bootstrap_subtype_is_frozen_and_extends_exact_base():
    bootstrap_type = (
        _production_bootstrap_type()
    )

    assert dataclasses.is_dataclass(
        bootstrap_type
    )

    assert issubclass(
        bootstrap_type,
        TeamsHitlBootstrap,
    )

    params = getattr(
        bootstrap_type,
        "__dataclass_params__",
    )

    assert params.frozen is True

    assert tuple(
        field.name
        for field in fields(
            bootstrap_type
        )
    ) == PRODUCTION_FIELD_NAMES


def test_production_builder_return_annotation_exposes_productive_bootstrap():
    module = _module()

    builder = (
        module
        .build_production_teams_hitl_app
    )

    signature = inspect.signature(
        builder
    )

    assert (
        "ProductionTeamsHitlBootstrap"
        in str(
            signature.return_annotation
        )
    )


def test_real_productive_persistence_propagates_session_store(
    monkeypatch,
):
    module = _module()

    bootstrap_type = (
        _production_bootstrap_type()
    )

    session_store = object()

    persistence = (
        _productive_persistence(
            session_store=session_store
        )
    )

    base_bootstrap = _base_bootstrap()

    persistence_calls = []
    teams_calls = []

    def fake_persistence_builder(
        settings,
    ):
        persistence_calls.append(
            settings
        )

        return persistence

    def fake_teams_builder(
        settings,
        *,
        persistence,
        azure_vm_power_state_reader,
    ):
        teams_calls.append(
            (
                settings,
                persistence,
                azure_vm_power_state_reader,
            )
        )

        return base_bootstrap

    monkeypatch.setattr(
        module,
        "build_azure_sql_teams_hitl_persistence",
        fake_persistence_builder,
    )

    monkeypatch.setattr(
        module,
        "build_teams_hitl_app",
        fake_teams_builder,
    )

    reader = _reader()
    settings = _settings()

    result = (
        module
        .build_production_teams_hitl_app(
            _app_settings(),
            settings,
            azure_vm_power_state_reader=reader,
        )
    )

    assert isinstance(
        result,
        bootstrap_type,
    )

    assert isinstance(
        result,
        TeamsHitlBootstrap,
    )

    assert result.session_store is session_store

    assert persistence_calls == [
        settings
    ]

    assert len(
        teams_calls
    ) == 1

    assert (
        teams_calls[0][1]
        is persistence
    )

    assert (
        teams_calls[0][2]
        is reader
    )


def test_productive_wrapper_preserves_every_base_bootstrap_field(
    monkeypatch,
):
    module = _module()

    session_store = object()

    persistence = (
        _productive_persistence(
            session_store=session_store
        )
    )

    base_bootstrap = _base_bootstrap()

    monkeypatch.setattr(
        module,
        "build_azure_sql_teams_hitl_persistence",
        lambda settings: persistence,
    )

    monkeypatch.setattr(
        module,
        "build_teams_hitl_app",
        lambda *args, **kwargs: (
            base_bootstrap
        ),
    )

    result = (
        module
        .build_production_teams_hitl_app(
            _app_settings(),
            _settings(),
            azure_vm_power_state_reader=_reader(),
        )
    )

    for field_name in BASE_FIELD_NAMES:
        assert (
            getattr(
                result,
                field_name,
            )
            is getattr(
                base_bootstrap,
                field_name,
            )
        )

    assert result.session_store is session_store


def test_production_propagation_contains_no_session_execution_or_new_authority():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.lower()

    required = (
        "productionteamshitlbootstrap",
        "azuresqlteamshitlpersistence",
        "session_store",
        "build_azure_sql_teams_hitl_persistence",
        "build_teams_hitl_app",
    )

    for fragment in required:
        assert fragment in lowered

    forbidden = (
        "run_conversation_agent_turn",
        "session_store.get",
        "session_store.set",
        "create_session",
        "agent.run",
        "foundryagent",
        "foundryagents",
        "agentkey",
        "service_session_id",
        "os.environ",
        "os.getenv",
        "mssql_python.connect",
        "managedidentitycredential",
        "defaultazurecredential",
        "azureclicredential",
        "create table",
        "alter table",
        "drop table",
        "sqlite",
        "cosmos",
        "servicebus",
        "mcp",
    )

    for fragment in forbidden:
        assert fragment not in lowered
