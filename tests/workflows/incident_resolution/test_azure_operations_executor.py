import pytest

from agent_framework import (
    WorkflowBuilder,
)

from src.runtime.procedure.models import (
    ApprovedProcedureStep,
    NextAction,
    OperationKind,
    ResolvedParameter,
)

from src.workflows.incident_resolution.azure_operations import (
    build_azure_operation_request,
)

from src.workflows.incident_resolution.azure_operations_models import (
    AzureOperationResult,
    VerifiedAzureOperationRequest,
)

from src.workflows.incident_resolution.executors.azure_operations import (
    AzureOperationsExecutor,
)

from src.workflows.incident_resolution.pre_call_security import (
    PreCallSecurityVerifier,
)


APPROVAL_ID = (
    "apr-11111111-1111-4111-"
    "8111-111111111111"
)

APPROVED_DESCRIPTION = (
    "Consultar el Resource Group rg-demo."
)


class FakeNativeResponse:
    def __init__(
        self,
        text: str | None = None,
    ) -> None:
        self.text = text


class FakeFoundryAgents:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def run_azure_operations(
        self,
        message: str,
    ):
        self.calls.append(
            message
        )

        return FakeNativeResponse(
            text=(
                "Azure operation fake result."
            )
        )


class FailingFoundryAgents:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def run_azure_operations(
        self,
        message: str,
    ):
        self.calls.append(
            message
        )

        raise RuntimeError(
            "Foundry unavailable"
        )


def create_approved_step(
) -> ApprovedProcedureStep:
    return ApprovedProcedureStep(
        workflow_id="wf-azure-001",

        approval_id=(
            APPROVAL_ID
        ),

        alert_id="ALT-AZ-001",

        correlation_id="corr-azure-001",

        conversation_id="conv-001",

        procedure_id="PROC-AZ-001",

        procedure_version="v1.0",

        current_step=1,

        step_id="1",

        description=(
            APPROVED_DESCRIPTION
        ),

        operation_domain="azure",

        operation_kind=(
            OperationKind.READ
        ),

        next_action=(
            NextAction.EXECUTE_STEP
        ),

        target_resource=(
            "/subscriptions/sub-001/"
            "resourceGroups/rg-demo"
        ),

        required_parameters=[
            "resource_group",
        ],

        resolved_parameters=[
            ResolvedParameter(
                name="resource_group",

                value="rg-demo",

                source=(
                    "normalized_alert."
                    "resource_group"
                ),
            )
        ],

        approved=True,
    )


def create_verified_request(
) -> VerifiedAzureOperationRequest:
    step = (
        create_approved_step()
    )

    candidate = (
        build_azure_operation_request(
            step
        )
    )

    return (
        PreCallSecurityVerifier.verify(
            approved_step=step,
            candidate=candidate,
        )
    )


def build_executor_workflow(
    agents,
):
    executor = (
        AzureOperationsExecutor(
            agents=agents,
        )
    )

    return (
        WorkflowBuilder(
            start_executor=executor,

            output_from=[
                executor,
            ],

            name=(
                "azure-operations-test"
            ),
        )
        .build()
    )


@pytest.mark.asyncio
async def test_executor_invokes_azure_operations_agent():
    agents = (
        FakeFoundryAgents()
    )

    workflow = (
        build_executor_workflow(
            agents
        )
    )

    request = (
        create_verified_request()
    )

    outputs = []

    async for event in workflow.run(
        request,
        stream=True,
    ):
        if event.type == "output":
            outputs.append(
                event.data
            )

    assert len(outputs) == 1

    assert len(
        agents.calls
    ) == 1

    prompt = (
        agents.calls[0]
    )

    assert (
        "wf-azure-001"
        in prompt
    )

    assert (
        APPROVAL_ID
        in prompt
    )

    assert (
        "ALT-AZ-001"
        in prompt
    )

    assert (
        "PROC-AZ-001"
        in prompt
    )

    assert (
        APPROVED_DESCRIPTION
        in prompt
    )

    assert (
        "resource_group = rg-demo"
        in prompt
    )

    assert (
        "Tipo: read"
        in prompt
    )

    result = (
        outputs[0]
    )

    assert isinstance(
        result,
        AzureOperationResult,
    )

    assert (
        result.success
        is True
    )

    assert (
        result.response_text
        == "Azure operation fake result."
    )

    assert result.error is None


@pytest.mark.asyncio
async def test_executor_preserves_operation_identity():
    agents = (
        FakeFoundryAgents()
    )

    workflow = (
        build_executor_workflow(
            agents
        )
    )

    request = (
        create_verified_request()
    )

    outputs = []

    async for event in workflow.run(
        request,
        stream=True,
    ):
        if event.type == "output":
            outputs.append(
                event.data
            )

    assert len(outputs) == 1

    result = (
        outputs[0]
    )

    assert (
        result.operation_id
        == request.operation_id
    )

    assert (
        result.workflow_id
        == request.workflow_id
    )

    assert (
        result.approval_id
        == request.approval_id
    )

    assert (
        result.alert_id
        == request.alert_id
    )

    assert (
        result.correlation_id
        == request.correlation_id
    )

    assert (
        result.conversation_id
        == request.conversation_id
    )

    assert (
        result.procedure_id
        == request.procedure_id
    )

    assert (
        result.procedure_version
        == request.procedure_version
    )

    assert (
        result.current_step
        == request.current_step
    )

    assert (
        result.step_id
        == request.step_id
    )

    assert (
        result.operation_kind
        == request.operation_kind
    )

    assert (
        result.target_resource
        == request.target_resource
    )


@pytest.mark.asyncio
async def test_executor_fails_closed_when_foundry_fails():
    agents = (
        FailingFoundryAgents()
    )

    workflow = (
        build_executor_workflow(
            agents
        )
    )

    request = (
        create_verified_request()
    )

    outputs = []

    async for event in workflow.run(
        request,
        stream=True,
    ):
        if event.type == "output":
            outputs.append(
                event.data
            )

    assert len(outputs) == 1

    result = (
        outputs[0]
    )

    assert isinstance(
        result,
        AzureOperationResult,
    )

    assert (
        result.success
        is False
    )

    assert (
        result.response_text
        is None
    )

    assert (
        result.error
        is not None
    )

    assert (
        "Foundry unavailable"
        in result.error
    )