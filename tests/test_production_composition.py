from __future__ import annotations

import ast
import importlib
import inspect
import textwrap

import pytest


TARGET_MODULE = (
    "src.production_composition"
)

TARGET_FACTORY = (
    "build_production_application"
)


def _module():
    return importlib.import_module(
        TARGET_MODULE
    )


async def _communication_runner(
    request,
):
    return request


def test_application_production_root_has_exact_sync_surface():
    module = _module()

    factory = getattr(
        module,
        TARGET_FACTORY,
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
    )


def test_application_production_root_rejects_unstructured_environment_before_dependencies(
    monkeypatch,
):
    module = _module()

    calls = []

    monkeypatch.setattr(
        module,
        "build_foundry_production_settings",
        lambda environment: (
            calls.append(
                "foundry_settings"
            )
        ),
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
            module.build_production_application(
                invalid_environment
            )

    assert calls == []



def test_application_root_composes_exact_foundry_and_teams_chain(
    monkeypatch,
):
    module = _module()

    environment = {
        "EXPLICIT": "mapping",
    }

    foundry_settings = object()
    bootstrap = object()

    async def communication_runner(
        request,
    ):
        return request

    class FakeProductionAgents:
        pass

    incident_agents = (
        FakeProductionAgents()
    )

    incident_agents.run_communication = (
        communication_runner
    )

    calls = []

    def fake_foundry_settings_builder(
        actual_environment,
    ):
        calls.append(
            (
                "foundry_settings",
                actual_environment,
            )
        )

        return foundry_settings

    def fake_agents_builder(
        actual_settings,
    ):
        calls.append(
            (
                "foundry_agents",
                actual_settings,
            )
        )

        return incident_agents

    def fake_teams_builder(
        actual_environment,
        *,
        communication_runner,
        incident_agents,
    ):
        calls.append(
            (
                "teams_host",
                actual_environment,
                communication_runner,
                incident_agents,
            )
        )

        return bootstrap

    monkeypatch.setattr(
        module,
        "build_foundry_production_settings",
        fake_foundry_settings_builder,
    )

    monkeypatch.setattr(
        module,
        "build_foundry_production_agents",
        fake_agents_builder,
    )

    monkeypatch.setattr(
        module,
        "build_production_teams_host_with_communication_and_incident_agents",
        fake_teams_builder,
    )

    result = (
        module
        .build_production_application(
            environment
        )
    )

    assert result is bootstrap

    assert calls == [
        (
            "foundry_settings",
            environment,
        ),
        (
            "foundry_agents",
            foundry_settings,
        ),
        (
            "teams_host",
            environment,
            communication_runner,
            incident_agents,
        ),
    ]


def test_application_root_fails_closed_if_runner_factory_returns_non_callable(
    monkeypatch,
):
    module = _module()

    environment = {
        "EXPLICIT": "mapping",
    }

    foundry_settings = object()
    teams_calls = []

    monkeypatch.setattr(
        module,
        "build_foundry_production_settings",
        lambda actual_environment: (
            foundry_settings
        ),
    )

    monkeypatch.setattr(
        module,
        "build_foundry_production_communication_runner",
        lambda actual_settings: object(),
    )

    monkeypatch.setattr(
        module,
        "build_production_teams_host_with_communication",
        lambda *args, **kwargs: (
            teams_calls.append(
                (
                    args,
                    kwargs,
                )
            )
        ),
    )

    with pytest.raises(
        TypeError
    ):
        module.build_production_application(
            environment
        )

    assert teams_calls == []



def test_application_root_does_not_mutate_environment(
    monkeypatch,
):
    module = _module()

    environment = {
        "FOUNDRY_PROJECT_ENDPOINT": (
            "https://example.invalid/project"
        ),
        "ANOTHER": "value",
    }

    before = dict(
        environment
    )

    async def communication_runner(
        request,
    ):
        return request

    class FakeProductionAgents:
        pass

    incident_agents = (
        FakeProductionAgents()
    )

    incident_agents.run_communication = (
        communication_runner
    )

    monkeypatch.setattr(
        module,
        "build_foundry_production_settings",
        lambda actual_environment: object(),
    )

    monkeypatch.setattr(
        module,
        "build_foundry_production_agents",
        lambda actual_settings: incident_agents,
    )

    monkeypatch.setattr(
        module,
        "build_production_teams_host_with_communication_and_incident_agents",
        lambda *args, **kwargs: object(),
    )

    module.build_production_application(
        environment
    )

    assert environment == before


def test_application_root_owns_composition_without_direct_runtime_or_credential_authority():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.casefold()

    required = (
        "build_foundry_production_settings",
        "build_foundry_production_communication_runner",
        "build_production_teams_host_with_communication",
        "communication_runner",
    )

    for fragment in required:
        assert fragment in lowered

    forbidden = (
        "managedidentitycredential",
        "azureclicredential",
        "defaultazurecredential",
        "foundryagents(",
        "build_foundry_production_credential",
        "get_token(",
        ".run_communication(",
        "await ",
        "asyncio.run",
        "create_session",
        "agentsession",
        "session=",
        "tools=",
        "mcp",
        "os.getenv",
        "os.environ",
        "build_teams_hitl_app",
        "build_production_teams_hitl_app",
    )

    for fragment in forbidden:
        assert fragment not in lowered
    tree = ast.parse(
        source
    )

    direct_runner_calls = [
        node
        for node in ast.walk(
            tree
        )
        if (
            isinstance(
                node,
                ast.Call,
            )
            and isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id
            == "communication_runner"
        )
    ]

    assert direct_runner_calls == []

# TDD_PHASE23_PRODUCTION_INCIDENT_MANAGED_IDENTITY_APPLICATION_ROOT_RED
def test_phase23_production_incident_managed_identity_application_root_shared_agents(
    monkeypatch,
):
    """
    El composition root construye un único bundle cognitivo
    productivo y reutiliza exactamente ese objeto para:

        - communication_runner;
        - incident-resolution.

    Así ningún pipeline cognitivo productivo puede caer en
    FoundryAgents() -> AzureCliCredential().
    """

    module = _module()

    environment = {
        "EXPLICIT": "mapping",
    }

    foundry_settings = object()
    bootstrap = object()

    async def communication_runner(
        request,
    ):
        return request

    class FakeProductionAgents:
        pass

    incident_agents = (
        FakeProductionAgents()
    )

    incident_agents.run_communication = (
        communication_runner
    )

    calls = []

    def fake_settings_builder(
        actual_environment,
    ):
        calls.append(
            (
                "settings",
                actual_environment,
            )
        )

        return foundry_settings

    def fake_agents_builder(
        actual_settings,
    ):
        calls.append(
            (
                "agents",
                actual_settings,
            )
        )

        return incident_agents

    def fake_teams_builder(
        actual_environment,
        *,
        communication_runner,
        incident_agents,
    ):
        calls.append(
            (
                "teams",
                actual_environment,
                communication_runner,
                incident_agents,
            )
        )

        return bootstrap

    def forbidden_legacy_runner(
        actual_settings,
    ):
        raise AssertionError(
            "El application root no debe construir "
            "un segundo bundle sólo para comunicación."
        )

    def forbidden_legacy_teams(
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "El application root debe usar el port "
            "que propaga incident_agents."
        )

    monkeypatch.setattr(
        module,
        "build_foundry_production_settings",
        fake_settings_builder,
    )

    monkeypatch.setattr(
        module,
        "build_foundry_production_agents",
        fake_agents_builder,
        raising=False,
    )

    monkeypatch.setattr(
        module,
        "build_production_teams_host_with_communication_and_incident_agents",
        fake_teams_builder,
        raising=False,
    )

    monkeypatch.setattr(
        module,
        "build_foundry_production_communication_runner",
        forbidden_legacy_runner,
    )

    monkeypatch.setattr(
        module,
        "build_production_teams_host_with_communication",
        forbidden_legacy_teams,
    )

    result = (
        module
        .build_production_application(
            environment
        )
    )

    assert result is bootstrap

    assert calls == [
        (
            "settings",
            environment,
        ),
        (
            "agents",
            foundry_settings,
        ),
        (
            "teams",
            environment,
            communication_runner,
            incident_agents,
        ),
    ]
