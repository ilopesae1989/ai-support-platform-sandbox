import pytest

from agent_framework import (
    FileCheckpointStorage,
)

from src.runtime.procedure.models import (
    ApprovedProcedureStep,
    NextAction,
    OperationKind,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
    ResolvedParameter,
)

from src.runtime.procedure.workflow import (
    ApprovalRequest,
    build_procedure_approval_workflow,
)


ALLOWED_CHECKPOINT_TYPES = {
    "src.runtime.procedure.workflow:ApprovalRequest",
    "src.runtime.procedure.workflow:ApprovalOutcome",

    "src.runtime.procedure.models:StepStatus",
    "src.runtime.procedure.models:WorkflowStatus",
    "src.runtime.procedure.models:ApprovalStatus",
    "src.runtime.procedure.models:OperationKind",
    "src.runtime.procedure.models:NextAction",

    "src.runtime.procedure.models:ProcedureReference",
    "src.runtime.procedure.models:ProcedureStep",
    "src.runtime.procedure.models:StepEvidence",
    "src.runtime.procedure.models:ProcedureExecutionResult",
    "src.runtime.procedure.models:ResolvedParameter",
    "src.runtime.procedure.models:ProcedureRuntimeState",
    "src.runtime.procedure.models:ApprovedProcedureStep",
}


WORKFLOW_ID = (
    "wf-checkpoint-001"
)

ALERT_ID = (
    "ALT-SQL-AG-001"
)

CORRELATION_ID = (
    "corr-sql-ag-checkpoint-001"
)

SQL_SERVER_INSTANCE = (
    "SQLPROD01"
)


def create_state() -> ProcedureRuntimeState:
    """
    Estado previo a HITL.

    approval_id todavía NO se fija aquí.

    Debe ser generado exactamente una vez por
    ProcedureApprovalExecutor al entrar en
    WAITING_APPROVAL y posteriormente sobrevivir
    al checkpoint.
    """

    return ProcedureRuntimeState(
        workflow_id=(
            WORKFLOW_ID
        ),

        alert_id=(
            ALERT_ID
        ),

        correlation_id=(
            CORRELATION_ID
        ),

        procedure=ProcedureReference(
            id="NTTSY-PRO-016",

            name=(
                "SQL AlwaysOnRol Change Alerta"
            ),

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

            operation_kind=(
                OperationKind.READ
            ),

            target_resource=(
                SQL_SERVER_INSTANCE
            ),

            required_parameters=[
                "sql_server_instance",
            ],
        ),

        resolved_parameters=[
            ResolvedParameter(
                name=(
                    "sql_server_instance"
                ),

                value=(
                    SQL_SERVER_INSTANCE
                ),

                source=(
                    "normalized_alert."
                    "affected_resource"
                ),
            )
        ],
    )


@pytest.mark.asyncio
async def test_pending_approval_survives_checkpoint(
    tmp_path,
):
    """
    FASE 14.20

    Demuestra:

        ProcedureRuntimeState
              ↓
        HITL pendiente
              ↓
        approval_id generado
              ↓
        CHECKPOINT
              ↓
        reinicio del proceso
              ↓
        RESTORE
              ↓
        mismo request HITL
              ↓
        aprobación
              ↓
        ApprovedProcedureStep

    Deben sobrevivir literalmente:

    - workflow_id;
    - approval_id;
    - alert_id;
    - correlation_id;
    - procedimiento;
    - versión;
    - paso;
    - operación;
    - target_resource;
    - required_parameters;
    - resolved_parameters.
    """

    checkpoint_dir = (
        tmp_path
        / "checkpoints"
    )

    #
    # --------------------------------------------------
    # 1. Primera instancia del workflow
    # --------------------------------------------------
    #

    workflow_a = (
        build_procedure_approval_workflow(
            str(checkpoint_dir)
        )
    )

    state = (
        create_state()
    )

    original_request_id = None
    original_request = None

    async for event in workflow_a.run(
        state,
        stream=True,
    ):
        if event.type == "request_info":
            original_request_id = (
                event.request_id
            )

            original_request = (
                event.data
            )

    assert (
        original_request_id
        is not None
    )

    assert isinstance(
        original_request,
        ApprovalRequest,
    )

    #
    # --------------------------------------------------
    # 2. approval_id fue generado por HITL
    # --------------------------------------------------
    #

    assert (
        original_request.approval_id
    )

    assert (
        original_request.approval_id
        .startswith(
            "apr-"
        )
    )

    #
    # Identidad previa al checkpoint.
    #

    assert (
        original_request.workflow_id
        == WORKFLOW_ID
    )

    assert (
        original_request.alert_id
        == ALERT_ID
    )

    assert (
        original_request.correlation_id
        == CORRELATION_ID
    )

    assert (
        original_request.required_parameters
        == [
            "sql_server_instance",
        ]
    )

    assert (
        original_request.resolved_parameters
        == [
            ResolvedParameter(
                name=(
                    "sql_server_instance"
                ),

                value=(
                    SQL_SERVER_INSTANCE
                ),

                source=(
                    "normalized_alert."
                    "affected_resource"
                ),
            )
        ]
    )

    original_approval_id = (
        original_request.approval_id
    )

    #
    # --------------------------------------------------
    # 3. Localizar checkpoint persistido
    # --------------------------------------------------
    #

    storage = FileCheckpointStorage(
        str(checkpoint_dir),

        allowed_checkpoint_types=(
            ALLOWED_CHECKPOINT_TYPES
        ),
    )

    checkpoints = (
        await storage.list_checkpoints(
            workflow_name=(
                "procedure-runtime"
            )
        )
    )

    assert (
        len(checkpoints)
        > 0
    )

    latest_checkpoint = sorted(
        checkpoints,

        key=lambda checkpoint:
            checkpoint.timestamp,

        reverse=True,
    )[0]

    #
    # --------------------------------------------------
    # 4. Simular reinicio del proceso
    # --------------------------------------------------
    #

    workflow_b = (
        build_procedure_approval_workflow(
            str(checkpoint_dir)
        )
    )

    restored_request_id = None
    restored_request = None

    async for event in workflow_b.run(
        checkpoint_id=(
            latest_checkpoint.checkpoint_id
        ),

        stream=True,
    ):
        if event.type == "request_info":
            restored_request_id = (
                event.request_id
            )

            restored_request = (
                event.data
            )

    assert (
        restored_request_id
        is not None
    )

    assert isinstance(
        restored_request,
        ApprovalRequest,
    )

    #
    # --------------------------------------------------
    # 5. Request HITL original = request restaurado
    # --------------------------------------------------
    #

    assert (
        restored_request_id
        == original_request_id
    )

    #
    # CRÍTICO:
    #
    # no debe generarse un approval_id nuevo.
    #
    assert (
        restored_request.approval_id
        == original_approval_id
    )

    assert (
        restored_request.workflow_id
        == original_request.workflow_id
    )

    assert (
        restored_request.alert_id
        == original_request.alert_id
    )

    assert (
        restored_request.correlation_id
        == original_request.correlation_id
    )

    assert (
        restored_request.procedure_id
        == original_request.procedure_id
    )

    assert (
        restored_request.procedure_version
        == original_request.procedure_version
    )

    assert (
        restored_request.current_step
        == original_request.current_step
    )

    assert (
        restored_request.step_id
        == original_request.step_id
    )

    assert (
        restored_request.operation_domain
        == original_request.operation_domain
    )

    assert (
        restored_request.operation_kind
        == original_request.operation_kind
    )

    assert (
        restored_request.next_action
        == original_request.next_action
    )

    assert (
        restored_request.target_resource
        == original_request.target_resource
    )

    assert (
        restored_request.required_parameters
        == original_request.required_parameters
    )

    assert (
        restored_request.resolved_parameters
        == original_request.resolved_parameters
    )

    #
    # Más fuerte:
    #
    # el snapshot HITL completo debe ser exactamente
    # el mismo antes y después del checkpoint.
    #
    assert (
        restored_request
        == original_request
    )

    #
    # --------------------------------------------------
    # 6. Responder DESPUÉS de restaurar
    # --------------------------------------------------
    #

    outputs = []

    async for event in workflow_b.run(
        responses={
            restored_request_id:
                True,
        },

        stream=True,
    ):
        if event.type == "output":
            outputs.append(
                event.data
            )

    assert (
        len(outputs)
        == 1
    )

    result = (
        outputs[0]
    )

    assert isinstance(
        result,
        ApprovedProcedureStep,
    )

    assert (
        result.approved
        is True
    )

    #
    # --------------------------------------------------
    # 7. Identidad post-HITL
    # --------------------------------------------------
    #

    assert (
        result.workflow_id
        == WORKFLOW_ID
    )

    assert (
        result.approval_id
        == original_approval_id
    )

    assert (
        result.alert_id
        == ALERT_ID
    )

    assert (
        result.correlation_id
        == CORRELATION_ID
    )

    #
    # --------------------------------------------------
    # 8. Procedimiento
    # --------------------------------------------------
    #

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

    #
    # --------------------------------------------------
    # 9. Operación aprobada
    # --------------------------------------------------
    #

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

    #
    # --------------------------------------------------
    # 10. Parámetros exactos
    # --------------------------------------------------
    #

    assert (
        result.required_parameters
        == state.step.required_parameters
    )

    assert (
        result.resolved_parameters
        == state.resolved_parameters
    )

    assert (
        result.resolved_parameters
        == [
            ResolvedParameter(
                name=(
                    "sql_server_instance"
                ),

                value=(
                    SQL_SERVER_INSTANCE
                ),

                source=(
                    "normalized_alert."
                    "affected_resource"
                ),
            )
        ]
    )

@pytest.mark.asyncio
async def test_operation_action_vm_start_checkpoint_deserialization(
    tmp_path,
):
    """
    FASE 18.2.20.1 RED.

    Demuestra que un workflow real que contiene:

        ProcedureRuntimeState
            -> ProcedureStep
            -> OperationAction.VM_START

    puede escribir sus checkpoints, pero todos los
    checkpoints generados deben poder ser
    deserializados posteriormente utilizando la
    allowlist exacta de producción.

    RED esperado actualmente:

        WorkflowCheckpointException

    causado por:

        src.runtime.procedure.models:OperationAction

    todavía ausente de _allowed_checkpoint_types().
    """

    from src.runtime.procedure.models import (
        OperationAction,
    )

    from src.runtime.procedure.workflow import (
        _allowed_checkpoint_types,
    )

    checkpoint_dir = (
        tmp_path
        / "operation-action-checkpoints"
    )

    workflow = (
        build_procedure_approval_workflow(
            str(checkpoint_dir)
        )
    )

    state = ProcedureRuntimeState(
        workflow_id=(
            "wf-operation-action-checkpoint-red"
        ),

        alert_id=(
            "ALT-AZ-VM-START-RED"
        ),

        correlation_id=(
            "corr-operation-action-checkpoint-red"
        ),

        conversation_id=(
            "conversation-operation-action-red"
        ),

        procedure=ProcedureReference(
            id="NTTSY-SBX-AZ-VM-001",
            name=(
                "Arranque gobernado de "
                "máquina virtual Azure"
            ),
            version="1.0",
        ),

        total_steps=1,
        current_step=1,

        step=ProcedureStep(
            id="1",

            description=(
                "Encender la máquina virtual "
                "autorizada."
            ),

            step_type="remediation",

            operation_domain="azure",

            operation_kind=(
                OperationKind.WRITE
            ),

            operation_action=(
                OperationAction.VM_START
            ),

            capability_id=(
                "azure.vm.start"
            ),

            hitl_required=True,

            target_resource=(
                "/subscriptions/sub-test/"
                "resourceGroups/rg-test/"
                "providers/Microsoft.Compute/"
                "virtualMachines/vm-test"
            ),

            required_parameters=[
                "subscription_id",
                "resource_group",
                "vm_name",
            ],
        ),

        resolved_parameters=[
            ResolvedParameter(
                name="subscription_id",
                value="sub-test",
                source="test.fixture",
            ),

            ResolvedParameter(
                name="resource_group",
                value="rg-test",
                source="test.fixture",
            ),

            ResolvedParameter(
                name="vm_name",
                value="vm-test",
                source="test.fixture",
            ),
        ],
    )

    request_event = None

    async for event in workflow.run(
        state,
        stream=True,
    ):
        if (
            event.type
            == "request_info"
        ):
            request_event = event

    assert (
        request_event
        is not None
    )

    assert isinstance(
        request_event.data,
        ApprovalRequest,
    )

    assert (
        request_event.data.operation_action
        == OperationAction.VM_START.value
    )

    checkpoint_files = sorted(
        checkpoint_dir.glob(
            "*.json"
        )
    )

    assert checkpoint_files

    storage = FileCheckpointStorage(
        str(checkpoint_dir),

        allowed_checkpoint_types=(
            _allowed_checkpoint_types()
        ),
    )

    loaded_checkpoints = []

    for checkpoint_file in checkpoint_files:
        checkpoint = await storage.load(
            checkpoint_file.stem
        )

        loaded_checkpoints.append(
            checkpoint
        )

    assert (
        len(loaded_checkpoints)
        == len(checkpoint_files)
    )