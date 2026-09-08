from __future__ import annotations

import inspect

import pytest

from src.communication.context import (
    SafeCommunicationContext,
    build_safe_communication_context,
)

from src.communication.context_state import (
    SAFE_COMMUNICATION_CONTEXT_STATE_KEY,
)

from src.workflows.incident_resolution.executors.triage import (
    AlertTriageExecutor,
)

from tests.workflows.incident_resolution.test_triage_executor import (
    FakeFoundryAgents,
    create_context,
)


class RecordingWorkflowContext:
    def __init__(
        self,
    ) -> None:
        self.messages = []
        self.state = {}
        self.events = []

    def set_state(
        self,
        key,
        value,
    ) -> None:
        self.events.append(
            (
                "set_state",
                key,
            )
        )

        self.state[key] = value

    def get_state(
        self,
        key,
        default=None,
    ):
        return self.state.get(
            key,
            default,
        )

    async def send_message(
        self,
        message,
    ) -> None:
        self.events.append(
            (
                "send_message",
                None,
            )
        )

        self.messages.append(
            message
        )


class FailingStateWorkflowContext(
    RecordingWorkflowContext
):
    def set_state(
        self,
        key,
        value,
    ) -> None:
        self.events.append(
            (
                "set_state",
                key,
            )
        )

        raise RuntimeError(
            "synthetic state write failure"
        )


@pytest.mark.asyncio
async def test_triage_persists_safe_snapshot_before_routing():
    executor = AlertTriageExecutor(
        agents=FakeFoundryAgents(),
    )

    ctx = RecordingWorkflowContext()

    await executor.triage_alert(
        create_context(),
        ctx,
    )

    assert len(ctx.messages) == 1

    assert (
        SAFE_COMMUNICATION_CONTEXT_STATE_KEY
        in ctx.state
    )

    payload = ctx.state[
        SAFE_COMMUNICATION_CONTEXT_STATE_KEY
    ]

    assert type(payload) is dict

    assert set(payload) == set(
        SafeCommunicationContext.model_fields
    )

    expected = (
        build_safe_communication_context(
            ctx.messages[0]
        ).model_dump(
            mode="json"
        )
    )

    assert payload == expected

    assert ctx.events == [
        (
            "set_state",
            SAFE_COMMUNICATION_CONTEXT_STATE_KEY,
        ),
        (
            "send_message",
            None,
        ),
    ]

    forbidden = {
        "workflow_id",
        "correlation_id",
        "approval_id",
        "conversation_id",
        "subscription_id",
        "resource_group",
        "vm_name",
        "tenant_id",
        "capability_id",
        "operation_action",
        "resolved_parameters",
    }

    assert forbidden.isdisjoint(
        payload
    )


@pytest.mark.asyncio
async def test_safe_snapshot_write_failure_blocks_routing():
    executor = AlertTriageExecutor(
        agents=FakeFoundryAgents(),
    )

    ctx = FailingStateWorkflowContext()

    with pytest.raises(
        RuntimeError,
        match="synthetic state write failure",
    ):
        await executor.triage_alert(
            create_context(),
            ctx,
        )

    assert ctx.messages == []

    assert ctx.events == [
        (
            "set_state",
            SAFE_COMMUNICATION_CONTEXT_STATE_KEY,
        ),
    ]


def test_triage_source_builds_and_stores_snapshot_before_emit():
    source = inspect.getsource(
        AlertTriageExecutor.triage_alert
    )

    assert (
        "build_safe_communication_context"
        in source
    )

    assert (
        "store_safe_communication_context"
        in source
    )

    build_position = source.index(
        "build_safe_communication_context"
    )

    store_position = source.index(
        "store_safe_communication_context"
    )

    send_position = source.index(
        "ctx.send_message"
    )

    assert build_position < store_position
    assert store_position < send_position

    forbidden = {
        "subscription_id",
        "resource_group",
        "vm_name",
        "tenant_id",
        "approval_id",
        "conversation_id",
        "capability_id",
        "operation_action",
        "resolved_parameters",
        "microsoft_teams",
        "foundryagent",
        "agentsession",
        "mcp",
    }

    method_source = source.casefold()

    for value in forbidden:
        assert value.casefold() not in method_source