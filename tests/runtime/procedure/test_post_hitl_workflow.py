import pytest

from agent_framework import (
    Case,
    Default,
    WorkflowBuilder,
)

from src.runtime.procedure.models import (
    OperationKind,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
)
from src.runtime.procedure.workflow import (
    ProcedureApprovalExecutor,
)
from src.workflows.incident_resolution.executors.post_hitl import (
    AzureRouteExecutor,
    BlockedRouteExecutor,
    DatabaseRouteExecutor,
    PostHitlRouteResult,
)
from src.workflows.incident_resolution.routing_post_hitl import (
    route_to_azure_operation,
    route_to_database_operation,
)


def create_state(
    *,
    domain: str = "database",
    kind: OperationKind = OperationKind.READ,
) -> ProcedureRuntimeState:
    return ProcedureRuntimeState(
        workflow_id="wf-post-hitl-001",
        alert_id="ALT-SQL-001",
        procedure=ProcedureReference(
            id="NTTSY-PRO-016",
            name="SQL AlwaysOnRol Change Alerta",
            version="v1.1",
        ),
        total_steps=1,
        current_step=1,
        step=ProcedureStep(
            id="1",
            description=(
                "Comprobar el estado de "
                "sincronización del Availability Group."
            ),
            step_type="validation",
            operation_domain=domain,
            operation_kind=kind,
            target_resource="SQLPROD01",
            required_parameters=[],
        ),
    )


def build_test_workflow():
    approval = ProcedureApprovalExecutor()

    azure = AzureRouteExecutor()
    database = DatabaseRouteExecutor()
    blocked = BlockedRouteExecutor()

    return (
    WorkflowBuilder(
        start_executor=approval,
        output_from=[
            approval,
            azure,
            database,
            blocked,
        ],
        name="post-hitl-routing-test",
    )
        .add_switch_case_edge_group(
            approval,
            [
                Case(
                    condition=route_to_azure_operation,
                    target=azure,
                ),
                Case(
                    condition=route_to_database_operation,
                    target=database,
                ),
                Default(
                    target=blocked,
                ),
            ],
        )
        .build()
    )


@pytest.mark.asyncio
async def test_approved_database_step_routes_to_database():
    workflow = build_test_workflow()

    pending_responses = {}

    async for event in workflow.run(
        create_state(
            domain="database"
        ),
        stream=True,
    ):
        if event.type == "request_info":
            pending_responses[
                event.request_id
            ] = True

    assert len(pending_responses) == 1

    outputs = []

    async for event in workflow.run(
        responses=pending_responses,
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

    assert (
        result.workflow_id
        == "wf-post-hitl-001"
    )

    assert (
        result.alert_id
        == "ALT-SQL-001"
    )

    assert (
        result.procedure_id
        == "NTTSY-PRO-016"
    )

    assert result.current_step == 1

    assert result.step_id == "1"

    assert (
        result.operation_kind
        == "read"
    )

    assert (
        result.target_resource
        == "SQLPROD01"
    )


@pytest.mark.asyncio
async def test_approved_azure_step_routes_to_azure():
    workflow = build_test_workflow()

    pending_responses = {}

    async for event in workflow.run(
        create_state(
            domain="azure"
        ),
        stream=True,
    ):
        if event.type == "request_info":
            pending_responses[
                event.request_id
            ] = True

    assert len(pending_responses) == 1

    outputs = []

    async for event in workflow.run(
        responses=pending_responses,
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
        == "SQLPROD01"
    )


@pytest.mark.asyncio
async def test_rejected_step_never_reaches_operational_route():
    workflow = build_test_workflow()

    pending_responses = {}

    async for event in workflow.run(
        create_state(),
        stream=True,
    ):
        if event.type == "request_info":
            pending_responses[
                event.request_id
            ] = False

    assert len(pending_responses) == 1

    outputs = []

    async for event in workflow.run(
        responses=pending_responses,
        stream=True,
    ):
        if event.type == "output":
            outputs.append(
                event.data
            )

    assert len(outputs) == 1

    result = outputs[0]

    #
    # El rechazo termina en ApprovalOutcome.
    # Nunca alcanza Azure/Database/Blocked
    # post-HITL porque no se emite
    # ApprovedProcedureStep.
    #
    assert result.approved is False

    assert (
        result.workflow_id
        == "wf-post-hitl-001"
    )