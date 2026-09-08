from __future__ import annotations

import inspect
import json

import pytest

from src.agents.catalog import (
    AgentKey,
    build_agent_catalog,
)

from src.agents.foundry_agents import (
    FoundryAgents,
)

from src.communication.contracts import (
    CommunicationRequest,
    CommunicationResult,
)


def _communication_key():
    return getattr(
        AgentKey,
        "COMMUNICATION",
    )


def _request() -> CommunicationRequest:
    return CommunicationRequest(
        event_type="resolved",
        alert_id="ALERT-SYNTHETIC-001",
        technical_domain="azure",
        corporate_criticality="high",
        affected_resource="vm-synthetic",
        technical_summary=(
            "Synthetic service availability incident."
        ),
        procedure_id="PROC-SYNTHETIC-001",
        procedure_name=(
            "Synthetic recovery procedure"
        ),
        status_summary=(
            "The governed runtime reports "
            "the incident as resolved."
        ),
        escalation_required=False,
        escalation_team=None,
    )


def _result_payload() -> dict:
    return {
        "headline": "Incident resolved",
        "summary": (
            "The incident has been resolved."
        ),
        "details": [
            "Validation succeeded.",
        ],
    }


class FakeResponse:
    def __init__(
        self,
        text,
    ) -> None:
        self.text = text


class CapturingFoundryAgent:
    instances = []

    def __init__(
        self,
        **kwargs,
    ) -> None:
        self.kwargs = kwargs
        self.calls = []

        type(self).instances.append(
            self
        )

    async def run(
        self,
        *args,
        **kwargs,
    ):
        self.calls.append(
            {
                "args": args,
                "kwargs": kwargs,
            }
        )

        return FakeResponse(
            json.dumps(
                _result_payload()
            )
        )


def test_catalog_registers_communication_default(
    monkeypatch,
):
    monkeypatch.delenv(
        "FOUNDRY_AGENT_COMMUNICATION_VERSION",
        raising=False,
    )

    key = _communication_key()

    catalog = build_agent_catalog()

    definition = catalog[key]

    assert definition.name == "agent-communication-sbx"
    assert definition.version == "1"


def test_catalog_allows_communication_version_override(
    monkeypatch,
):
    monkeypatch.setenv(
        "FOUNDRY_AGENT_COMMUNICATION_VERSION",
        "17",
    )

    key = _communication_key()

    catalog = build_agent_catalog()

    assert catalog[key].version == "17"


def test_catalog_rejects_empty_communication_version(
    monkeypatch,
):
    monkeypatch.setenv(
        "FOUNDRY_AGENT_COMMUNICATION_VERSION",
        "   ",
    )

    _communication_key()

    with pytest.raises(
        ValueError,
        match="no puede estar vacío",
    ):
        build_agent_catalog()


@pytest.mark.asyncio
async def test_run_communication_returns_validated_result(
    monkeypatch,
):
    CapturingFoundryAgent.instances = []

    monkeypatch.delenv(
        "FOUNDRY_AGENT_COMMUNICATION_VERSION",
        raising=False,
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

    result = await agents.run_communication(
        _request()
    )

    assert isinstance(
        result,
        CommunicationResult,
    )

    assert result.headline == "Incident resolved"


@pytest.mark.asyncio
async def test_run_communication_is_single_stateless_foundry_call(
    monkeypatch,
):
    CapturingFoundryAgent.instances = []

    monkeypatch.delenv(
        "FOUNDRY_AGENT_COMMUNICATION_VERSION",
        raising=False,
    )

    monkeypatch.setattr(
        "src.agents.foundry_agents.FoundryAgent",
        CapturingFoundryAgent,
    )

    request = _request()

    agents = FoundryAgents(
        project_endpoint=(
            "https://example.invalid/"
            "api/projects/test"
        )
    )

    await agents.run_communication(
        request
    )

    assert len(
        CapturingFoundryAgent.instances
    ) == 1

    agent = (
        CapturingFoundryAgent
        .instances[0]
    )

    assert (
        agent.kwargs["agent_name"]
        == "agent-communication-sbx"
    )

    assert (
        agent.kwargs["agent_version"]
        == "1"
    )

    assert (
        agent.kwargs.get(
            "default_options"
        )
        is None
    )

    assert "tools" not in agent.kwargs

    assert len(agent.calls) == 1

    call = agent.calls[0]

    assert call["kwargs"] == {}
    assert len(call["args"]) == 1

    sent_payload = json.loads(
        call["args"][0]
    )

    assert sent_payload == (
        request.model_dump(
            mode="json"
        )
    )


def test_run_communication_reuses_stateless_adapter_boundary():
    method = getattr(
        FoundryAgents,
        "run_communication",
    )

    source = inspect.getsource(
        method
    )

    assert "CommunicationAgentAdapter" in source

    forbidden = {
        "create_session",
        "AgentSession",
        "SessionStore",
        "session=",
        "ChatOptions",
        "tools=",
        "mcp",
        "tenant_id",
        "conversation_id",
        "recipient",
        "approval_id",
        "capability_id",
        "resolved_parameters",
        "operation_action",
        "target_resource",
    }

    lowered = source.casefold()

    for value in forbidden:
        assert value.casefold() not in lowered