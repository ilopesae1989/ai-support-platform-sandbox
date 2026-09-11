from __future__ import annotations

import importlib
import inspect
import textwrap
from types import SimpleNamespace

import pytest


TARGET_MODULE = (
    "src.channels.teams.production_composition"
)

NEW_FACTORY = (
    "build_production_teams_host_with_communication"
)

TEAMS_MANAGED_IDENTITY_CLIENT_ID = (
    "7fa09b7a-cc8f-48e5-af88-1600d924c799"
)

GRAPH_MEMBERSHIP_CHECKER = object()


def _module():
    return importlib.import_module(
        TARGET_MODULE
    )


async def _runner(
    request,
):
    return request


def test_historical_host_surface_remains_exact_and_new_port_is_additive():
    module = _module()

    historical = (
        module
        .build_production_teams_host
    )

    historical_signature = (
        inspect.signature(
            historical
        )
    )

    assert tuple(
        historical_signature.parameters
    ) == (
        "environment",
    )

    factory = getattr(
        module,
        NEW_FACTORY,
        None,
    )

    assert callable(
        factory
    )

    assert not inspect.iscoroutinefunction(
        factory
    )

    signature = inspect.signature(
        factory
    )

    assert tuple(
        signature.parameters
    ) == (
        "environment",
        "communication_runner",
    )

    runner_parameter = (
        signature.parameters[
            "communication_runner"
        ]
    )

    assert (
        runner_parameter.kind
        is inspect.Parameter.KEYWORD_ONLY
    )

    assert (
        runner_parameter.default
        is inspect.Parameter.empty
    )


def test_new_composition_port_rejects_unstructured_environment():
    module = _module()

    factory = getattr(
        module,
        NEW_FACTORY,
    )

    for invalid_environment in (
        None,
        object(),
        [],
        "KEY=value",
    ):
        with pytest.raises(
            TypeError
        ):
            factory(
                invalid_environment,
                communication_runner=(
                    _runner
                ),
            )


def test_new_composition_port_rejects_non_callable_runner_before_dependencies(
    monkeypatch,
):
    module = _module()

    factory = getattr(
        module,
        NEW_FACTORY,
    )

    calls = []

    monkeypatch.setattr(
        module,
        "build_production_teams_host_settings",
        lambda environment: (
            calls.append(
                "host_settings"
            )
        ),
    )

    monkeypatch.setattr(
        module,
        "build_azure_vm_observation_settings",
        lambda environment: (
            calls.append(
                "observation_settings"
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
                {},
                communication_runner=(
                    invalid_runner
                ),
            )

    assert calls == []


def test_new_composition_port_delegates_exact_boundaries_and_runner(
    monkeypatch,
):
    module = _module()

    factory = getattr(
        module,
        NEW_FACTORY,
    )

    environment = {
        "EXPLICIT": "mapping",
    }

    app_settings = SimpleNamespace(
        managed_identity_client_id=(
            TEAMS_MANAGED_IDENTITY_CLIENT_ID
        ),
    )
    azure_sql_settings = object()

    host_settings = SimpleNamespace(
        app_settings=app_settings,
        azure_sql_settings=(
            azure_sql_settings
        ),
    )

    observation_settings = object()
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

    def fake_graph_builder(
        *,
        managed_identity_client_id,
    ):
        calls.append(
            (
                "graph_membership",
                managed_identity_client_id,
            )
        )

        return GRAPH_MEMBERSHIP_CHECKER

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
        actual_app_settings,
        actual_azure_sql_settings,
        *,
        membership_checker,
        azure_vm_power_state_reader,
        communication_runner,
    ):
        calls.append(
            (
                "bootstrap",
                actual_app_settings,
                actual_azure_sql_settings,
                membership_checker,
                azure_vm_power_state_reader,
                communication_runner,
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
        "build_managed_identity_graph_membership_client",
        fake_graph_builder,
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
        "build_production_teams_hitl_app_with_communication",
        fake_bootstrap_builder,
    )

    result = factory(
        environment,
        communication_runner=(
            _runner
        ),
    )

    assert result is bootstrap

    assert calls == [
        (
            "host_settings",
            environment,
        ),
        (
            "graph_membership",
            TEAMS_MANAGED_IDENTITY_CLIENT_ID,
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
            app_settings,
            azure_sql_settings,
            GRAPH_MEMBERSHIP_CHECKER,
            reader,
            _runner,
        ),
    ]


def test_new_composition_port_does_not_invoke_runner(
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
            "communication_runner no debe ejecutarse "
            "durante composition."
        )

    host_settings = SimpleNamespace(
        app_settings=SimpleNamespace(
            managed_identity_client_id=(
                TEAMS_MANAGED_IDENTITY_CLIENT_ID
            ),
        ),
        azure_sql_settings=object(),
    )

    monkeypatch.setattr(
        module,
        "build_production_teams_host_settings",
        lambda environment: host_settings,
    )

    monkeypatch.setattr(
        module,
        "build_managed_identity_graph_membership_client",
        lambda **kwargs: GRAPH_MEMBERSHIP_CHECKER,
    )

    monkeypatch.setattr(
        module,
        "build_azure_vm_observation_settings",
        lambda environment: object(),
    )

    monkeypatch.setattr(
        module,
        "build_azure_vm_observation_reader",
        lambda settings: object(),
    )

    monkeypatch.setattr(
        module,
        "build_production_teams_hitl_app_with_communication",
        lambda *args, **kwargs: object(),
    )

    result = factory(
        {},
        communication_runner=(
            communication_runner
        ),
    )

    assert result is not None
    assert runner_calls == []


def test_new_composition_port_does_not_mutate_environment(
    monkeypatch,
):
    module = _module()

    factory = getattr(
        module,
        NEW_FACTORY,
    )

    environment = {
        "EXPLICIT": "value",
        "ANOTHER": "value",
    }

    before = dict(
        environment
    )

    host_settings = SimpleNamespace(
        app_settings=SimpleNamespace(
            managed_identity_client_id=(
                TEAMS_MANAGED_IDENTITY_CLIENT_ID
            ),
        ),
        azure_sql_settings=object(),
    )

    monkeypatch.setattr(
        module,
        "build_production_teams_host_settings",
        lambda actual_environment: (
            host_settings
        ),
    )

    monkeypatch.setattr(
        module,
        "build_managed_identity_graph_membership_client",
        lambda **kwargs: GRAPH_MEMBERSHIP_CHECKER,
    )

    monkeypatch.setattr(
        module,
        "build_azure_vm_observation_settings",
        lambda actual_environment: object(),
    )

    monkeypatch.setattr(
        module,
        "build_azure_vm_observation_reader",
        lambda settings: object(),
    )

    monkeypatch.setattr(
        module,
        "build_production_teams_hitl_app_with_communication",
        lambda *args, **kwargs: object(),
    )

    factory(
        environment,
        communication_runner=(
            _runner
        ),
    )

    assert environment == before


def test_new_composition_port_remains_foundry_and_runtime_agnostic():
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

    required_module = (
        "build_production_teams_host",
        "build_production_teams_host_with_communication",
        "build_production_teams_hitl_app",
        "build_production_teams_hitl_app_with_communication",
        "build_production_teams_host_settings",
        "build_managed_identity_graph_membership_client",
        "build_azure_vm_observation_settings",
        "build_azure_vm_observation_reader",
    )

    for fragment in required_module:
        assert fragment in module_lowered

    module_forbidden = (
        "foundryagents",
        "foundryproductionsettings",
        "production_communication_runner",
        "managedidentitycredential",
        "azureclicredential",
        "defaultazurecredential",
        "get_token(",
        "run_communication",
        "os.getenv",
        "os.environ",
        "asyncio.run",
        "mcp",
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

    required_factory = (
        "communication_runner",
        "build_production_teams_host_settings",
        "build_managed_identity_graph_membership_client",
        "build_azure_vm_observation_settings",
        "build_azure_vm_observation_reader",
        "build_production_teams_hitl_app_with_communication",
    )

    for fragment in required_factory:
        assert fragment in factory_lowered

    factory_forbidden = (
        "foundryagents",
        "foundryproductionsettings",
        "production_communication_runner",
        "managedidentitycredential",
        "azureclicredential",
        "defaultazurecredential",
        "get_token(",
        "run_communication",
        "communication_runner(",
        "await ",
        "asyncio.run",
        "create_session",
        "agentsession",
        "session=",
        "tools=",
        "mcp",
    )

    for fragment in factory_forbidden:
        assert fragment not in factory_lowered