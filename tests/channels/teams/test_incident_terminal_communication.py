from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from src.channels.teams.incident_terminal_presenter import (
    IncidentTerminalPresentationError,
    notify_teams_incident_terminal_result,
    render_incident_terminal_result,
)

from src.communication.context import (
    SafeCommunicationContext,
)

from src.communication.contracts import (
    CommunicationRequest,
    CommunicationResult,
)

from src.communication.projection import (
    CommunicationProjectionError,
)

from tests.channels.teams.test_incident_terminal_presenter import (
    _invocation,
    _state,
)


def _safe_context(
    *,
    alert_id="alert-terminal-test",
) -> SafeCommunicationContext:
    return SafeCommunicationContext(
        alert_id=alert_id,
        technical_domain="azure",
        corporate_criticality="high",
        affected_resource="vm-terminal-safe",
        technical_summary=(
            "Synthetic terminal incident."
        ),
        procedure_id="PROC-TERMINAL-001",
        procedure_name=(
            "Procedimiento terminal test"
        ),
    )


def _processed(
    *,
    state=None,
    safe_context=None,
):
    return SimpleNamespace(
        workflow_result=(
            state
            if state is not None
            else _state()
        ),
        safe_communication_context=(
            safe_context
            if safe_context is not None
            else _safe_context()
        ),
    )


def _communication_result():
    return CommunicationResult(
        headline="Incident resolved",
        summary=(
            "The incident has been resolved."
        ),
        details=[
            "Validation succeeded.",
            "Service state is healthy.",
        ],
    )


@pytest.mark.asyncio
async def test_presenter_projects_governed_request_before_cognitive_call(
    monkeypatch,
):
    import src.channels.teams.incident_terminal_presenter as presenter

    captured = {
        "requests": [],
        "sends": [],
    }

    async def fake_communication_runner(
        request,
    ):
        captured["requests"].append(
            request
        )

        return _communication_result()

    async def fake_send(
        **kwargs,
    ):
        captured["sends"].append(
            kwargs
        )

        return "sent"

    monkeypatch.setattr(
        presenter,
        "send_teams_message",
        fake_send,
    )

    result = await (
        notify_teams_incident_terminal_result(
            invocation=_invocation(),
            processed=_processed(),
            outbound=object(),
            communication_runner=(
                fake_communication_runner
            ),
        )
    )

    assert result == "sent"

    assert len(
        captured["requests"]
    ) == 1

    request = (
        captured["requests"][0]
    )

    assert type(request) is CommunicationRequest

    assert request.event_type == "resolved"
    assert request.alert_id == "alert-terminal-test"
    assert request.technical_domain == "azure"

    assert request.affected_resource == (
        "vm-terminal-safe"
    )

    serialized = repr(
        request.model_dump(
            mode="json"
        )
    )

    for forbidden in (
        "apr-terminal-test",
        "conversation-terminal-test",
        "target_resource",
        "resolved_parameters",
        "capability_id",
        "operation_action",
    ):
        assert forbidden not in serialized


@pytest.mark.asyncio
async def test_presenter_renders_validated_communication_result(
    monkeypatch,
):
    import src.channels.teams.incident_terminal_presenter as presenter

    captured = {}

    async def fake_communication_runner(
        request,
    ):
        return _communication_result()

    async def fake_send(
        *,
        dependencies,
        tenant_id,
        conversation_id,
        text,
    ):
        captured["dependencies"] = dependencies
        captured["tenant_id"] = tenant_id
        captured["conversation_id"] = (
            conversation_id
        )
        captured["text"] = text

        return "sent"

    monkeypatch.setattr(
        presenter,
        "send_teams_message",
        fake_send,
    )

    await (
        notify_teams_incident_terminal_result(
            invocation=_invocation(),
            processed=_processed(),
            outbound=object(),
            communication_runner=(
                fake_communication_runner
            ),
        )
    )

    assert captured["text"] == (
        "Incident resolved\n"
        "The incident has been resolved.\n"
        "- Validation succeeded.\n"
        "- Service state is healthy."
    )


@pytest.mark.asyncio
async def test_cognitive_failure_uses_deterministic_terminal_fallback(
    monkeypatch,
):
    import src.channels.teams.incident_terminal_presenter as presenter

    state = _state()
    captured = {}

    async def failing_communication_runner(
        request,
    ):
        raise RuntimeError(
            "synthetic cognitive failure"
        )

    async def fake_send(
        **kwargs,
    ):
        captured.update(
            kwargs
        )

        return "sent"

    monkeypatch.setattr(
        presenter,
        "send_teams_message",
        fake_send,
    )

    result = await (
        notify_teams_incident_terminal_result(
            invocation=_invocation(),
            processed=_processed(
                state=state
            ),
            outbound=object(),
            communication_runner=(
                failing_communication_runner
            ),
        )
    )

    assert result == "sent"

    assert captured["text"] == (
        render_incident_terminal_result(
            state
        )
    )


@pytest.mark.asyncio
async def test_cognitive_path_keeps_authorized_teams_destination(
    monkeypatch,
):
    import src.channels.teams.incident_terminal_presenter as presenter

    invocation = _invocation()
    captured = {}

    async def fake_communication_runner(
        request,
    ):
        return _communication_result()

    async def fake_send(
        **kwargs,
    ):
        captured.update(
            kwargs
        )

        return "sent"

    monkeypatch.setattr(
        presenter,
        "send_teams_message",
        fake_send,
    )

    await (
        notify_teams_incident_terminal_result(
            invocation=invocation,
            processed=_processed(),
            outbound=object(),
            communication_runner=(
                fake_communication_runner
            ),
        )
    )

    assert captured["tenant_id"] == (
        invocation.operator.tenant_id
    )

    assert captured["conversation_id"] == (
        invocation.operator.conversation_id
    )


@pytest.mark.asyncio
async def test_missing_safe_context_blocks_cognitive_path_before_send(
    monkeypatch,
):
    import src.channels.teams.incident_terminal_presenter as presenter

    runner_calls = []
    send_calls = []

    async def fake_communication_runner(
        request,
    ):
        runner_calls.append(
            request
        )

        return _communication_result()

    async def fake_send(
        **kwargs,
    ):
        send_calls.append(
            kwargs
        )

        return "sent"

    monkeypatch.setattr(
        presenter,
        "send_teams_message",
        fake_send,
    )

    processed = SimpleNamespace(
        workflow_result=_state()
    )

    with pytest.raises(
        IncidentTerminalPresentationError
    ):
        await (
            notify_teams_incident_terminal_result(
                invocation=_invocation(),
                processed=processed,
                outbound=object(),
                communication_runner=(
                    fake_communication_runner
                ),
            )
        )

    assert runner_calls == []
    assert send_calls == []


@pytest.mark.asyncio
async def test_safe_context_runtime_mismatch_fails_before_agent_and_send(
    monkeypatch,
):
    import src.channels.teams.incident_terminal_presenter as presenter

    runner_calls = []
    send_calls = []

    async def fake_communication_runner(
        request,
    ):
        runner_calls.append(
            request
        )

        return _communication_result()

    async def fake_send(
        **kwargs,
    ):
        send_calls.append(
            kwargs
        )

        return "sent"

    monkeypatch.setattr(
        presenter,
        "send_teams_message",
        fake_send,
    )

    with pytest.raises(
        CommunicationProjectionError
    ):
        await (
            notify_teams_incident_terminal_result(
                invocation=_invocation(),
                processed=_processed(
                    safe_context=_safe_context(
                        alert_id="OTHER-ALERT"
                    )
                ),
                outbound=object(),
                communication_runner=(
                    fake_communication_runner
                ),
            )
        )

    assert runner_calls == []
    assert send_calls == []


def test_presenter_cognitive_boundary_is_injected_and_non_authoritative():
    import src.channels.teams.incident_terminal_presenter as presenter

    source = inspect.getsource(
        presenter.notify_teams_incident_terminal_result
    ).casefold()

    required = {
        "communication_runner",
        "build_runtime_communication_request",
        "safe_communication_context",
        "render_incident_terminal_result",
        "send_teams_message",
        "invocation.operator.tenant_id",
        "invocation.operator.conversation_id",
    }

    for value in required:
        assert value.casefold() in source

    forbidden = {
        "foundryagents",
        "communicationagentadapter",
        "create_session",
        "agentsession",
        "session=",
        "tools=",
        "mcp",
        "approval_id",
        "capability_id",
        "resolved_parameters",
        "operation_action",
        "target_resource",
    }

    for value in forbidden:
        assert value.casefold() not in source