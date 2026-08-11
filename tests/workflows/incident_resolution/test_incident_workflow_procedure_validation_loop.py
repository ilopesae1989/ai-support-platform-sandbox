import json

import pytest

from src.agents.contracts import (
    ProcedureValidationEscalation,
    ProcedureValidationResult,
)

from src.runtime.procedure.models import (
    ProcedureRuntimeState,
    StepStatus,
    WorkflowStatus,
)

from src.workflows.incident_resolution.azure_operations_models import (
    AzureOperationResult,
)

from src.workflows.incident_resolution.workflow import (
    build_incident_resolution_workflow,
)

from tests.workflows.incident_resolution.test_incident_workflow import (
    create_alert,
)

from tests.workflows.incident_resolution.test_incident_workflow_azure_operations import (
    AzureWorkflowFakeFoundryAgents,
)


class ValidationLoopFakeFoundryAgents(
    AzureWorkflowFakeFoundryAgents
):
    """
    Fake E2E offline para FASE 16.8.

    Sólo sustituye llamadas remotas:

    - agentes cognitivos previos;
    - Azure Operations;
    - Procedure Validation.

    Workflow, HITL, routing, lifecycle,
    correlación y Transition Gate son reales.
    """

    def __init__(
        self,
    ) -> None:
        super().__init__()

        self.procedure_validation_prompt: (
            str | None
        ) = None

    async def run_procedure_validation(
        self,
        message: str,
    ) -> ProcedureValidationResult:
        self.calls.append(
            "procedure_validation"
        )

        self.procedure_validation_prompt = (
            message
        )

        payload = json.loads(
            message
        )

        operation_id = (
            payload[
                "trusted_identity"
            ][
                "operation_id"
            ]
        )

        return ProcedureValidationResult(
            operation_id=operation_id,

            validation_status=(
                "satisfied"
            ),

            proposed_next_action=(
                "continue"
            ),

            validation_summary=(
                "El resultado operacional "
                "satisface el criterio del "
                "procedimiento."
            ),

            escalation=(
                ProcedureValidationEscalation(
                    required=False
                )
            ),
        )


async def run_until_approval(
    workflow,
):
    pending_responses = {}

    async for event in workflow.run(
        create_alert(),
        stream=True,
    ):
        if (
            event.type
            == "request_info"
        ):
            pending_responses[
                event.request_id
            ] = True

    assert len(
        pending_responses
    ) == 1

    return pending_responses


@pytest.mark.asyncio
async def test_approved_azure_operation_reaches_procedure_validation():
    """
    RED 16.8.3

    El AzureOperationResult NO puede terminar
    el workflow.

    Debe alcanzar Procedure Validation.
    """

    agents = (
        ValidationLoopFakeFoundryAgents()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    pending_responses = (
        await run_until_approval(
            workflow
        )
    )

    async for _ in workflow.run(
        responses=pending_responses,
        stream=True,
    ):
        pass

    assert agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
        "azure_operations",
        "procedure_validation",
    ]

    assert (
        agents.calls.count(
            "azure_operations"
        )
        == 1
    )

    assert (
        agents.calls.count(
            "procedure_validation"
        )
        == 1
    )

    assert (
        agents.procedure_validation_prompt
        is not None
    )


@pytest.mark.asyncio
async def test_integrated_workflow_outputs_transitioned_runtime_state():
    """
    La salida integrada de FASE 16 debe ser
    el ProcedureRuntimeState posterior al
    Transition Gate.

    AzureOperationResult deja de ser terminal.
    """

    agents = (
        ValidationLoopFakeFoundryAgents()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    pending_responses = (
        await run_until_approval(
            workflow
        )
    )

    outputs = []

    async for event in workflow.run(
        responses=pending_responses,
        stream=True,
    ):
        if (
            event.type
            == "output"
        ):
            outputs.append(
                event.data
            )

    assert len(
        outputs
    ) == 1

    result = outputs[0]

    assert isinstance(
        result,
        ProcedureRuntimeState,
    )

    assert not isinstance(
        result,
        AzureOperationResult,
    )

    assert (
        result.step_status
        == StepStatus.SUCCEEDED
    )

    assert (
        result.workflow_status
        == WorkflowStatus.RUNNING
    )

    assert (
        result.operation_result
        is not None
    )

    assert (
        result.verification_result
        is not None
    )


@pytest.mark.asyncio
async def test_validation_receives_exact_operation_identity_from_azure():
    """
    La identidad creada antes de Azure debe
    atravesar:

        Azure Operations
            ↓
        OperationResultRegistration
            ↓
        ProcedureValidationExecutor

    sin reconstrucción cognitiva.
    """

    agents = (
        ValidationLoopFakeFoundryAgents()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    pending_responses = (
        await run_until_approval(
            workflow
        )
    )

    outputs = []

    async for event in workflow.run(
        responses=pending_responses,
        stream=True,
    ):
        if (
            event.type
            == "output"
        ):
            outputs.append(
                event.data
            )

    assert (
        agents.procedure_validation_prompt
        is not None
    )

    payload = json.loads(
        agents.procedure_validation_prompt
    )

    trusted_identity = (
        payload[
            "trusted_identity"
        ]
    )

    assert (
        trusted_identity[
            "alert_id"
        ]
        == "ALT-SQL-AG-001"
    )

    assert (
        trusted_identity[
            "procedure_id"
        ]
        == "NTTSY-PRO-016"
    )

    assert (
        trusted_identity[
            "procedure_version"
        ]
        == "v1.1"
    )

    assert (
        trusted_identity[
            "current_step"
        ]
        == 1
    )

    assert (
        trusted_identity[
            "step_id"
        ]
        == "1"
    )

    operation_result = (
        payload[
            "operation_result"
        ]
    )

    assert (
        trusted_identity[
            "operation_id"
        ]
        ==
        operation_result[
            "operation_id"
        ]
    )

    assert (
        trusted_identity[
            "workflow_id"
        ]
        ==
        operation_result[
            "workflow_id"
        ]
    )

    assert (
        trusted_identity[
            "approval_id"
        ]
        ==
        operation_result[
            "approval_id"
        ]
    )


@pytest.mark.asyncio
async def test_transition_occurs_after_azure_and_validation_exactly_once():
    """
    Test de orden del loop.

    No puede existir validación antes de Azure
    ni una segunda interpretación cognitiva.
    """

    agents = (
        ValidationLoopFakeFoundryAgents()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    pending_responses = (
        await run_until_approval(
            workflow
        )
    )

    outputs = []

    async for event in workflow.run(
        responses=pending_responses,
        stream=True,
    ):
        if (
            event.type
            == "output"
        ):
            outputs.append(
                event.data
            )

    assert (
        agents.calls.index(
            "azure_operations"
        )
        <
        agents.calls.index(
            "procedure_validation"
        )
    )

    assert (
        agents.calls.count(
            "procedure_execution"
        )
        == 1
    )

    assert (
        agents.calls.count(
            "azure_operations"
        )
        == 1
    )

    assert (
        agents.calls.count(
            "procedure_validation"
        )
        == 1
    )

    assert len(
        outputs
    ) == 1
