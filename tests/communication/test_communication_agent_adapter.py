from __future__ import annotations

from importlib import import_module
import inspect
import json

import pytest

from src.communication.contracts import (
    CommunicationRequest,
)


def _adapter_module():
    try:
        return import_module(
            "src.communication.agent_adapter"
        )
    except ModuleNotFoundError as exc:
        if exc.name != "src.communication.agent_adapter":
            raise

        pytest.fail(
            "Stateless Communication Agent adapter "
            "is not implemented.",
            pytrace=False,
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


def _valid_result_payload() -> dict:
    return {
        "headline": "Incident resolved",
        "summary": (
            "The incident has been resolved."
        ),
        "details": [
            "Post-operation validation succeeded.",
            "No further automatic action is required.",
        ],
    }


class FakeResponse:
    def __init__(
        self,
        text,
    ) -> None:
        self.text = text


class FakeRunner:
    def __init__(
        self,
        response,
    ) -> None:
        self.response = response
        self.calls = []

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

        return self.response


@pytest.mark.asyncio
async def test_adapter_accepts_exact_request_and_returns_validated_result():
    module = _adapter_module()

    runner = FakeRunner(
        FakeResponse(
            json.dumps(
                _valid_result_payload()
            )
        )
    )

    adapter = (
        module.CommunicationAgentAdapter(
            runner=runner
        )
    )

    result = await adapter.run(
        _request()
    )

    assert (
        type(result).__name__
        == "CommunicationResult"
    )

    assert result.headline == "Incident resolved"
    assert result.summary == (
        "The incident has been resolved."
    )

    assert result.details == [
        "Post-operation validation succeeded.",
        "No further automatic action is required.",
    ]


@pytest.mark.asyncio
async def test_adapter_sends_only_safe_request_json():
    module = _adapter_module()

    runner = FakeRunner(
        FakeResponse(
            json.dumps(
                _valid_result_payload()
            )
        )
    )

    adapter = (
        module.CommunicationAgentAdapter(
            runner=runner
        )
    )

    request = _request()

    await adapter.run(
        request
    )

    assert len(runner.calls) == 1

    args = runner.calls[0]["args"]

    assert len(args) == 1
    assert isinstance(args[0], str)

    sent_payload = json.loads(
        args[0]
    )

    assert sent_payload == (
        request.model_dump(
            mode="json"
        )
    )

    assert set(sent_payload) == set(
        CommunicationRequest.model_fields
    )


@pytest.mark.asyncio
async def test_adapter_invokes_runner_once_without_session_options_or_tools():
    module = _adapter_module()

    runner = FakeRunner(
        FakeResponse(
            json.dumps(
                _valid_result_payload()
            )
        )
    )

    adapter = (
        module.CommunicationAgentAdapter(
            runner=runner
        )
    )

    await adapter.run(
        _request()
    )

    assert len(runner.calls) == 1

    call = runner.calls[0]

    assert len(call["args"]) == 1

    assert call["kwargs"] == {}


@pytest.mark.asyncio
async def test_adapter_requires_exact_communication_request():
    module = _adapter_module()

    runner = FakeRunner(
        FakeResponse(
            json.dumps(
                _valid_result_payload()
            )
        )
    )

    adapter = (
        module.CommunicationAgentAdapter(
            runner=runner
        )
    )

    with pytest.raises(TypeError):
        await adapter.run(
            object()
        )

    assert runner.calls == []


@pytest.mark.asyncio
async def test_adapter_rejects_malformed_json():
    module = _adapter_module()

    runner = FakeRunner(
        FakeResponse(
            "not-json"
        )
    )

    adapter = (
        module.CommunicationAgentAdapter(
            runner=runner
        )
    )

    with pytest.raises(
        module.CommunicationAgentAdapterError
    ):
        await adapter.run(
            _request()
        )


@pytest.mark.asyncio
async def test_adapter_rejects_non_object_json():
    module = _adapter_module()

    runner = FakeRunner(
        FakeResponse(
            json.dumps(
                [
                    "not",
                    "an",
                    "object",
                ]
            )
        )
    )

    adapter = (
        module.CommunicationAgentAdapter(
            runner=runner
        )
    )

    with pytest.raises(
        module.CommunicationAgentAdapterError
    ):
        await adapter.run(
            _request()
        )


@pytest.mark.asyncio
async def test_adapter_rejects_response_without_text():
    module = _adapter_module()

    runner = FakeRunner(
        object()
    )

    adapter = (
        module.CommunicationAgentAdapter(
            runner=runner
        )
    )

    with pytest.raises(
        module.CommunicationAgentAdapterError
    ):
        await adapter.run(
            _request()
        )


@pytest.mark.asyncio
async def test_adapter_rejects_truth_authority_in_output():
    module = _adapter_module()

    payload = _valid_result_payload()
    payload["event_type"] = "resolved"

    runner = FakeRunner(
        FakeResponse(
            json.dumps(
                payload
            )
        )
    )

    adapter = (
        module.CommunicationAgentAdapter(
            runner=runner
        )
    )

    with pytest.raises(
        module.CommunicationAgentAdapterError
    ):
        await adapter.run(
            _request()
        )


def test_adapter_requires_runner_with_run_method():
    module = _adapter_module()

    with pytest.raises(TypeError):
        module.CommunicationAgentAdapter(
            runner=object()
        )


def test_adapter_source_is_stateless_framework_and_channel_agnostic():
    module = _adapter_module()

    source = inspect.getsource(
        module
    )

    forbidden = {
        "agent_framework",
        "FoundryAgent",
        "AgentSession",
        "SessionStore",
        "create_session",
        "microsoft_teams",
        "src.channels.teams",
        "send_teams_message",
        "send_teams_adaptive_card",
        "tenant_id",
        "conversation_id",
        "recipient",
        "approval_id",
        "capability_id",
        "resolved_parameters",
        "operation_action",
        "target_resource",
        "tools=",
        "mcp",
    }

    lowered = source.casefold()

    for value in forbidden:
        assert value.casefold() not in lowered