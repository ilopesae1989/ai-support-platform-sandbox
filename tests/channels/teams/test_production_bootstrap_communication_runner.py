from __future__ import annotations

import importlib
import inspect
import textwrap

import pytest

from src.channels.teams.bootstrap import (
    TeamsManagedIdentityAppSettings,
)

from src.persistence.azure_sql.connection_provider import (
    AzureSqlManagedIdentitySettings,
)


TARGET_MODULE = (
    "src.channels.teams.production_bootstrap"
)

NEW_FACTORY = (
    "build_production_teams_hitl_app_with_communication"
)


def _module():
    return importlib.import_module(
        TARGET_MODULE
    )


def _app_settings():
    return TeamsManagedIdentityAppSettings(
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


def _azure_sql_settings():
    return AzureSqlManagedIdentitySettings(
        server=(
            "ai-support-platform-sbx"
            ".database.windows.net"
        ),
        database=(
            "ai_support_platform_sbx"
        ),
    )


class FakeReader:
    async def read_power_state(
        self,
        *,
        subscription_id,
        resource_group,
        vm_name,
    ):
        raise AssertionError(
            "reader no debe ejecutarse "
            "durante composition."
        )


def test_historical_builder_surface_remains_exact_and_new_port_is_additive():
    module = _module()

    historical = (
        module
        .build_production_teams_hitl_app
    )

    historical_signature = (
        inspect.signature(
            historical
        )
    )

    assert tuple(
        historical_signature.parameters
    ) == (
        "app_settings",
        "azure_sql_settings",
        "azure_vm_power_state_reader",
    )

    factory = getattr(
        module,
        NEW_FACTORY,
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
        "app_settings",
        "azure_sql_settings",
        "azure_vm_power_state_reader",
        "communication_runner",
    )

    reader_parameter = (
        signature.parameters[
            "azure_vm_power_state_reader"
        ]
    )

    runner_parameter = (
        signature.parameters[
            "communication_runner"
        ]
    )

    assert (
        reader_parameter.kind
        is inspect.Parameter.KEYWORD_ONLY
    )

    assert (
        runner_parameter.kind
        is inspect.Parameter.KEYWORD_ONLY
    )

    assert (
        runner_parameter.default
        is inspect.Parameter.empty
    )


def test_new_port_rejects_non_callable_runner_before_persistence_composition(
    monkeypatch,
):
    module = _module()

    factory = getattr(
        module,
        NEW_FACTORY,
    )

    persistence_calls = []

    monkeypatch.setattr(
        module,
        "build_azure_sql_teams_hitl_persistence",
        lambda settings: (
            persistence_calls.append(
                settings
            )
        ),
    )

    for invalid_runner in (
        None,
        object(),
        "runner",
        123,
    ):
        with pytest.raises(
            TypeError
        ):
            factory(
                _app_settings(),
                _azure_sql_settings(),
                azure_vm_power_state_reader=(
                    FakeReader()
                ),
                communication_runner=(
                    invalid_runner
                ),
            )

    assert persistence_calls == []


def test_new_port_forwards_exact_runner_to_base_teams_bootstrap(
    monkeypatch,
):
    module = _module()

    factory = getattr(
        module,
        NEW_FACTORY,
    )

    app_settings = _app_settings()
    sql_settings = _azure_sql_settings()
    reader = FakeReader()

    persistence = object()
    bootstrap = object()

    async def communication_runner(
        request,
    ):
        return request

    calls = []

    def fake_persistence_builder(
        actual_settings,
    ):
        calls.append(
            (
                "persistence",
                actual_settings,
            )
        )

        return persistence

    def fake_base_builder(
        actual_app_settings,
        *,
        persistence,
        azure_vm_power_state_reader,
        communication_runner,
    ):
        calls.append(
            (
                "base",
                actual_app_settings,
                persistence,
                azure_vm_power_state_reader,
                communication_runner,
            )
        )

        return bootstrap

    monkeypatch.setattr(
        module,
        "build_azure_sql_teams_hitl_persistence",
        fake_persistence_builder,
    )

    monkeypatch.setattr(
        module,
        "build_teams_hitl_app",
        fake_base_builder,
    )

    result = factory(
        app_settings,
        sql_settings,
        azure_vm_power_state_reader=reader,
        communication_runner=(
            communication_runner
        ),
    )

    assert result is bootstrap

    assert calls == [
        (
            "persistence",
            sql_settings,
        ),
        (
            "base",
            app_settings,
            persistence,
            reader,
            communication_runner,
        ),
    ]


def test_new_port_does_not_invoke_communication_runner_during_composition(
    monkeypatch,
):
    module = _module()

    factory = getattr(
        module,
        NEW_FACTORY,
    )

    runner_calls = []

    async def communication_runner(
        request,
    ):
        runner_calls.append(
            request
        )

        raise AssertionError(
            "communication runner no debe "
            "ejecutarse durante composition."
        )

    monkeypatch.setattr(
        module,
        "build_azure_sql_teams_hitl_persistence",
        lambda settings: object(),
    )

    monkeypatch.setattr(
        module,
        "build_teams_hitl_app",
        lambda *args, **kwargs: object(),
    )

    result = factory(
        _app_settings(),
        _azure_sql_settings(),
        azure_vm_power_state_reader=(
            FakeReader()
        ),
        communication_runner=(
            communication_runner
        ),
    )

    assert result is not None
    assert runner_calls == []


def test_production_bootstrap_port_remains_foundry_agnostic():
    module = _module()

    factory = getattr(
        module,
        NEW_FACTORY,
        None,
    )

    assert callable(
        factory
    )

    module_source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    module_lowered = (
        module_source.casefold()
    )

    module_forbidden = (
        "foundryagents",
        "production_communication_runner",
        "managedidentitycredential",
        "azureclicredential",
        "defaultazurecredential",
        "run_communication",
        "get_token(",
    )

    for fragment in module_forbidden:
        assert fragment not in module_lowered

    factory_source = textwrap.dedent(
        inspect.getsource(
            factory
        )
    )

    factory_lowered = (
        factory_source.casefold()
    )

    required = (
        "build_production_teams_hitl_app_with_communication",
        "communication_runner",
        "build_teams_hitl_app",
    )

    for fragment in required:
        assert fragment in factory_lowered

    factory_forbidden = (
        "foundryagents",
        "production_communication_runner",
        "managedidentitycredential",
        "azureclicredential",
        "defaultazurecredential",
        "run_communication",
        "get_token(",
        "create_session",
        "agentsession",
        "session=",
        "tools=",
        "mcp",
    )

    for fragment in factory_forbidden:
        assert fragment not in factory_lowered
