from __future__ import annotations

from .models import (
    ApprovalStatus,
    NextAction,
    OperationKind,
    ProcedureExecutionResult,
    ProcedureRuntimeState,
    StepEvidence,
    StepStatus,
    WorkflowStatus,
    utc_now,
)


class ProcedureRuntime:
    """
    Runtime determinista para la ejecución de procedimientos.

    NO interpreta procedimientos.
    NO llama agentes.
    NO llama MCP.
    NO mantiene conversación.
    NO decide mediante LLM.

    Gestiona únicamente estado, políticas y transiciones.
    """

    def requires_human_approval(
        self,
        state: ProcedureRuntimeState,
    ) -> bool:
        """
        Política actual de SANDBOX:

        Toda operación externa requiere aprobación humana.

        Esta política está aquí deliberadamente y no en el
        Procedure Execution Agent.
        """

        return state.step.operation_kind in {
            OperationKind.READ,
            OperationKind.WRITE,
            OperationKind.HUMAN,
        }

    def prepare_current_step(
        self,
        state: ProcedureRuntimeState,
    ) -> ProcedureRuntimeState:
        """
        Prepara el paso actual antes de su ejecución.
        """

        if state.step_status != StepStatus.PENDING:
            raise ValueError(
                f"El paso {state.current_step} no está en estado pending. "
                f"Estado actual: {state.step_status}"
            )

        if self.requires_human_approval(state):
            state.step_status = StepStatus.WAITING_APPROVAL
            state.approval_status = ApprovalStatus.PENDING
            state.workflow_status = WorkflowStatus.WAITING_HUMAN
        else:
            state.step_status = StepStatus.APPROVED
            state.approval_status = ApprovalStatus.NOT_REQUIRED
            state.workflow_status = WorkflowStatus.RUNNING

        state.updated_at = utc_now()

        return state

    def register_approval(
        self,
        state: ProcedureRuntimeState,
        approved: bool,
    ) -> ProcedureRuntimeState:
        """
        Registra la decisión humana.

        El runtime no interpreta lenguaje natural.
        Recibe un booleano ya resuelto por la capa de aplicación.
        """

        if state.step_status != StepStatus.WAITING_APPROVAL:
            raise ValueError(
                "No existe una aprobación pendiente para el paso actual."
            )

        if approved:
            state.approval_status = ApprovalStatus.APPROVED
            state.step_status = StepStatus.APPROVED
            state.workflow_status = WorkflowStatus.RUNNING
        else:
            state.approval_status = ApprovalStatus.REJECTED
            state.step_status = StepStatus.REJECTED
            state.workflow_status = WorkflowStatus.BLOCKED

        state.updated_at = utc_now()

        return state

    def mark_operation_started(
        self,
        state: ProcedureRuntimeState,
    ) -> ProcedureRuntimeState:
        """
        Marca que el especialista operativo ha comenzado la operación.
        """

        if state.step_status != StepStatus.APPROVED:
            raise ValueError(
                "No puede iniciarse una operación sin que el paso "
                "esté aprobado."
            )

        state.step_status = StepStatus.RUNNING
        state.workflow_status = WorkflowStatus.WAITING_OPERATION
        state.updated_at = utc_now()

        return state

    def register_operation_result(
        self,
        state: ProcedureRuntimeState,
        evidence: StepEvidence,
    ) -> ProcedureRuntimeState:
        """
        Registra la evidencia devuelta por el especialista operativo.
        """

        if state.step_status != StepStatus.RUNNING:
            raise ValueError(
                "El paso no se encuentra en ejecución."
            )

        state.operation_result = evidence

        if evidence.success:
            state.step_status = StepStatus.WAITING_VALIDATION
            state.workflow_status = WorkflowStatus.WAITING_VALIDATION
        else:
            state.step_status = StepStatus.FAILED
            state.workflow_status = WorkflowStatus.WAITING_VALIDATION

        state.updated_at = utc_now()

        return state

    def apply_procedure_decision(
        self,
        state: ProcedureRuntimeState,
        decision: ProcedureExecutionResult,
    ) -> ProcedureRuntimeState:
        """
        Aplica de forma determinista la decisión devuelta por
        Procedure Execution Agent después de interpretar la evidencia.

        El runtime no decide el camino; solo ejecuta la transición.
        """

        if decision.next_action == NextAction.CONTINUE:
            state.step_status = StepStatus.SUCCEEDED
            state.workflow_status = WorkflowStatus.RUNNING

        elif decision.next_action == NextAction.REPEAT:
            state.retry_count += 1
            state.step_status = StepStatus.PENDING
            state.workflow_status = WorkflowStatus.RUNNING

        elif decision.next_action == NextAction.WAIT:
            state.step_status = StepStatus.WAITING_VALIDATION
            state.workflow_status = WorkflowStatus.WAITING_VALIDATION

        elif decision.next_action == NextAction.RESOLVED:
            state.step_status = StepStatus.SUCCEEDED
            state.workflow_status = WorkflowStatus.RESOLVED

        elif decision.next_action == NextAction.ESCALATE:
            state.step_status = StepStatus.FAILED
            state.workflow_status = WorkflowStatus.ESCALATION_REQUIRED

            state.escalation_required = True
            state.escalation_team = decision.escalation_team
            state.escalation_level = decision.escalation_level
            state.escalation_criteria = decision.escalation_criteria

        elif decision.next_action == NextAction.BLOCKED:
            state.step_status = StepStatus.BLOCKED
            state.workflow_status = WorkflowStatus.BLOCKED

        elif decision.next_action == NextAction.EXECUTE_STEP:
            raise ValueError(
                "execute_step no es una decisión válida después "
                "de ejecutar un paso."
            )

        else:
            raise ValueError(
                f"next_action no soportado: {decision.next_action}"
            )

        state.updated_at = utc_now()

        return state