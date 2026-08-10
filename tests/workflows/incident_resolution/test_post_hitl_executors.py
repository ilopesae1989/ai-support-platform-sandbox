import pytest

from agent_framework import WorkflowBuilder

from src.runtime.procedure.models import (
    ApprovedProcedureStep,
    NextAction,
    OperationKind,
)
from src.workflows.incident_resolution.executors.post_hitl import (
    AzureRouteExecutor,
    DatabaseRouteExecutor,
    PostHitlRouteResult,
)


def create_step(
    *,
    domain: str,
) -> ApprovedProcedureStep:
    return ApprovedProcedureStep(
        workflow_id="wf-001",
        approval_id="apr-post-hitl-001",
        alert_id="ALT-001",
        procedure_id="PROC-001",
        procedure_version="v1.0",
        current_step=1,
        step_id="1",
        operation_domain=domain,
        operation_kind=OperationKind.READ,
        next_action=(
            NextAction.EXECUTE_STEP
        ),
        target_resource="resource-01",
        required_parameters=[],
        approved=True,
    )


@pytest.mark.asyncio
async def test_azure_placeholder_yields_route_result():
    executor = AzureRouteExecutor()

    workflow = (
        WorkflowBuilder(
            start_executor=executor,
            output_from=[executor],
            name="test-azure-route",
        )
        .build()
    )

    outputs = []

    async for event in workflow.run(
        create_step(
            domain="azure"
        ),
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
        PostHitlRouteResult,
    )

    assert result.route == "azure"

    assert (
        result.target_resource
        == "resource-01"
    )


@pytest.mark.asyncio
async def test_database_placeholder_yields_route_result():
    executor = DatabaseRouteExecutor()

    workflow = (
        WorkflowBuilder(
            start_executor=executor,
            output_from=[executor],
            name="test-database-route",
        )
        .build()
    )

    outputs = []

    async for event in workflow.run(
        create_step(
            domain="database"
        ),
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
        PostHitlRouteResult,
    )

    assert result.route == "database"