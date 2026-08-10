import pytest

from src.agents.contracts import (
    ProcedureValidationResult,
)

from src.agents.foundry_agents import (
    FoundryAgents,
)


class FakeResponse:
    def __init__(
        self,
        text,
    ):
        self.text = text
        self.messages = []


class FakeAgent:
    def __init__(
        self,
        response,
    ):
        self.response = response
        self.calls = []

    async def run(
        self,
        message,
    ):
        self.calls.append(
            message
        )

        return self.response


def create_foundry_agents_without_init(
    fake_agent,
):
    agents = FoundryAgents.__new__(
        FoundryAgents
    )

    agents._catalog = {}
    agents._project_endpoint = (
        "https://example.invalid"
    )

    agents._credential = None

    agents.get_definition = (
        lambda key:
            type(
                "Definition",
                (),
                {
                    "key": key,
                    "name": (
                        "agent-procedure-"
                        "execution-sbx"
                    ),
                    "version": "6",
                },
            )()
    )

    agents._register_invocation = (
        lambda definition:
            None
    )

    agents._create_agent = (
        lambda definition:
            fake_agent
    )

    return agents


@pytest.mark.asyncio
async def test_foundry_adapter_parses_strict_validation_json():
    fake_agent = FakeAgent(
        FakeResponse(
            """
{
  "operation_id": "op-001",
  "validation_status": "satisfied",
  "proposed_next_action": "continue",
  "validation_summary": "Resultado válido.",
  "escalation": {
    "required": false,
    "team": null,
    "level": null,
    "criteria": null
  }
}
""".strip()
        )
    )

    agents = (
        create_foundry_agents_without_init(
            fake_agent
        )
    )

    result = (
        await agents
        .run_procedure_validation(
            "validation prompt"
        )
    )

    assert isinstance(
        result,
        ProcedureValidationResult,
    )

    assert (
        result.operation_id
        == "op-001"
    )

    assert (
        result.proposed_next_action
        == "continue"
    )

    assert fake_agent.calls == [
        "validation prompt"
    ]


@pytest.mark.asyncio
async def test_foundry_adapter_rejects_non_json():
    fake_agent = FakeAgent(
        FakeResponse(
            "not-json"
        )
    )

    agents = (
        create_foundry_agents_without_init(
            fake_agent
        )
    )

    with pytest.raises(
        RuntimeError,
    ):
        await agents.run_procedure_validation(
            "validation prompt"
        )


@pytest.mark.asyncio
async def test_foundry_adapter_rejects_old_procedure_execution_contract():
    fake_agent = FakeAgent(
        FakeResponse(
            """
{
  "alert_id": "ALT-001",
  "procedure": {
    "id": "PROC-001",
    "name": "Procedure",
    "version": "v1"
  },
  "execution_allowed": true,
  "blocked_by_policy": false,
  "total_steps": 1,
  "current_step": 1,
  "step": null,
  "resolution_criteria": null,
  "next_action": "continue",
  "escalation": {
    "required": false,
    "team": null,
    "level": null,
    "criteria": null
  },
  "requires_clarification": false,
  "missing_information": [],
  "source_documents": [],
  "confidence": 0.9
}
""".strip()
        )
    )

    agents = (
        create_foundry_agents_without_init(
            fake_agent
        )
    )

    with pytest.raises(
        RuntimeError,
    ):
        await agents.run_procedure_validation(
            "validation prompt"
        )


@pytest.mark.asyncio
async def test_foundry_adapter_rejects_execute_step_validation_output():
    fake_agent = FakeAgent(
        FakeResponse(
            """
{
  "operation_id": "op-001",
  "validation_status": "satisfied",
  "proposed_next_action": "execute_step",
  "validation_summary": "No permitido.",
  "escalation": {
    "required": false,
    "team": null,
    "level": null,
    "criteria": null
  }
}
""".strip()
        )
    )

    agents = (
        create_foundry_agents_without_init(
            fake_agent
        )
    )

    with pytest.raises(
        RuntimeError,
    ):
        await agents.run_procedure_validation(
            "validation prompt"
        )
