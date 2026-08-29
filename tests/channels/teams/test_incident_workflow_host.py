from dataclasses import (
    dataclass,
)

import pytest

from tests.channels.teams.test_approval_card import (
    create_request,
)


REQUEST_ID = (
    "request-info-phase18-host-001"
)

CHECKPOINT_ID = (
    "checkpoint-phase18-host-001"
)

TENANT_ID = (
    "3048dc87-43f0-4100-"
    "9acb-ae1971c79395"
)

CONVERSATION_ID = (
    "a:test-approval-conversation"
)


@dataclass
class FakeRequestInfoEvent:
    type: str
    request_id: str
    data: object


@dataclass
class FakeCheckpoint:
    checkpoint_id: str
    pending_request_info_events: dict


class FakeWorkflow:
    name = "incident-resolution"

    def __init__(
        self,
        events,
    ):
        self.events = list(events)

        self.stream_finished = False
        self.run_calls = []

    async def run(
        self,
        alert,
        *,
        stream,
        checkpoint_storage,
    ):
        self.run_calls.append(
            {
                "alert": alert,
                "stream": stream,
                "checkpoint_storage":
                    checkpoint_storage,
            }
        )

        for event in self.events:
            yield event

        #
        # Importante:
        # sólo después de agotar el stream se
        # considera terminada la ejecución
        # suspendida en HITL.
        #
        self.stream_finished = True


class FakeCheckpointStorage:
    def __init__(
        self,
        *,
        workflow,
        checkpoints,
    ):
        self.workflow = workflow
        self.checkpoints = checkpoints
        self.list_calls = []

    async def list_checkpoints(
        self,
        *,
        workflow_name,
    ):
        #
        # Nunca se debe buscar el checkpoint
        # mientras el stream todavía está
        # procesando el superstep.
        #
        assert (
            self.workflow.stream_finished
            is True
        )

        self.list_calls.append(
            workflow_name
        )

        return self.checkpoints


@pytest.mark.asyncio
async def test_host_waits_for_suspended_run_then_registers_and_notifies(
    monkeypatch,
):
    import src.channels.teams.incident_workflow_host as host

    request = create_request()

    event = FakeRequestInfoEvent(
        type="request_info",
        request_id=REQUEST_ID,
        data=request,
    )

    workflow = FakeWorkflow(
        [
            event,
        ]
    )

    checkpoint = FakeCheckpoint(
        checkpoint_id=CHECKPOINT_ID,

        pending_request_info_events={
            REQUEST_ID: {
                "request_id": REQUEST_ID,
            }
        },
    )

    storage = FakeCheckpointStorage(
        workflow=workflow,
        checkpoints=[
            checkpoint,
        ],
    )

    sequence = []

    correlation = object()
    notification_result = object()

    def fake_register(
        *,
        request,
        request_id,
        checkpoints,
        store,
    ):
        sequence.append(
            "register"
        )

        assert (
            request
            is event.data
        )

        assert (
            request_id
            == REQUEST_ID
        )

        assert checkpoints == [
            checkpoint,
        ]

        return correlation

    async def fake_notify(
        *,
        request,
        request_id,
        store,
        outbound,
        tenant_id,
        conversation_id,
    ):
        sequence.append(
            "notify"
        )

        assert (
            request
            is event.data
        )

        assert (
            request_id
            == REQUEST_ID
        )

        assert tenant_id == TENANT_ID

        assert (
            conversation_id
            == CONVERSATION_ID
        )

        return notification_result

    monkeypatch.setattr(
        host,
        "register_pending_approval_correlation",
        fake_register,
        raising=False,
    )

    monkeypatch.setattr(
        host,
        "notify_registered_teams_approval",
        fake_notify,
        raising=False,
    )

    alert = _create_host_normalized_alert()
    store = object()
    outbound = object()

    result = await (
        host.run_incident_until_teams_approval(
            workflow=workflow,
            alert=alert,
            checkpoint_storage=storage,
            store=store,
            outbound=outbound,
            tenant_id=TENANT_ID,
            conversation_id=(
                CONVERSATION_ID
            ),
        )
    )

    assert result is notification_result

    assert len(
        workflow.run_calls
    ) == 1

    # TDD_PHASE18_HOST_ENVELOPE_RUN_CALL_ASSERTION_FIX
    from src.workflows.incident_resolution.workflow_input import (
        IncidentWorkflowInput,
    )

    run_call = (
        workflow.run_calls[0]
    )

    assert set(
        run_call
    ) == {
        "alert",
        "stream",
        "checkpoint_storage",
    }

    workflow_input = (
        run_call["alert"]
    )

    assert isinstance(
        workflow_input,
        IncidentWorkflowInput,
    )

    assert (
        workflow_input.alert
        is alert
    )

    assert (
        workflow_input.conversation_id
        == CONVERSATION_ID
    )

    assert (
        run_call["stream"]
        is True
    )

    assert (
        run_call["checkpoint_storage"]
        is storage
    )

    assert storage.list_calls == [
        "incident-resolution"
    ]

    assert sequence == [
        "register",
        "notify",
    ]


@pytest.mark.asyncio
async def test_host_requires_exactly_one_request_info(
    monkeypatch,
):
    import src.channels.teams.incident_workflow_host as host

    workflow = FakeWorkflow(
        []
    )

    storage = FakeCheckpointStorage(
        workflow=workflow,
        checkpoints=[],
    )

    register_calls = []
    notify_calls = []

    monkeypatch.setattr(
        host,
        "register_pending_approval_correlation",
        lambda **kwargs:
            register_calls.append(
                kwargs
            ),
        raising=False,
    )

    async def fake_notify(
        **kwargs,
    ):
        notify_calls.append(
            kwargs
        )

    monkeypatch.setattr(
        host,
        "notify_registered_teams_approval",
        fake_notify,
        raising=False,
    )

    with pytest.raises(
        host.IncidentWorkflowHostError
    ):
        await (
            host.run_incident_until_teams_approval(
                workflow=workflow,
                alert=_create_host_normalized_alert(),
                checkpoint_storage=storage,
                store=object(),
                outbound=object(),
                tenant_id=TENANT_ID,
                conversation_id=(
                    CONVERSATION_ID
                ),
            )
        )

    assert register_calls == []
    assert notify_calls == []


@pytest.mark.asyncio
async def test_registration_failure_prevents_teams_notification(
    monkeypatch,
):
    import src.channels.teams.incident_workflow_host as host

    request = create_request()

    workflow = FakeWorkflow(
        [
            FakeRequestInfoEvent(
                type="request_info",
                request_id=REQUEST_ID,
                data=request,
            )
        ]
    )

    checkpoint = FakeCheckpoint(
        checkpoint_id=CHECKPOINT_ID,

        pending_request_info_events={
            REQUEST_ID: {}
        },
    )

    storage = FakeCheckpointStorage(
        workflow=workflow,
        checkpoints=[
            checkpoint,
        ],
    )

    notify_calls = []

    def fail_registration(
        **kwargs,
    ):
        raise RuntimeError(
            "synthetic registration failure"
        )

    async def fake_notify(
        **kwargs,
    ):
        notify_calls.append(
            kwargs
        )

    monkeypatch.setattr(
        host,
        "register_pending_approval_correlation",
        fail_registration,
        raising=False,
    )

    monkeypatch.setattr(
        host,
        "notify_registered_teams_approval",
        fake_notify,
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic registration failure",
    ):
        await (
            host.run_incident_until_teams_approval(
                workflow=workflow,
                alert=_create_host_normalized_alert(),
                checkpoint_storage=storage,
                store=object(),
                outbound=object(),
                tenant_id=TENANT_ID,
                conversation_id=(
                    CONVERSATION_ID
                ),
            )
        )

    assert notify_calls == []

# TDD_PHASE18_REPLAYABLE_CONVERSATION_INPUT_RED
@pytest.mark.asyncio
async def test_host_places_exact_conversation_id_in_replayable_workflow_input(
    monkeypatch,
):
    """
    El conversation_id validado por el boundary
    Teams debe entrar en el input inicial del
    incident workflow.

    Razón:

    Agent Framework 1.13.0 checkpointa el input
    original en iteration_count == 0.

    Por tanto la correlación necesaria para HITL:

        conversation_id

    debe formar parte del input replayable y no
    permanecer únicamente fuera del workflow.

    El input NO puede transportar tenant_id ni
    autoridad operacional.
    """

    import src.channels.teams.incident_workflow_host as host

    from src.workflows.incident_resolution.alert_models import (
        NormalizedAlert,
    )

    alert = NormalizedAlert(
        alert_id=(
            "alert-phase18-conversation-"
            "input-red-001"
        ),
        source="azure_monitor",
        name="VM stopped",
        description=(
            "Synthetic alert used only "
            "for conversation input TDD."
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

    request = create_request()

    event = FakeRequestInfoEvent(
        type="request_info",
        request_id=REQUEST_ID,
        data=request,
    )

    workflow = FakeWorkflow(
        [
            event,
        ]
    )

    checkpoint = FakeCheckpoint(
        checkpoint_id=CHECKPOINT_ID,
        pending_request_info_events={
            REQUEST_ID: {
                "request_id":
                    REQUEST_ID,
            }
        },
    )

    storage = FakeCheckpointStorage(
        workflow=workflow,
        checkpoints=[
            checkpoint,
        ],
    )

    def fake_register(
        **kwargs,
    ):
        return object()

    async def fake_notify(
        **kwargs,
    ):
        return object()

    monkeypatch.setattr(
        host,
        "register_pending_approval_correlation",
        fake_register,
        raising=False,
    )

    monkeypatch.setattr(
        host,
        "notify_registered_teams_approval",
        fake_notify,
        raising=False,
    )

    await host.run_incident_until_teams_approval(
        workflow=workflow,
        alert=alert,
        checkpoint_storage=storage,
        store=object(),
        outbound=object(),
        tenant_id=TENANT_ID,
        conversation_id=CONVERSATION_ID,
    )

    assert len(
        workflow.run_calls
    ) == 1

    workflow_input = (
        workflow.run_calls[0][
            "alert"
        ]
    )

    #
    # RED actual:
    #
    # hoy workflow_input ES directamente
    # NormalizedAlert.
    #
    assert (
        type(workflow_input).__name__
        == "IncidentWorkflowInput"
    )

    assert (
        workflow_input.alert
        is alert
    )

    assert (
        workflow_input.conversation_id
        == CONVERSATION_ID
    )

    #
    # La identidad/tenant del operador continúa
    # perteneciendo al boundary Teams.
    #
    assert not hasattr(
        workflow_input,
        "tenant_id",
    )


# TDD_PHASE18_HOST_VALID_NORMALIZED_ALERT_FIX
def _create_host_normalized_alert():
    """
    NormalizedAlert mínima para tests del host.

    El producto mantiene la frontera tipada:
    IncidentWorkflowInput no acepta object().
    """

    from src.workflows.incident_resolution.alert_models import (
        NormalizedAlert,
    )

    return NormalizedAlert(
        alert_id="ALT-HOST-TEST-001",
        source="azure_monitor",
        name="Host test alert",
        description=(
            "Typed synthetic alert used only "
            "by incident workflow host tests."
        ),
        affected_resource="vm-test",
        resource_type=(
            "Microsoft.Compute/"
            "virtualMachines"
        ),
        subscription_id="sub-test",
        resource_group="rg-test",
        vm_name="vm-test",
    )
