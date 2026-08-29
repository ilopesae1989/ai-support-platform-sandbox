from __future__ import annotations

from dataclasses import (
    dataclass,
)

from types import (
    SimpleNamespace,
)

import pytest

from microsoft_teams.api import (
    AdaptiveCardActionMessageResponse,
    AdaptiveCardInvokeActivity,
)

from src.channels.teams.approval_authorization import (
    ExactTeamsApprovalPolicy,
    TeamsApprovalPrincipal,
)

from src.channels.teams.incident_approval_handoff_handler import (
    TeamsApprovalHandlerDependencies,
    handle_teams_approval_action,
)

from src.channels.teams.incident_continuation_store import (
    IncidentContinuationStatus,
    SqliteIncidentContinuationStore,
)

from src.channels.teams.incident_continuation_worker import (
    IncidentContinuationWorker,
    IncidentContinuationWorkerDependencies,
    IncidentContinuationWorkerOutcome,
)

from src.channels.teams import (
    incident_terminal_presenter
    as terminal_presenter_module,
)

from src.channels.teams.incident_terminal_presenter import (
    notify_teams_incident_terminal_result,
)

from src.runtime.procedure.approval_correlation import (
    PendingApprovalCorrelation,
)

from src.runtime.procedure.approval_store import (
    SqlitePendingApprovalStore,
)

from src.runtime.procedure.models import (
    ApprovalStatus,
    OperationKind,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
    StepEvidence,
    StepStatus,
    WorkflowStatus,
)

from tests.channels.teams.test_activity_identity import (
    AAD_OBJECT_ID,
    CONVERSATION_ID,
    TENANT_ID,
    create_activity,
)


APPROVAL_ID = (
    "apr-post-ack-e2e-local-001"
)

WORKFLOW_ID = (
    "wf-post-ack-e2e-local-001"
)

REQUEST_ID = (
    "req-post-ack-e2e-local-001"
)

CHECKPOINT_ID = (
    "cp-post-ack-e2e-local-001"
)


@dataclass
class FakeActivityContext:
    activity: AdaptiveCardInvokeActivity


def _terminal_state():
    return ProcedureRuntimeState(
        workflow_id=WORKFLOW_ID,

        alert_id=(
            "alert-post-ack-e2e-local-001"
        ),

        approval_id=APPROVAL_ID,

        conversation_id=(
            CONVERSATION_ID
        ),

        procedure=ProcedureReference(
            id=(
                "PROC-POST-ACK-E2E-001"
            ),

            name=(
                "Procedimiento local E2E"
            ),

            version="1.0",
        ),

        total_steps=1,

        current_step=1,

        step=ProcedureStep(
            id="step-1",

            description=(
                "Operación local simulada"
            ),

            step_type=(
                "azure_operation"
            ),

            operation_domain="azure",

            operation_kind=(
                OperationKind.WRITE
            ),
        ),

        workflow_status=(
            WorkflowStatus.RESOLVED
        ),

        step_status=(
            StepStatus.SUCCEEDED
        ),

        approval_status=(
            ApprovalStatus.APPROVED
        ),

        verification_result=(
            StepEvidence(
                success=True,

                result={
                    "source":
                        "local-post-ack-e2e",

                    "verified":
                        True,
                },
            )
        ),
    )


@pytest.mark.asyncio
async def test_post_ack_channel_e2e_exactly_once(
    tmp_path,
    monkeypatch,
):
    #
    # --------------------------------------------
    # Durable stores reales.
    # --------------------------------------------
    #
    approval_store = (
        SqlitePendingApprovalStore(
            tmp_path
            / "pending-approval.db"
        )
    )

    continuation_store = (
        SqliteIncidentContinuationStore(
            tmp_path
            / "continuation.db"
        )
    )

    approval_store.register(
        PendingApprovalCorrelation(
            approval_id=(
                APPROVAL_ID
            ),

            workflow_id=(
                WORKFLOW_ID
            ),

            request_id=(
                REQUEST_ID
            ),

            checkpoint_id=(
                CHECKPOINT_ID
            ),
        )
    )

    #
    # --------------------------------------------
    # Activity Action.Execute real del SDK.
    # --------------------------------------------
    #
    activity = create_activity(
        tenant_id=TENANT_ID,

        aad_object_id=(
            AAD_OBJECT_ID
        ),

        conversation_id=(
            CONVERSATION_ID
        ),

        action_data={
            "action":
                "approval_decision",

            "approval_id":
                APPROVAL_ID,

            "decision":
                "approve",
        },
    )

    ctx = FakeActivityContext(
        activity=activity
    )

    policy = (
        ExactTeamsApprovalPolicy(
            policy_id=(
                "teams-hitl-e2e-local-v1"
            ),

            allowed_principals=(
                TeamsApprovalPrincipal(
                    tenant_id=(
                        TENANT_ID
                    ),

                    aad_object_id=(
                        AAD_OBJECT_ID
                    ),
                ),
            ),
        )
    )

    #
    # Este processor NO debe ejecutarse dentro
    # del Action.Execute.
    #
    def should_never_run_in_handler(
        **kwargs,
    ):
        raise AssertionError(
            "El processor no debe ejecutarse "
            "dentro del Action.Execute."
        )

    dependencies = (
        TeamsApprovalHandlerDependencies(
            policy=policy,

            store=(
                approval_store
            ),

            continuation_store=(
                continuation_store
            ),

            workflow_factory=(
                lambda: object()
            ),

            processor=(
                should_never_run_in_handler
            ),
        )
    )

    #
    # --------------------------------------------
    # 1. ACTION.EXECUTE -> ACK.
    # --------------------------------------------
    #
    response = await (
        handle_teams_approval_action(
            ctx=ctx,

            dependencies=(
                dependencies
            ),
        )
    )

    assert isinstance(
        response,
        AdaptiveCardActionMessageResponse,
    )

    assert response.status_code == 200

    assert (
        "Aprobación registrada"
        in response.value
    )

    #
    # ACK ya existe, pero approval todavía
    # NO fue consumida.
    #
    assert (
        approval_store
        .get_consumption_record(
            APPROVAL_ID
        )
        == (
            "pending",
            None,
        )
    )

    queued = (
        continuation_store.get(
            APPROVAL_ID
        )
    )

    assert (
        queued.status
        == IncidentContinuationStatus
        .PENDING
    )

    assert queued.attempt_count == 0

    #
    # --------------------------------------------
    # 2. WORKER POST-ACK.
    # --------------------------------------------
    #
    processor_calls = []
    proactive_calls = []

    async def fake_processor(
        *,
        invocation,
        store,
        workflow,
    ):
        processor_calls.append(
            invocation
            .action
            .approval_id
        )

        assert (
            invocation
            .action
            .approval_id
            == APPROVAL_ID
        )

        assert (
            invocation
            .operator
            .conversation_id
            == CONVERSATION_ID
        )

        #
        # Simula exactamente la frontera
        # durable del incident processor:
        # claim -> trabajo -> complete.
        #
        store.claim(
            approval_id=(
                APPROVAL_ID
            ),

            approved=True,
        )

        result = SimpleNamespace(
            workflow_result=(
                _terminal_state()
            )
        )

        store.complete(
            APPROVAL_ID
        )

        return result

    async def fake_send_teams_message(
        *,
        dependencies,
        tenant_id,
        conversation_id,
        text,
    ):
        proactive_calls.append(
            {
                "tenant_id":
                    tenant_id,

                "conversation_id":
                    conversation_id,

                "text":
                    text,
            }
        )

        return (
            "fake-proactive-send-ok"
        )

    monkeypatch.setattr(
        terminal_presenter_module,
        "send_teams_message",
        fake_send_teams_message,
    )

    async def terminal_notifier(
        *,
        invocation,
        processed,
    ):
        return await (
            notify_teams_incident_terminal_result(
                invocation=(
                    invocation
                ),

                processed=(
                    processed
                ),

                outbound=object(),
            )
        )

    worker = (
        IncidentContinuationWorker(
            IncidentContinuationWorkerDependencies(
                continuation_store=(
                    continuation_store
                ),

                approval_store=(
                    approval_store
                ),

                workflow_factory=(
                    lambda: (
                        "fake-workflow"
                    )
                ),

                processor=(
                    fake_processor
                ),

                terminal_notifier=(
                    terminal_notifier
                ),

                worker_id=(
                    "worker-e2e-local"
                ),
            )
        )
    )

    outcome = await (
        worker.process_next_once()
    )

    assert (
        outcome
        == IncidentContinuationWorkerOutcome
        .COMPLETED
    )

    #
    # --------------------------------------------
    # 3. EXACTAMENTE UNA EJECUCIÓN.
    # --------------------------------------------
    #
    assert processor_calls == [
        APPROVAL_ID
    ]

    assert len(
        proactive_calls
    ) == 1

    sent = proactive_calls[0]

    assert (
        sent["tenant_id"]
        == TENANT_ID
    )

    assert (
        sent["conversation_id"]
        == CONVERSATION_ID
    )

    assert (
        "Incidencia resuelta"
        in sent["text"]
    )

    assert (
        "PROC-POST-ACK-E2E-001"
        in sent["text"]
    )

    #
    # Ninguna autoridad operacional debe
    # filtrarse al mensaje humano.
    #
    lower_message = (
        sent["text"].lower()
    )

    forbidden_human_output = (
        "subscription_id",
        "resource_group",
        "capability_id",
        "resolved_parameters",
        "target_resource",
        "azure.vm.start",
    )

    for token in forbidden_human_output:
        assert token not in lower_message

    #
    # Stores terminales.
    #
    assert (
        approval_store
        .get_consumption_record(
            APPROVAL_ID
        )
        == (
            "completed",
            True,
        )
    )

    completed_job = (
        continuation_store.get(
            APPROVAL_ID
        )
    )

    assert (
        completed_job.status
        == IncidentContinuationStatus
        .COMPLETED
    )

    assert completed_job.attempt_count == 1

    #
    # --------------------------------------------
    # 4. SEGUNDA PASADA DEL WORKER.
    # --------------------------------------------
    #
    second_outcome = await (
        worker.process_next_once()
    )

    assert (
        second_outcome
        == IncidentContinuationWorkerOutcome
        .IDLE
    )

    assert processor_calls == [
        APPROVAL_ID
    ]

    assert len(
        proactive_calls
    ) == 1

    #
    # --------------------------------------------
    # 5. RETRY EXACTO DE ACTION.EXECUTE.
    #
    # El enqueue es idempotente. No crea una
    # segunda unidad de trabajo.
    # --------------------------------------------
    #
    retry_response = await (
        handle_teams_approval_action(
            ctx=ctx,

            dependencies=(
                dependencies
            ),
        )
    )

    assert isinstance(
        retry_response,
        AdaptiveCardActionMessageResponse,
    )

    assert retry_response.status_code == 200

    assert (
        continuation_store
        .get(
            APPROVAL_ID
        )
        .status
        == IncidentContinuationStatus
        .COMPLETED
    )

    third_outcome = await (
        worker.process_next_once()
    )

    assert (
        third_outcome
        == IncidentContinuationWorkerOutcome
        .IDLE
    )

    assert processor_calls == [
        APPROVAL_ID
    ]

    assert len(
        proactive_calls
    ) == 1