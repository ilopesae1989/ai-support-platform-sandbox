import pytest

from pydantic import (
    ValidationError,
)

from importlib import (
    import_module,
)

from src.agents.contracts import (
    ProcedureValidationEscalation,
    ProcedureValidationResult,
)

from src.runtime.procedure.models import (
    NextAction,
    OperationKind,
    ResolvedParameter,
)

from src.workflows.incident_resolution.operation_models import (
    OperationResult,
)

from src.workflows.incident_resolution.procedure_validation_models import (
    ProcedureValidationContext,
    ProcedureValidationRequest,
    ProcedureValidationStep,
)


OPERATION_ID = (
    "op-procedure-validation-executor-001"
)

WORKFLOW_ID = (
    "wf-procedure-validation-executor-001"
)

APPROVAL_ID = (
    "apr-procedure-validation-executor-001"
)

ALERT_ID = (
    "ALT-AZ-RG-LIST-001"
)

CORRELATION_ID = (
    "corr-procedure-validation-executor-001"
)

CONVERSATION_ID = (
    "conv-procedure-validation-executor-001"
)

PROCEDURE_ID = (
    "NTTSY-SBX-AZ-001"
)

PROCEDURE_VERSION = "v1.0"

SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
)


def get_executor_type():
    module = import_module(
        "src.workflows."
        "incident_resolution."
        "executors."
        "procedure_validation"
    )

    return (
        module
        .ProcedureValidationExecutor
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


def create_operation_result():
    return OperationResult(
        operation_id=(
            OPERATION_ID
        ),

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

        target_resource="subscription",

        required_parameters=[
            "subscription_id",
        ],

        resolved_parameters=(
            resolved_parameters()
        ),

        success=True,

        technical_success=None,

        response_text=(
            "Resource Groups recuperados."
        ),

        error=None,

        evidence=None,
    )


def create_request():
    return ProcedureValidationRequest(
        operation_result=(
            create_operation_result()
        ),

        step=ProcedureValidationStep(
            procedure_id=(
                PROCEDURE_ID
            ),

            procedure_version=(
                PROCEDURE_VERSION
            ),

            current_step=1,

            step_id="1",

            description=(
                "Consultar Resource Groups "
                "de la suscripción."
            ),

            expected_result=(
                "Lista de Resource Groups."
            ),

            verification=(
                "Validar que la respuesta "
                "corresponde a la suscripción."
            ),
        ),
    )


def create_validation_result(
    *,
    operation_id=OPERATION_ID,
    status="satisfied",
    action="continue",
):
    return ProcedureValidationResult(
        operation_id=(
            operation_id
        ),

        validation_status=(
            status
        ),

        proposed_next_action=(
            action
        ),

        validation_summary=(
            "El resultado ha sido "
            "interpretado según "
            "el procedimiento."
        ),

        escalation=(
            ProcedureValidationEscalation(
                required=False
            )
        ),
    )


class FakeFoundryAgents:
    def __init__(
        self,
        result,
    ):
        self.result = result
        self.calls = []

    async def run_procedure_validation(
        self,
        message: str,
    ):
        self.calls.append(
            message
        )

        return self.result


class FakeWorkflowContext:
    def __init__(self):
        self.messages = []

    async def send_message(
        self,
        message,
    ):
        self.messages.append(
            message
        )


@pytest.mark.asyncio
async def test_executor_calls_procedure_validation_once_and_emits_context():
    request = (
        create_request()
    )

    agents = FakeFoundryAgents(
        create_validation_result()
    )

    ctx = FakeWorkflowContext()

    executor = (
        get_executor_type()(
            agents
        )
    )

    await executor.handle(
        request,
        ctx,
    )

    assert len(
        agents.calls
    ) == 1

    assert len(
        ctx.messages
    ) == 1

    assert isinstance(
        ctx.messages[0],
        ProcedureValidationContext,
    )

    assert (
        ctx.messages[0].request
        == request
    )

    assert (
        ctx.messages[0]
        .result
        .operation_id
        == OPERATION_ID
    )


@pytest.mark.asyncio
async def test_executor_prompt_declares_validation_mode_and_trusted_identity():
    request = (
        create_request()
    )

    agents = FakeFoundryAgents(
        create_validation_result()
    )

    ctx = FakeWorkflowContext()

    await get_executor_type()(
        agents
    ).handle(
        request,
        ctx,
    )

    prompt = (
        agents.calls[0]
    )

    assert (
        "validate_result"
        in prompt
    )

    assert (
        OPERATION_ID
        in prompt
    )

    assert (
        WORKFLOW_ID
        in prompt
    )

    assert (
        APPROVAL_ID
        in prompt
    )

    assert (
        PROCEDURE_ID
        in prompt
    )

    assert (
        PROCEDURE_VERSION
        in prompt
    )


@pytest.mark.asyncio
async def test_executor_prompt_contains_expected_result_verification_and_real_result():
    request = (
        create_request()
    )

    agents = FakeFoundryAgents(
        create_validation_result()
    )

    ctx = FakeWorkflowContext()

    await get_executor_type()(
        agents
    ).handle(
        request,
        ctx,
    )

    prompt = (
        agents.calls[0]
    )

    assert (
        request.step.expected_result
        in prompt
    )

    assert (
        request.step.verification
        in prompt
    )

    assert (
        request
        .operation_result
        .response_text
        in prompt
    )

    assert (
        '"technical_success": null'
        in prompt.lower()
    )


@pytest.mark.asyncio
async def test_executor_does_not_mutate_request():
    request = (
        create_request()
    )

    before = (
        request.model_dump(
            mode="json"
        )
    )

    agents = FakeFoundryAgents(
        create_validation_result()
    )

    ctx = FakeWorkflowContext()

    await get_executor_type()(
        agents
    ).handle(
        request,
        ctx,
    )

    assert (
        request.model_dump(
            mode="json"
        )
        == before
    )


@pytest.mark.asyncio
async def test_executor_rejects_validation_for_other_operation():
    request = (
        create_request()
    )

    agents = FakeFoundryAgents(
        create_validation_result(
            operation_id=(
                "op-attacker"
            )
        )
    )

    ctx = FakeWorkflowContext()

    with pytest.raises(
        ValidationError,
    ):
        await get_executor_type()(
            agents
        ).handle(
            request,
            ctx,
        )

    assert (
        ctx.messages
        == []
    )


@pytest.mark.asyncio
async def test_executor_does_not_access_or_modify_workflow_state():
    request = (
        create_request()
    )

    agents = FakeFoundryAgents(
        create_validation_result()
    )

    class StateForbiddenContext(
        FakeWorkflowContext
    ):
        def get_state(
            self,
            *args,
            **kwargs,
        ):
            raise AssertionError(
                "ProcedureValidationExecutor "
                "no debe leer workflow state."
            )

        def set_state(
            self,
            *args,
            **kwargs,
        ):
            raise AssertionError(
                "ProcedureValidationExecutor "
                "no debe modificar workflow state."
            )

    ctx = (
        StateForbiddenContext()
    )

    await get_executor_type()(
        agents
    ).handle(
        request,
        ctx,
    )

    assert len(
        ctx.messages
    ) == 1

@pytest.mark.asyncio
async def test_executor_allows_foundry_iq_but_forbids_operational_actions():
    request = (
        create_request()
    )

    agents = FakeFoundryAgents(
        create_validation_result()
    )

    ctx = FakeWorkflowContext()

    await get_executor_type()(
        agents
    ).handle(
        request,
        ctx,
    )

    prompt = (
        agents.calls[0]
    )

    assert (
        "Foundry IQ"
        in prompt
    )

    assert (
        "Do not execute operational actions."
        in prompt
    )

    assert (
        "Do not execute tools or operations."
        not in prompt
    )
