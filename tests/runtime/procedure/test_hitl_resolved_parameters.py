import pytest

from src.runtime.procedure.models import (
    ApprovedProcedureStep,
    OperationKind,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
    ResolvedParameter,
)

from src.runtime.procedure.workflow import (
    build_procedure_approval_workflow,
)


SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
)


def create_runtime_state() -> (
    ProcedureRuntimeState
):
    return ProcedureRuntimeState(
        workflow_id=(
            "wf-ALT-AZ-RG-LIST-001"
        ),

        alert_id=(
            "ALT-AZ-RG-LIST-001"
        ),

        conversation_id=(
            "conv-azure-rg-list-001"
        ),

        procedure=ProcedureReference(
            id="NTTSY-SBX-AZ-001",
            name=(
                "Consulta de Resource Groups "
                "de una suscripción Azure"
            ),
            version="v1.0",
        ),

        total_steps=1,
        current_step=1,

        step=ProcedureStep(
            id="1",

            description=(
                "Consultar los Resource Groups "
                "de la suscripción autorizada."
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
                "Lista de Resource Groups "
                "visibles."
            ),

            verification=(
                "Validar que únicamente se "
                "devuelve información de la "
                "suscripción autorizada."
            ),
        ),

        resolved_parameters=[
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
        ],
    )


@pytest.mark.asyncio
async def test_hitl_preserves_resolved_parameters_exactly():
    """
    Demuestra el recorrido completo:

        ProcedureRuntimeState
            ↓
        HITL request
            ↓
        approved=True
            ↓
        ApprovedProcedureStep

    El parámetro concreto aprobado debe llegar
    intacto después de HITL.
    """

    workflow = (
        build_procedure_approval_workflow()
    )

    pending_responses = {}

    approval_request = None

    #
    # --------------------------------------------------
    # Primera ejecución:
    # ProcedureRuntimeState -> HITL
    # --------------------------------------------------
    #

    async for event in workflow.run(
        create_runtime_state(),
        stream=True,
    ):
        if event.type == "request_info":
            approval_request = (
                event.data
                if hasattr(event, "data")
                else None
            )

            pending_responses[
                event.request_id
            ] = True

    assert len(
        pending_responses
    ) == 1

    #
    # --------------------------------------------------
    # Segunda ejecución:
    # aprobar HITL
    # --------------------------------------------------
    #

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

    approved_step = outputs[0]

    assert isinstance(
        approved_step,
        ApprovedProcedureStep,
    )

    #
    # --------------------------------------------------
    # Identidad principal
    # --------------------------------------------------
    #

    assert (
        approved_step.workflow_id
        == "wf-ALT-AZ-RG-LIST-001"
    )

    assert (
        approved_step.alert_id
        == "ALT-AZ-RG-LIST-001"
    )

    assert (
        approved_step.procedure_id
        == "NTTSY-SBX-AZ-001"
    )

    assert (
        approved_step.procedure_version
        == "v1.0"
    )

    assert approved_step.current_step == 1

    assert approved_step.step_id == "1"

    assert (
        approved_step.operation_domain
        == "azure"
    )

    assert (
        approved_step.operation_kind
        == OperationKind.READ
    )

    assert (
        approved_step.target_resource
        == "subscription"
    )

    #
    # --------------------------------------------------
    # Contrato Procedure
    # --------------------------------------------------
    #

    assert (
        approved_step.required_parameters
        == [
            "subscription_id",
        ]
    )

    #
    # --------------------------------------------------
    # Parámetro concreto aprobado
    # --------------------------------------------------
    #

    assert len(
        approved_step.resolved_parameters
    ) == 1

    resolved = (
        approved_step.resolved_parameters[0]
    )

    assert (
        resolved.name
        == "subscription_id"
    )

    assert (
        resolved.value
        == SUBSCRIPTION_ID
    )

    assert (
        resolved.source
        == (
            "normalized_alert."
            "subscription_id"
        )
    )

    #
    # La frontera post-HITL debe marcar
    # explícitamente aprobación válida.
    #
    assert approved_step.approved is True