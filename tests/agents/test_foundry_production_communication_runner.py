from __future__ import annotations

import importlib
import inspect
import textwrap

import pytest

from src.agents.production_settings import (
    FoundryProductionSettings,
)


TARGET_MODULE = (
    "src.agents.production_communication_runner"
)

PROJECT_ENDPOINT = (
    "https://aif-example.services.ai.azure.com/"
    "api/projects/project-example"
)

USER_ASSIGNED_CLIENT_ID = (
    "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
)


def _module():
    return importlib.import_module(
        TARGET_MODULE
    )


def _settings():
    return FoundryProductionSettings(
        project_endpoint=PROJECT_ENDPOINT,
        managed_identity_client_id=(
            USER_ASSIGNED_CLIENT_ID
        ),
    )


def test_production_communication_runner_factory_has_exact_sync_surface():
    module = _module()

    factory = getattr(
        module,
        "build_foundry_production_communication_runner",
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
        "settings",
    )


def test_runner_factory_rejects_wrong_settings_before_dependency_composition(
    monkeypatch,
):
    module = _module()

    credential_calls = []

    monkeypatch.setattr(
        module,
        "build_foundry_production_credential",
        lambda settings: (
            credential_calls.append(
                settings
            )
        ),
    )

    for invalid_settings in (
        None,
        object(),
        {},
        "production",
        USER_ASSIGNED_CLIENT_ID,
    ):
        with pytest.raises(
            TypeError
        ):
            module.build_foundry_production_communication_runner(
                invalid_settings
            )

    assert credential_calls == []


def test_runner_factory_builds_credential_once_from_exact_settings(
    monkeypatch,
):
    module = _module()

    settings = _settings()

    credential = object()

    credential_calls = []

    async def expected_runner(
        request,
    ):
        return request

    class FakeFoundryAgents:
        def __init__(
            self,
            **kwargs,
        ):
            self.run_communication = (
                expected_runner
            )

    def fake_credential_builder(
        actual_settings,
    ):
        credential_calls.append(
            actual_settings
        )

        return credential

    monkeypatch.setattr(
        module,
        "build_foundry_production_credential",
        fake_credential_builder,
    )

    monkeypatch.setattr(
        module,
        "FoundryAgents",
        FakeFoundryAgents,
    )

    result = (
        module
        .build_foundry_production_communication_runner(
            settings
        )
    )

    assert credential_calls == [
        settings,
    ]

    assert result is expected_runner


def test_runner_factory_constructs_foundry_agents_once_with_exact_dependencies(
    monkeypatch,
):
    module = _module()

    settings = _settings()

    credential = object()

    construction_calls = []

    async def expected_runner(
        request,
    ):
        return request

    class FakeFoundryAgents:
        def __init__(
            self,
            *args,
            **kwargs,
        ):
            construction_calls.append(
                (
                    args,
                    kwargs,
                )
            )

            self.run_communication = (
                expected_runner
            )

    monkeypatch.setattr(
        module,
        "build_foundry_production_credential",
        lambda actual_settings: (
            credential
        ),
    )

    monkeypatch.setattr(
        module,
        "FoundryAgents",
        FakeFoundryAgents,
    )

    result = (
        module
        .build_foundry_production_communication_runner(
            settings
        )
    )

    assert construction_calls == [
        (
            (),
            {
                "project_endpoint": (
                    PROJECT_ENDPOINT
                ),
                "credential": credential,
            },
        ),
    ]

    assert result is expected_runner


def test_runner_factory_returns_exact_run_communication_callable(
    monkeypatch,
):
    module = _module()

    settings = _settings()

    async def expected_runner(
        request,
    ):
        return request

    class FakeFoundryAgents:
        def __init__(
            self,
            **kwargs,
        ):
            self.run_communication = (
                expected_runner
            )

    monkeypatch.setattr(
        module,
        "build_foundry_production_credential",
        lambda actual_settings: object(),
    )

    monkeypatch.setattr(
        module,
        "FoundryAgents",
        FakeFoundryAgents,
    )

    result = (
        module
        .build_foundry_production_communication_runner(
            settings
        )
    )

    assert result is expected_runner
    assert callable(result)


def test_runner_factory_does_not_request_token_or_invoke_agent(
    monkeypatch,
):
    module = _module()

    settings = _settings()

    runner_calls = []

    class FakeCredential:
        def get_token(
            self,
            *args,
            **kwargs,
        ):
            raise AssertionError(
                "get_token no debe ejecutarse "
                "durante composition."
            )

    async def forbidden_runner(
        request,
    ):
        runner_calls.append(
            request
        )

        raise AssertionError(
            "run_communication no debe ejecutarse "
            "durante composition."
        )

    class FakeFoundryAgents:
        def __init__(
            self,
            **kwargs,
        ):
            self.run_communication = (
                forbidden_runner
            )

    monkeypatch.setattr(
        module,
        "build_foundry_production_credential",
        lambda actual_settings: FakeCredential(),
    )

    monkeypatch.setattr(
        module,
        "FoundryAgents",
        FakeFoundryAgents,
    )

    result = (
        module
        .build_foundry_production_communication_runner(
            settings
        )
    )

    assert callable(
        result
    )

    assert runner_calls == []


def test_runner_composition_has_no_environment_channel_session_tool_or_mcp_authority():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.casefold()

    required = (
        "foundryproductionsettings",
        "build_foundry_production_credential",
        "foundryagents",
        "project_endpoint",
        "credential",
        "run_communication",
    )

    for fragment in required:
        assert fragment in lowered

    forbidden = (
        "os.getenv",
        "os.environ",
        "from_environment",
        "azureclicredential",
        "managedidentitycredential",
        "defaultazurecredential",
        "get_token(",
        "await ",
        "asyncio.run",
        "create_session",
        "agentsession",
        "session=",
        "tools=",
        "mcp",
        "build_teams_hitl_app",
        "send_teams_message",
        "teamsoutbound",
        "conversation_id",
        "tenant_id",
        ".run_communication(",
    )

    for fragment in forbidden:
        assert fragment not in lowered