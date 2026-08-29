from __future__ import annotations

from dataclasses import (
    fields,
)

import pytest

from src.agents.contracts import (
    ClassificationResult,
)

from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)

from src.workflows.incident_resolution.checkpoint_storage import (
    incident_checkpoint_allowed_types,
)

from src.workflows.incident_resolution.executors.classification import (
    ClassificationExecutor,
)

import src.workflows.incident_resolution.executors.runtime as runtime_module

from src.workflows.incident_resolution.executors.runtime import (
    ProcedureRuntimeExecutor,
)

from src.workflows.incident_resolution.workflow_input import (
    INCIDENT_CONVERSATION_ID_STATE_KEY,
    IncidentWorkflowInput,
    load_incident_conversation_id,
    store_incident_conversation_id,
)


CONVERSATION_ID = (
    "19:phase18-conversation@thread.v2"
)


def create_alert():
    return NormalizedAlert(
        alert_id="ALT-CONVERSATION-001",
        source="azure_monitor",
        name="VM stopped",
        description=(
            "Synthetic conversation correlation test."
        ),
        affected_resource="vm-demo",
        resource_type=(
            "Microsoft.Compute/"
            "virtualMachines"
        ),
        subscription_id="sub-demo",
        resource_group="rg-demo",
        vm_name="vm-demo",
    )


class FakeWorkflowContext:
    def __init__(
        self,
    ):
        self.state = {}
        self.messages = []

    def set_state(
        self,
        key,
        value,
    ):
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
        value,
    ):
        self.messages.append(
            value
        )


class FakeClassificationAgents:
    def __init__(
        self,
    ):
        self.prompt = None

    async def run_classification(
        self,
        prompt,
    ):
        self.prompt = prompt

        return ClassificationResult(
            alert_id="ALT-CONVERSATION-001",
            alert_classification=(
                "infrastructure_availability"
            ),
            technical_domain="azure",
            affected_resource="vm-demo",
            affected_service="azure-vm",
            classification_summary=(
                "Synthetic classification."
            ),
            requires_clarification=False,
            missing_information=[],
            confidence=0.99,
        )


def test_input_fields_are_exact_transport_boundary():
    names = {
        field.name
        for field in fields(
            IncidentWorkflowInput
        )
    }

    assert names == {
        "alert",
        "conversation_id",
    }


def test_input_preserves_exact_alert_and_conversation():
    alert = create_alert()

    value = IncidentWorkflowInput(
        alert=alert,
        conversation_id=CONVERSATION_ID,
    )

    assert value.alert is alert

    assert (
        value.conversation_id
        == CONVERSATION_ID
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        " ",
        " conversation",
        "conversation ",
        123,
        None,
    ],
)
def test_input_rejects_invalid_conversation_id(
    value,
):
    with pytest.raises(
        (
            TypeError,
            ValueError,
        )
    ):
        IncidentWorkflowInput(
            alert=create_alert(),
            conversation_id=value,
        )


def test_workflow_state_round_trip_is_exact():
    ctx = FakeWorkflowContext()

    store_incident_conversation_id(
        ctx,
        CONVERSATION_ID,
    )

    assert (
        ctx.state[
            INCIDENT_CONVERSATION_ID_STATE_KEY
        ]
        == CONVERSATION_ID
    )

    assert (
        load_incident_conversation_id(
            ctx
        )
        == CONVERSATION_ID
    )


def test_missing_state_preserves_legacy_workflow_compatibility():
    ctx = FakeWorkflowContext()

    assert (
        load_incident_conversation_id(
            ctx
        )
        is None
    )


@pytest.mark.asyncio
async def test_classification_agent_never_receives_conversation_id():
    agents = FakeClassificationAgents()

    executor = ClassificationExecutor(
        agents=agents,
    )

    ctx = FakeWorkflowContext()

    alert = create_alert()

    await executor.classify_workflow_input(
        IncidentWorkflowInput(
            alert=alert,
            conversation_id=(
                CONVERSATION_ID
            ),
        ),
        ctx,
    )

    assert (
        ctx.state[
            INCIDENT_CONVERSATION_ID_STATE_KEY
        ]
        == CONVERSATION_ID
    )

    assert agents.prompt is not None

    assert (
        CONVERSATION_ID
        not in agents.prompt
    )

    assert len(
        ctx.messages
    ) == 1

    assert (
        ctx.messages[0].alert
        is alert
    )


@pytest.mark.asyncio
async def test_runtime_handler_copies_conversation_into_runtime_state(
    monkeypatch,
):
    ctx = FakeWorkflowContext()

    store_incident_conversation_id(
        ctx,
        CONVERSATION_ID,
    )

    captured = {}

    state_sentinel = object()

    def fake_build(
        self,
        context,
        *,
        conversation_id=None,
    ):
        captured[
            "context"
        ] = context

        captured[
            "conversation_id"
        ] = conversation_id

        return state_sentinel

    monkeypatch.setattr(
        ProcedureRuntimeExecutor,
        "_build_runtime_state",
        fake_build,
    )

    monkeypatch.setattr(
        runtime_module,
        "store_procedure_runtime_state",
        lambda ctx, state: None,
    )

    executor = object.__new__(
        ProcedureRuntimeExecutor
    )

    execution_context = object()

    await executor.create_runtime_state(
        execution_context,
        ctx,
    )

    assert (
        captured[
            "context"
        ]
        is execution_context
    )

    assert (
        captured[
            "conversation_id"
        ]
        == CONVERSATION_ID
    )

    assert (
        ctx.messages
        == [
            state_sentinel
        ]
    )


def test_checkpoint_allowlist_is_exactly_extended_by_input_type():
    allowed = (
        incident_checkpoint_allowed_types()
    )

    expected = (
        "src.workflows.incident_resolution."
        "workflow_input:IncidentWorkflowInput"
    )

    assert len(
        allowed
    ) == 43

    assert expected in allowed
