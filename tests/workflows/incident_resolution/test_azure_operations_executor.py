import pytest

from agent_framework import (
    WorkflowBuilder,
)

from src.runtime.procedure.models import (
    ApprovedProcedureStep,
    NextAction,
    OperationKind,
)
from src.workflows.incident_resolution.azure_operations_models import (
    AzureOperationResult,
)
from src.workflows.incident_resolution.executors.azure_operations import (
    AzureOperationsExecutor,
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
            text="Azure operation fake result."
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


def create_step(
    *,
    domain: str = "azure",
    approved: bool = True,
) -> ApprovedProcedureStep:
    return ApprovedProcedureStep(
        workflow_id="wf-azure-001",
        alert_id="ALT-AZ-001",
        conversation_id="conv-001",
        procedure_id="PROC-AZ-001",
        procedure_version="v1.0",
        current_step=1,
        step_id="1",
        operation_domain=domain,
        operation_kind=OperationKind.READ,
        next_action=NextAction.EXECUTE_STEP,
        target_resource=(
            "/subscriptions/sub-001/"
            "resourceGroups/rg-demo"
        ),
        required_parameters=[
            "resource_group=rg-demo",
        ],
        approved=approved,
    )


def build_executor_workflow(
    agents,
):
    executor = AzureOperationsExecutor(
        agents=agents,
    )

    return (
        WorkflowBuilder(
            start_executor=executor,
            output_from=[
                executor,
            ],
            name="azure-operations-test",
        )
        .build()
    )


@pytest.mark.asyncio
async def test_executor_invokes_azure_operations_agent():
    agents = FakeFoundryAgents()

    workflow = build_executor_workflow(
        agents
    )

    outputs = []

    async for event in workflow.run(
        create_step(),
        stream=True,
    ):
        if event.type == "output":
            outputs.append(
                event.data
            )

    assert len(outputs) == 1

    assert len(agents.calls) == 1

    prompt = agents.calls[0]

    assert "wf-azure-001" in prompt
    assert "ALT-AZ-001" in prompt
    assert "PROC-AZ-001" in prompt
    assert "rg-demo" in prompt
    assert "Tipo: read" in prompt

    result = outputs[0]

    assert isinstance(
        result,
        AzureOperationResult,
    )

    assert result.success is True

    assert (
        result.response_text
        == "Azure operation fake result."
    )

    assert result.error is None


@pytest.mark.asyncio
async def test_executor_preserves_operation_identity():
    agents = FakeFoundryAgents()

    workflow = build_executor_workflow(
        agents
    )

    outputs = []

    step = create_step()

    async for event in workflow.run(
        step,
        stream=True,
    ):
        if event.type == "output":
            outputs.append(
                event.data
            )

    assert len(outputs) == 1

    result = outputs[0]

    assert (
        result.workflow_id
        == step.workflow_id
    )

    assert (
        result.alert_id
        == step.alert_id
    )

    assert (
        result.procedure_id
        == step.procedure_id
    )

    assert (
        result.procedure_version
        == step.procedure_version
    )

    assert (
        result.current_step
        == step.current_step
    )

    assert (
        result.step_id
        == step.step_id
    )

    assert (
        result.operation_kind
        == step.operation_kind
    )

    assert (
        result.target_resource
        == step.target_resource
    )


@pytest.mark.asyncio
async def test_executor_fails_closed_when_foundry_fails():
    agents = FailingFoundryAgents()

    workflow = build_executor_workflow(
        agents
    )

    outputs = []

    async for event in workflow.run(
        create_step(),
        stream=True,
    ):
        if event.type == "output":
            outputs.append(
                event.data
            )

    assert len(outputs) == 1

    result = outputs[0]

    assert isinstance(
        result,
        AzureOperationResult,
    )

    assert result.success is False

    assert result.response_text is None

    assert result.error is not None

    assert (
        "Foundry unavailable"
        in result.error
    )


@pytest.mark.asyncio
async def test_executor_rejects_non_azure_step_before_foundry_call():
    agents = FakeFoundryAgents()

    workflow = build_executor_workflow(
        agents
    )

    with pytest.raises(
        ValueError,
        match="dominio Azure",
    ):
        async for _ in workflow.run(
            create_step(
                domain="database"
            ),
            stream=True,
        ):
            pass

    assert agents.calls == []