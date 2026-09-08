from __future__ import annotations

import inspect

import src.agents.foundry_agents as foundry_module

from src.agents.catalog import (
    AgentKey,
)
from src.agents.foundry_agents import (
    FoundryAgents,
)


PROJECT_ENDPOINT = (
    "https://example.invalid/"
    "api/projects/test"
)


def test_foundry_agents_accepts_optional_keyword_only_credential():
    signature = inspect.signature(
        FoundryAgents
    )

    assert "credential" in signature.parameters

    parameter = signature.parameters[
        "credential"
    ]

    assert (
        parameter.kind
        is inspect.Parameter.KEYWORD_ONLY
    )

    assert parameter.default is None


def test_injected_credential_bypasses_local_azure_cli_construction(
    monkeypatch,
):
    injected_credential = object()

    cli_construction = []

    def forbidden_cli_credential():
        cli_construction.append(
            True
        )

        raise AssertionError(
            "AzureCliCredential no debe "
            "construirse cuando credential "
            "fue inyectada."
        )

    monkeypatch.setattr(
        foundry_module,
        "AzureCliCredential",
        forbidden_cli_credential,
    )

    agents = FoundryAgents(
        project_endpoint=PROJECT_ENDPOINT,
        credential=injected_credential,
    )

    assert cli_construction == []

    assert (
        agents._credential
        is injected_credential
    )


def test_create_cognitive_agent_uses_exact_injected_credential(
    monkeypatch,
):
    injected_credential = object()

    captured = []

    class CapturingFoundryAgent:
        def __init__(
            self,
            **kwargs,
        ):
            captured.append(
                kwargs
            )

    def forbidden_cli_credential():
        raise AssertionError(
            "AzureCliCredential no debe "
            "construirse cuando credential "
            "fue inyectada."
        )

    monkeypatch.setattr(
        foundry_module,
        "FoundryAgent",
        CapturingFoundryAgent,
    )

    monkeypatch.setattr(
        foundry_module,
        "AzureCliCredential",
        forbidden_cli_credential,
    )

    agents = FoundryAgents(
        project_endpoint=PROJECT_ENDPOINT,
        credential=injected_credential,
    )

    definition = agents.get_definition(
        AgentKey.CLASSIFICATION
    )

    agents._create_agent(
        definition
    )

    assert len(captured) == 1

    assert (
        captured[0]["credential"]
        is injected_credential
    )


def test_same_injected_credential_is_reused_across_agent_definitions(
    monkeypatch,
):
    injected_credential = object()

    captured = []

    class CapturingFoundryAgent:
        def __init__(
            self,
            **kwargs,
        ):
            captured.append(
                kwargs
            )

    def forbidden_cli_credential():
        raise AssertionError(
            "AzureCliCredential no debe "
            "construirse cuando credential "
            "fue inyectada."
        )

    monkeypatch.setattr(
        foundry_module,
        "FoundryAgent",
        CapturingFoundryAgent,
    )

    monkeypatch.setattr(
        foundry_module,
        "AzureCliCredential",
        forbidden_cli_credential,
    )

    agents = FoundryAgents(
        project_endpoint=PROJECT_ENDPOINT,
        credential=injected_credential,
    )

    for key in (
        AgentKey.COMMUNICATION,
        AgentKey.AZURE_OPERATIONS,
    ):
        agents._create_agent(
            agents.get_definition(
                key
            )
        )

    assert len(captured) == 2

    assert all(
        kwargs["credential"]
        is injected_credential
        for kwargs in captured
    )