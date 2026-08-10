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

    async def run(
        self,
        message: str,
    ):
        self.messages.append(
            message
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


@pytest.mark.asyncio
async def test_run_azure_operations_does_not_parse_response(
    monkeypatch,
):
    """
    Durante FASE 13 FoundryAgents debe conservar
    la respuesta nativa del agente Azure.

    No debe intentar repararla, convertirla a JSON
    ni aplicar contratos que todavía no hemos
    validado contra MCP LIVE.
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