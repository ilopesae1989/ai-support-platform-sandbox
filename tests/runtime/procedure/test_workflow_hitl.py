import pytest

from src.runtime.procedure.models import (
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
        conversation_id="conv-hitl-001",
        alert_id="ALT-SQL-AG-001",
        procedure=ProcedureReference(
            id="NTTSY-PRO-020",
            name="Alertas SQL Server",
            version="v1.1",
        ),
        total_steps=5,
        current_step=1,
        step=ProcedureStep(
            id="1",
            description=(
                "Comprobar el estado actual de la réplica de Always On."
            ),
            step_type="validation",
            operation_domain="database",
            operation_kind=OperationKind.READ,
            target_resource="SQLPROD01",
            expected_result=(
                "El estado actual de sincronización queda identificado."
            ),
            verification=(
                "Validar el estado mediante el mecanismo "
                "indicado en el procedimiento."
            ),
        ),
    )


@pytest.mark.asyncio
async def test_workflow_requests_human_approval():
    workflow = build_procedure_approval_workflow()
    state = create_always_on_state()

    stream = workflow.run(
        state,
        stream=True,
    )

    requests = []

    async for event in stream:
        if event.type == "request_info":
            requests.append(event)

    assert len(requests) == 1

    request_event = requests[0]

    assert isinstance(request_event.data, ApprovalRequest)
    assert request_event.data.workflow_id == "wf-hitl-001"
    assert request_event.data.procedure_id == "NTTSY-PRO-020"
    assert request_event.data.current_step == 1
    assert request_event.data.operation_domain == "database"
    assert request_event.data.operation_kind == "read"
    assert request_event.data.target_resource == "SQLPROD01"


@pytest.mark.asyncio
async def test_workflow_resumes_after_approval():
    workflow = build_procedure_approval_workflow()
    state = create_always_on_state()

    stream = workflow.run(
        state,
        stream=True,
    )

    pending_responses = {}

    async for event in stream:
        if event.type == "request_info":
            pending_responses[event.request_id] = True

    assert len(pending_responses) == 1

    stream = workflow.run(
        stream=True,
        responses=pending_responses,
    )

    outputs = []

    async for event in stream:
        if event.type == "output":
            outputs.append(event.data)

    assert len(outputs) == 1

    result = outputs[0]

    assert isinstance(result, ApprovalOutcome)
    assert result.workflow_id == "wf-hitl-001"
    assert result.approved is True
    assert result.status == "running"


@pytest.mark.asyncio
async def test_workflow_blocks_after_rejection():
    workflow = build_procedure_approval_workflow()
    state = create_always_on_state()

    stream = workflow.run(
        state,
        stream=True,
    )

    pending_responses = {}

    async for event in stream:
        if event.type == "request_info":
            pending_responses[event.request_id] = False

    assert len(pending_responses) == 1

    stream = workflow.run(
        stream=True,
        responses=pending_responses,
    )

    outputs = []

    async for event in stream:
        if event.type == "output":
            outputs.append(event.data)

    assert len(outputs) == 1

    result = outputs[0]

    assert isinstance(result, ApprovalOutcome)
    assert result.workflow_id == "wf-hitl-001"
    assert result.approved is False
    assert result.status == "blocked"