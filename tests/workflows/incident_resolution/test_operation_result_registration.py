from importlib import (
    import_module,
)

import pytest

from src.runtime.procedure.identity import (
    create_operation_id,
)

from src.runtime.procedure.models import (
    ApprovalStatus,
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

from src.workflows.incident_resolution.operation_evidence import (
    OperationEvidence,
)

from src.workflows.incident_resolution.operation_models import (
    OperationResult,
)

from src.workflows.incident_resolution.procedure_validation_models import (
    ProcedureValidationRequest,
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
    "corr-registration-001"
)

CONVERSATION_ID = (
    "conv-registration-001"
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
    ):
        self.states[
            key
        ] = value

    async def send_message(
        self,
        message,
    ):
        self.messages.append(
            message
        )


def get_executor():
    module = import_module(
        "src.workflows."
        "incident_resolution."
        "executors."
        "operation_result_registration"
    )

    return (
        module
        .OperationResultRegistrationExecutor()
    )


def resolved_parameters():
    return [
        ResolvedParameter(
            name="subscription_id",

            value=(
                SUBSCRIPTION_ID
            ),

            source=(
                "normalized_alert."
                "subscription_id"
            ),
        )
    ]


def create_runtime_state():
    return ProcedureRuntimeState(
        workflow_id=(
            WORKFLOW_ID
        ),

        approval_id=(
            APPROVAL_ID
        ),

        alert_id=(
            ALERT_ID
        ),

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
                "Validar que la respuesta "
                "corresponde a la suscripción."
            ),
        ),

        resolved_parameters=(
            resolved_parameters()
        ),

        workflow_status=(
            WorkflowStatus
            .WAITING_OPERATION
        ),

        step_status=(
            StepStatus.RUNNING
        ),

        approval_status=(
            ApprovalStatus.APPROVED
        ),
    )


def operation_identity():
    return {
        "operation_id": (
            create_operation_id(
                workflow_id=(
                    WORKFLOW_ID
                ),

                approval_id=(
                    APPROVAL_ID
                ),

                alert_id=(
                    ALERT_ID
                ),

                procedure_id=(
                    PROCEDURE_ID
                ),

                current_step=1,
                step_id="1",
            )
        ),

        "workflow_id": (
            WORKFLOW_ID
        ),

        "approval_id": (
            APPROVAL_ID
        ),

        "alert_id": (
            ALERT_ID
        ),

        "correlation_id": (
            CORRELATION_ID
        ),

        "conversation_id": (
            CONVERSATION_ID
        ),

        "procedure_id": (
            PROCEDURE_ID
        ),

        "procedure_version": (
            PROCEDURE_VERSION
        ),

        "current_step": 1,
        "step_id": "1",

        "operation_domain": "azure",

        "operation_kind": (
            OperationKind.READ
        ),

        "next_action": (
            NextAction.EXECUTE_STEP
        ),

        "target_resource": (
            "subscription"
        ),

        "required_parameters": [
            "subscription_id",
        ],

        "resolved_parameters": (
            resolved_parameters()
        ),
    }


def create_evidence():
    return OperationEvidence(
        **operation_identity()
    )


def create_result(
    *,
    success=True,
    include_evidence=True,
):
    evidence = (
        create_evidence()
        if include_evidence
        else None
    )

    return OperationResult(
        **operation_identity(),

        success=success,

        technical_success=(
            evidence
            .derive_technical_success()
            if evidence is not None
            else (
                None
                if success
                else False
            )
        ),

        response_text=(
            "fake Azure response"
            if success
            else None
        ),

        error=(
            None
            if success
            else (
                "RuntimeError: fake "
                "backend failure"
            )
        ),

        evidence=evidence,
    )


def load_stored_state(
    ctx,
):
    return (
        ProcedureRuntimeState
        .model_validate(
            ctx.states[
                PROCEDURE_RUNTIME_STATE_KEY
            ]
        )
    )


@pytest.mark.asyncio
async def test_successful_operation_result_is_registered_and_waits_validation():
    state = (
        create_runtime_state()
    )

    result = (
        create_result(
            success=True
        )
    )

    ctx = FakeWorkflowContext(
        state
    )

    executor = (
        get_executor()
    )

    await executor.handle(
        result,
        ctx,
    )

    stored = (
        load_stored_state(
            ctx
        )
    )

    assert (
        stored.workflow_status
        == WorkflowStatus.WAITING_VALIDATION
    )

    assert (
        stored.step_status
        == StepStatus.WAITING_VALIDATION
    )

    assert (
        stored.operation_result
        is not None
    )

    assert (
        stored.operation_result.success
        is True
    )

    assert len(
        ctx.messages
    ) == 1

    assert isinstance(
        ctx.messages[0],
        ProcedureValidationRequest,
    )


@pytest.mark.asyncio
async def test_backend_failure_still_waits_for_procedure_validation():
    """
    success=False es fallo de backend.

    NO autoriza a Python a declarar que el
    ProcedureStep ha fallado semánticamente.
    """

    state = (
        create_runtime_state()
    )

    result = (
        create_result(
            success=False,
            include_evidence=False,
        )
    )

    ctx = FakeWorkflowContext(
        state
    )

    await get_executor().handle(
        result,
        ctx,
    )

    stored = (
        load_stored_state(
            ctx
        )
    )

    assert (
        stored.workflow_status
        == WorkflowStatus.WAITING_VALIDATION
    )

    assert (
        stored.step_status
        == StepStatus.WAITING_VALIDATION
    )

    assert (
        stored.step_status
        is not StepStatus.FAILED
    )

    assert (
        stored.operation_result
        is not None
    )

    # Conservamos el success operacional.
    assert (
        stored.operation_result.success
        is False
    )

    assert (
        stored.operation_result.error
        ==
        "RuntimeError: fake backend failure"
    )


@pytest.mark.asyncio
async def test_indeterminate_technical_success_is_preserved_for_validation():
    state = (
        create_runtime_state()
    )

    result = (
        create_result(
            success=True,
            include_evidence=True,
        )
    )

    assert (
        result.technical_success
        is None
    )

    ctx = FakeWorkflowContext(
        state
    )

    await get_executor().handle(
        result,
        ctx,
    )

    stored = (
        load_stored_state(
            ctx
        )
    )

    assert (
        stored.operation_result
        is not None
    )

    payload = (
        stored.operation_result.result
    )

    assert (
        payload[
            "technical_success"
        ]
        is None
    )

    request = (
        ctx.messages[0]
    )

    assert (
        request
        .operation_result
        .technical_success
        is None
    )


@pytest.mark.asyncio
async def test_registered_step_evidence_contains_full_operation_result_snapshot():
    state = (
        create_runtime_state()
    )

    result = (
        create_result()
    )

    ctx = FakeWorkflowContext(
        state
    )

    await get_executor().handle(
        result,
        ctx,
    )

    stored = (
        load_stored_state(
            ctx
        )
    )

    evidence = (
        stored.operation_result
    )

    assert evidence is not None

    assert (
        evidence.result
        ==
        result.model_dump(
            mode="json"
        )
    )


@pytest.mark.asyncio
async def test_validation_request_preserves_authoritative_step_semantics():
    state = (
        create_runtime_state()
    )

    result = (
        create_result()
    )

    ctx = FakeWorkflowContext(
        state
    )

    await get_executor().handle(
        result,
        ctx,
    )

    request = (
        ctx.messages[0]
    )

    assert (
        request.step.procedure_id
        == PROCEDURE_ID
    )

    assert (
        request.step.procedure_version
        == PROCEDURE_VERSION
    )

    assert (
        request.step.current_step
        == 1
    )

    assert (
        request.step.step_id
        == "1"
    )

    assert (
        request.step.description
        ==
        state.step.description
    )

    assert (
        request.step.expected_result
        ==
        state.step.expected_result
    )

    assert (
        request.step.verification
        ==
        state.step.verification
    )


@pytest.mark.asyncio
async def test_wrong_result_identity_fails_without_state_mutation_or_output():
    state = (
        create_runtime_state()
    )

    data = (
        create_result()
        .model_dump(
            mode="python"
        )
    )

    data[
        "workflow_id"
    ] = "wf-attacker"

    data[
        "evidence"
    ] = None

    data[
        "technical_success"
    ] = None

    result = (
        OperationResult(
            **data
        )
    )

    original = (
        state.model_dump(
            mode="json"
        )
    )

    ctx = FakeWorkflowContext(
        state
    )

    with pytest.raises(
        ValueError,
    ):
        await get_executor().handle(
            result,
            ctx,
        )

    assert (
        ctx.states[
            PROCEDURE_RUNTIME_STATE_KEY
        ]
        == original
    )

    assert ctx.messages == []


@pytest.mark.asyncio
async def test_missing_authoritative_runtime_fails_closed():
    result = (
        create_result()
    )

    ctx = FakeWorkflowContext(
        None
    )

    with pytest.raises(
        RuntimeError,
    ):
        await get_executor().handle(
            result,
            ctx,
        )

    assert ctx.messages == []

    assert (
        PROCEDURE_RUNTIME_STATE_KEY
        not in ctx.states
    )


@pytest.mark.asyncio
async def test_duplicate_result_is_rejected_without_second_output():
    state = (
        create_runtime_state()
    )

    result = (
        create_result()
    )

    ctx = FakeWorkflowContext(
        state
    )

    executor = (
        get_executor()
    )

    await executor.handle(
        result,
        ctx,
    )

    stored_after_first = (
        ctx.states[
            PROCEDURE_RUNTIME_STATE_KEY
        ]
    )

    assert len(
        ctx.messages
    ) == 1

    with pytest.raises(
        ValueError,
    ):
        await executor.handle(
            result,
            ctx,
        )

    assert (
        ctx.states[
            PROCEDURE_RUNTIME_STATE_KEY
        ]
        == stored_after_first
    )

    assert len(
        ctx.messages
    ) == 1
