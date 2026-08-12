import pytest

from src.agents.catalog import (
    AgentKey,
)
from src.agents.foundry_agents import (
    FoundryAgents,
)


class FakeAgent:
    def __init__(self) -> None:
        self.messages = []
        self.run_options = []

    async def run(
        self,
        message: str,
        **options,
    ):
        self.messages.append(
            message
        )

        self.run_options.append(
            options
        )

        return {
            "fake": True,
            "message": message,
        }


@pytest.mark.asyncio
async def test_run_azure_operations_uses_catalog_definition(
    monkeypatch,
):
    agents = FoundryAgents(
        project_endpoint=(
            "https://example.invalid/"
            "api/projects/test"
        )
    )

    definition = agents.get_definition(
        AgentKey.AZURE_OPERATIONS
    )

    assert (
        definition.name
        == "agent-azure-operations-sbx"
    )

    assert (
        definition.version
        == "11"
    )

    fake_agent = FakeAgent()

    created_definitions = []

    def fake_create_agent(
        received_definition,
    ):
        created_definitions.append(
            received_definition
        )

        return fake_agent

    monkeypatch.setattr(
        agents,
        "_create_agent",
        fake_create_agent,
    )

    response = (
        await agents.run_azure_operations(
            "Consulta Azure controlada."
        )
    )

    assert len(
        created_definitions
    ) == 1

    assert (
        created_definitions[0]
        == definition
    )

    assert fake_agent.messages == [
        "Consulta Azure controlada."
    ]

    assert response == {
        "fake": True,
        "message": (
            "Consulta Azure controlada."
        ),
    }


def test_create_azure_operations_agent_limits_backend_to_one_tool_call(
    monkeypatch,
):
    captured_kwargs = []

    class CapturingFoundryAgent:
        def __init__(
            self,
            **kwargs,
        ) -> None:
            captured_kwargs.append(
                kwargs
            )

    monkeypatch.setattr(
        "src.agents.foundry_agents.FoundryAgent",
        CapturingFoundryAgent,
    )

    agents = FoundryAgents(
        project_endpoint=(
            "https://example.invalid/"
            "api/projects/test"
        )
    )

    definition = agents.get_definition(
        AgentKey.AZURE_OPERATIONS
    )

    agents._create_agent(
        definition
    )

    assert len(
        captured_kwargs
    ) == 1

    options = (
        captured_kwargs[0]
        .get(
            "default_options"
        )
    )

    assert options == {
        "extra_body": {
            "max_tool_calls": 1,
            "parallel_tool_calls": False,
        }
    }


def test_create_cognitive_agent_does_not_apply_azure_tool_call_policy(
    monkeypatch,
):
    captured_kwargs = []

    class CapturingFoundryAgent:
        def __init__(
            self,
            **kwargs,
        ) -> None:
            captured_kwargs.append(
                kwargs
            )

    monkeypatch.setattr(
        "src.agents.foundry_agents.FoundryAgent",
        CapturingFoundryAgent,
    )

    agents = FoundryAgents(
        project_endpoint=(
            "https://example.invalid/"
            "api/projects/test"
        )
    )

    definition = agents.get_definition(
        AgentKey.CLASSIFICATION
    )

    agents._create_agent(
        definition
    )

    assert len(
        captured_kwargs
    ) == 1

    assert (
        captured_kwargs[0]
        .get(
            "default_options"
        )
        is None
    )


@pytest.mark.asyncio
async def test_run_azure_operations_does_not_parse_response(
    monkeypatch,
):
    """
    FoundryAgents conserva la respuesta nativa
    de Azure Operations.

    La limitación de tool calls no autoriza a esta
    capa a interpretar, reparar o sustituir la
    respuesta del agente.
    """

    agents = FoundryAgents(
        project_endpoint=(
            "https://example.invalid/"
            "api/projects/test"
        )
    )

    native_response = object()

    class NativeFakeAgent:
        async def run(
            self,
            message: str,
            **options,
        ):
            return native_response

    monkeypatch.setattr(
        agents,
        "_create_agent",
        lambda definition:
            NativeFakeAgent(),
    )

    result = (
        await agents.run_azure_operations(
            "Operación Azure."
        )
    )

    assert result is native_response