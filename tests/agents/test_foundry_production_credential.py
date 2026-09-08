from __future__ import annotations

import importlib
import inspect
import textwrap

import pytest

from src.agents.production_settings import (
    FoundryProductionSettings,
)


TARGET_MODULE = (
    "src.agents.production_credential"
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


def test_foundry_credential_factory_has_exact_surface():
    module = _module()

    factory = getattr(
        module,
        "build_foundry_production_credential",
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
        "settings",
    )


def test_foundry_credential_factory_rejects_wrong_settings_type():
    module = _module()

    for invalid_settings in (
        None,
        object(),
        {},
        "system",
        USER_ASSIGNED_CLIENT_ID,
    ):
        with pytest.raises(
            TypeError
        ):
            module.build_foundry_production_credential(
                invalid_settings
            )


def test_system_assigned_settings_construct_managed_identity_without_client_id(
    monkeypatch,
):
    module = _module()

    calls = []
    sentinel = object()

    def fake_credential(
        **kwargs,
    ):
        calls.append(
            kwargs
        )

        return sentinel

    monkeypatch.setattr(
        module,
        "ManagedIdentityCredential",
        fake_credential,
    )

    settings = FoundryProductionSettings(
        project_endpoint=PROJECT_ENDPOINT,
        managed_identity_client_id=None,
    )

    result = (
        module
        .build_foundry_production_credential(
            settings
        )
    )

    assert result is sentinel

    assert calls == [
        {},
    ]


def test_user_assigned_settings_construct_exact_client_id(
    monkeypatch,
):
    module = _module()

    calls = []
    sentinel = object()

    def fake_credential(
        **kwargs,
    ):
        calls.append(
            kwargs
        )

        return sentinel

    monkeypatch.setattr(
        module,
        "ManagedIdentityCredential",
        fake_credential,
    )

    settings = FoundryProductionSettings(
        project_endpoint=PROJECT_ENDPOINT,
        managed_identity_client_id=(
            USER_ASSIGNED_CLIENT_ID
        ),
    )

    result = (
        module
        .build_foundry_production_credential(
            settings
        )
    )

    assert result is sentinel

    assert calls == [
        {
            "client_id": (
                USER_ASSIGNED_CLIENT_ID
            ),
        },
    ]


def test_credential_factory_does_not_request_token_during_construction(
    monkeypatch,
):
    module = _module()

    constructor_calls = []

    class FakeCredential:
        def get_token(
            self,
            *args,
            **kwargs,
        ):
            raise AssertionError(
                "get_token no debe ejecutarse "
                "durante credential composition."
            )

    def fake_credential(
        **kwargs,
    ):
        constructor_calls.append(
            kwargs
        )

        return FakeCredential()

    monkeypatch.setattr(
        module,
        "ManagedIdentityCredential",
        fake_credential,
    )

    result = (
        module
        .build_foundry_production_credential(
            FoundryProductionSettings(
                project_endpoint=PROJECT_ENDPOINT,
                managed_identity_client_id=None,
            )
        )
    )

    assert isinstance(
        result,
        FakeCredential,
    )

    assert constructor_calls == [
        {},
    ]


def test_credential_factory_has_no_environment_agent_runtime_or_channel_authority():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.casefold()

    required = (
        "managedidentitycredential",
        "foundryproductionsettings",
        "managed_identity_client_id",
    )

    for fragment in required:
        assert fragment in lowered

    forbidden = (
        "os.getenv",
        "os.environ",
        "from_environment",
        "azureclicredential",
        "defaultazurecredential",
        "environmentcredential",
        "clientsecretcredential",
        "client_secret",
        "get_token(",
        "foundryagents(",
        "run_communication",
        "communication_runner",
        "build_teams_hitl_app",
        "send_teams_message",
        "asyncio.run",
        ".start(",
        ".run(",
        "mssql_python",
        "sqlite",
        "cosmos",
        "servicebus",
        "mcp",
    )

    for fragment in forbidden:
        assert fragment not in lowered