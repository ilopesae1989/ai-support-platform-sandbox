import pytest

from src.runtime.procedure.models import (
    ApprovedProcedureStep,
    NextAction,
    OperationKind,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
)
from src.runtime.procedure.workflow import (
    ApprovalOutcome,
    ApprovalRequest,
    build_procedure_approval_workflow,
)


def create_always_on_state() -> ProcedureRuntimeState:
    return ProcedureRuntimeState(
        workflow_id="wf-hitl-001",
        alert_id="ALT-SQL-AG-001",
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
                "Comprobar el estado de sincronización "
                "del Availability Group."
            ),
            step_type="validation",
            operation_domain="database",
            operation_kind=OperationKind.READ,
            target_resource="SQLPROD01",
            required_parameters=[],
        ),
    )


@pytest.mark.asyncio
async def test_workflow_requests_human_approval():
    workflow = (
        build_procedure_approval_workflow()
    )

    state = create_always_on_state()

    requests = []

    async for event in workflow.run(
        state,
        stream=True,
    ):
        if event.type == "request_info":
            requests.append(
                event
            )

    assert len(requests) == 1

    request_event = requests[0]

    assert isinstance(
        request_event.data,
        ApprovalRequest,
    )

    request = request_event.data

    assert (
        request.workflow_id
        == state.workflow_id
    )

    assert (
        request.alert_id
        == state.alert_id
    )

    assert (
        request.procedure_id
        == state.procedure.id
    )

    assert (
        request.current_step
        == state.current_step
    )

    assert (
        request.operation_domain
        == state.step.operation_domain
    )

    assert (
        request.operation_kind
        == state.step.operation_kind.value
    )

    assert (
        request.target_resource
        == state.step.target_resource
    )


@pytest.mark.asyncio
async def test_workflow_resumes_after_approval():
    workflow = (
        build_procedure_approval_workflow()
    )

    state = create_always_on_state()

    pending_responses = {}

    async for event in workflow.run(
        state,
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
        ApprovedProcedureStep,
    )

    assert result.approved is True

    assert (
        result.workflow_id
        == state.workflow_id
    )

    assert (
        result.alert_id
        == state.alert_id
    )

    assert (
        result.procedure_id
        == state.procedure.id
    )

    assert (
        result.procedure_version
        == state.procedure.version
    )

    assert (
        result.current_step
        == state.current_step
    )

    assert (
        result.step_id
        == state.step.id
    )

    assert (
        result.operation_domain
        == state.step.operation_domain
    )

    assert (
        result.operation_kind
        == state.step.operation_kind
    )

    assert (
        result.next_action
        == NextAction.EXECUTE_STEP
    )

    assert (
        result.target_resource
        == state.step.target_resource
    )

    assert (
        result.required_parameters
        == state.step.required_parameters
    )


@pytest.mark.asyncio
async def test_workflow_blocks_after_rejection():
    workflow = (
        build_procedure_approval_workflow()
    )

    state = create_always_on_state()

    pending_responses = {}

    async for event in workflow.run(
        state,
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

    assert isinstance(
        result,
        ApprovalOutcome,
    )

    assert result.approved is False

    assert (
        result.workflow_id
        == state.workflow_id
    )

    assert result.status == "blocked"