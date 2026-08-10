from importlib import (
    import_module,
)

import pytest

from src.runtime.procedure.models import (
    ApprovalStatus,
    ApprovedProcedureStep,
    NextAction,
    OperationKind,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
    ResolvedParameter,
    StepStatus,
    WorkflowStatus,
)

from src.runtime.procedure.workflow_state import (
    PROCEDURE_RUNTIME_STATE_KEY,
)

from src.workflows.incident_resolution.azure_operations import (
    build_azure_operation_request,
)

from src.workflows.incident_resolution.pre_call_security import (
    PreCallSecurityVerifier,
)


WORKFLOW_ID = (
    "wf-11111111-1111-4111-"
    "8111-111111111111"
)

APPROVAL_ID = (
    "apr-11111111-1111-4111-"
    "8111-111111111111"
)

ALERT_ID = (
    "ALT-AZ-RG-LIST-001"
)

CORRELATION_ID = (
    "corr-operation-start-001"
)

CONVERSATION_ID = (
    "conv-operation-start-001"
)

PROCEDURE_ID = (
    "NTTSY-SBX-AZ-001"
)

PROCEDURE_VERSION = (
    "v1.0"
)

SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
)


class FakeWorkflowContext:
    def __init__(
        self,
        state: ProcedureRuntimeState | None,
    ) -> None:
        self.states = {}
        self.messages = []

        if state is not None:
            self.states[
                PROCEDURE_RUNTIME_STATE_KEY
            ] = state.model_dump(
                mode="json"
            )

    def get_state(
        self,
        key,
        default=None,
    ):
        return self.states.get(
            key,
            default,
        )

    def set_state(
        self,
        key,
        value,
    ) -> None:
        self.states[
            key
        ] = value

    async def send_message(
        self,
        message,
    ) -> None:
        self.messages.append(
            message
        )


def create_runtime_state(
    *,
    workflow_id: str = WORKFLOW_ID,
    approval_id: str = APPROVAL_ID,
    step_status: StepStatus = (
        StepStatus.APPROVED
    ),
    workflow_status: WorkflowStatus = (
        WorkflowStatus.RUNNING
    ),
    approval_status: ApprovalStatus = (
        ApprovalStatus.APPROVED
    ),
) -> ProcedureRuntimeState:
    return ProcedureRuntimeState(
        workflow_id=workflow_id,

        approval_id=approval_id,

        alert_id=ALERT_ID,

        correlation_id=(
            CORRELATION_ID
        ),

        conversation_id=(
            CONVERSATION_ID
        ),

        procedure=ProcedureReference(
            id=PROCEDURE_ID,

            name=(
                "Consulta de Resource Groups"
            ),

            version=(
                PROCEDURE_VERSION
            ),
        ),

        total_steps=1,
        current_step=1,

        step=ProcedureStep(
            id="1",

            description=(
                "Consultar Resource Groups "
                "de la suscripción."
            ),

            step_type=(
                "technical_operation"
            ),

            operation_domain="azure",

            operation_kind=(
                OperationKind.READ
            ),

            target_resource=(
                "subscription"
            ),

            required_parameters=[
                "subscription_id",
            ],

            preconditions=[],

            expected_result=(
                "Lista de Resource Groups."
            ),

            verification=(
                "Validar los Resource Groups "
                "devueltos por Azure."
            ),
        ),

        resolved_parameters=[
            ResolvedParameter(
                name=(
                    "subscription_id"
                ),

                value=(
                    SUBSCRIPTION_ID
                ),

                source=(
                    "normalized_alert."
                    "subscription_id"
                ),
            )
        ],

        workflow_status=(
            workflow_status
        ),

        step_status=(
            step_status
        ),

        approval_status=(
            approval_status
        ),
    )


def create_approved_step():
    return ApprovedProcedureStep(
        workflow_id=WORKFLOW_ID,

        approval_id=APPROVAL_ID,

        alert_id=ALERT_ID,

        correlation_id=(
            CORRELATION_ID
        ),

        conversation_id=(
            CONVERSATION_ID
        ),

        procedure_id=(
            PROCEDURE_ID
        ),

        procedure_version=(
            PROCEDURE_VERSION
        ),

        current_step=1,

        step_id="1",

        operation_domain="azure",

        operation_kind=(
            OperationKind.READ
        ),

        next_action=(
            NextAction.EXECUTE_STEP
        ),

        target_resource=(
            "subscription"
        ),

        required_parameters=[
            "subscription_id",
        ],

        resolved_parameters=[
            ResolvedParameter(
                name=(
                    "subscription_id"
                ),

                value=(
                    SUBSCRIPTION_ID
                ),

                source=(
                    "normalized_alert."
                    "subscription_id"
                ),
            )
        ],

        approved=True,
    )


def create_verified_request():
    approved_step = (
        create_approved_step()
    )

    candidate = (
        build_azure_operation_request(
            approved_step
        )
    )

    return (
        PreCallSecurityVerifier()
        .verify(
            approved_step=(
                approved_step
            ),

            candidate=(
                candidate
            ),
        )
    )


def create_executor():
    """
    Import diferido deliberadamente.

    Permite ejecutar la batería RED antes
    de que exista el nuevo executor.
    """

    module = import_module(
        "src.workflows."
        "incident_resolution."
        "executors."
        "operation_lifecycle"
    )

    return (
        module.OperationStartExecutor()
    )


@pytest.mark.asyncio
async def test_verified_operation_marks_authoritative_runtime_as_waiting_operation():
    """
    FASE 16.2.3

    Un request que:
      - ya atravesó PreCallSecurity;
      - coincide exactamente con el runtime;
      - corresponde al paso aprobado;

    puede provocar:

        APPROVED
            ↓
        RUNNING / WAITING_OPERATION

    antes de llegar al executor operativo.
    """

    state = (
        create_runtime_state()
    )

    verified = (
        create_verified_request()
    )

    ctx = FakeWorkflowContext(
        state
    )

    executor = (
        create_executor()
    )

    await executor.handle(
        verified,
        ctx,
    )

    stored = (
        ProcedureRuntimeState
        .model_validate(
            ctx.states[
                PROCEDURE_RUNTIME_STATE_KEY
            ]
        )
    )

    assert (
        stored.step_status
        == StepStatus.RUNNING
    )

    assert (
        stored.workflow_status
        == WorkflowStatus.WAITING_OPERATION
    )

    assert (
        stored.approval_status
        == ApprovalStatus.APPROVED
    )

    assert (
        stored.approval_id
        == APPROVAL_ID
    )

    assert len(
        ctx.messages
    ) == 1

    # El lifecycle no debe reconstruir,
    # modificar ni sustituir la request.
    assert (
        ctx.messages[0]
        is verified
    )


@pytest.mark.asyncio
async def test_operation_start_fails_closed_without_authoritative_runtime_state():
    """
    Un VerifiedAzureOperationRequest no basta.

    Sin ProcedureRuntimeState autoritativo:
        no hay operación.
    """

    verified = (
        create_verified_request()
    )

    ctx = FakeWorkflowContext(
        None
    )

    executor = (
        create_executor()
    )

    with pytest.raises(
        RuntimeError,
    ):
        await executor.handle(
            verified,
            ctx,
        )

    assert ctx.messages == []

    assert (
        PROCEDURE_RUNTIME_STATE_KEY
        not in ctx.states
    )


@pytest.mark.asyncio
async def test_operation_start_rejects_verified_request_for_different_runtime():
    """
    Aunque el request sea formalmente Verified,
    debe corresponder al runtime ACTIVO.

    Otro workflow no puede iniciar la operación.
    """

    state = (
        create_runtime_state(
            workflow_id=(
                "wf-22222222-2222-4222-"
                "8222-222222222222"
            )
        )
    )

    verified = (
        create_verified_request()
    )

    original_snapshot = (
        state.model_dump(
            mode="json"
        )
    )

    ctx = FakeWorkflowContext(
        state
    )

    executor = (
        create_executor()
    )

    with pytest.raises(
        ValueError,
    ):
        await executor.handle(
            verified,
            ctx,
        )

    assert ctx.messages == []

    assert (
        ctx.states[
            PROCEDURE_RUNTIME_STATE_KEY
        ]
        == original_snapshot
    )


@pytest.mark.asyncio
async def test_operation_start_rejects_runtime_not_in_approved_state():
    """
    PreCallSecurity no sustituye al lifecycle.

    Si el runtime no está APPROVED, la operación
    no puede comenzar aunque exista una request
    verificada.
    """

    state = (
        create_runtime_state(
            step_status=(
                StepStatus.WAITING_APPROVAL
            ),

            workflow_status=(
                WorkflowStatus.WAITING_HUMAN
            ),

            approval_status=(
                ApprovalStatus.PENDING
            ),
        )
    )

    verified = (
        create_verified_request()
    )

    original_snapshot = (
        state.model_dump(
            mode="json"
        )
    )

    ctx = FakeWorkflowContext(
        state
    )

    executor = (
        create_executor()
    )

    with pytest.raises(
        ValueError,
    ):
        await executor.handle(
            verified,
            ctx,
        )

    assert ctx.messages == []

    assert (
        ctx.states[
            PROCEDURE_RUNTIME_STATE_KEY
        ]
        == original_snapshot
    )
