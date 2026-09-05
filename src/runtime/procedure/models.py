from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)
from enum import Enum
from typing import Any

from pydantic import (
    BaseModel,
    Field,
)


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


class StepStatus(str, Enum):
    PENDING = "pending"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    RUNNING = "running"
    WAITING_VALIDATION = "waiting_validation"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


class WorkflowStatus(str, Enum):
    INITIALIZED = "initialized"
    WAITING_HUMAN = "waiting_human"
    RUNNING = "running"
    WAITING_OPERATION = "waiting_operation"
    WAITING_VALIDATION = "waiting_validation"
    RESOLVED = "resolved"
    ESCALATION_REQUIRED = "escalation_required"
    BLOCKED = "blocked"
    FAILED = "failed"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    NOT_REQUIRED = "not_required"
    APPROVED = "approved"
    REJECTED = "rejected"


class OperationKind(str, Enum):
    READ = "read"
    WRITE = "write"
    WAIT = "wait"
    HUMAN = "human"
    NONE = "none"


class OperationAction(str, Enum):
    """
    Acción operacional canónica gobernada por Python.

    No representa routing del workflow.

    No debe confundirse con NextAction.

    Se ampliará progresivamente a medida que nuevas
    acciones operativas sean autorizadas explícitamente
    por la plataforma.
    """

    VM_START = "vm_start"


class NextAction(str, Enum):
    EXECUTE_STEP = "execute_step"
    CONTINUE = "continue"
    REPEAT = "repeat"
    WAIT = "wait"
    RESOLVED = "resolved"
    ESCALATE = "escalate"
    BLOCKED = "blocked"


class ProcedureReference(BaseModel):
    id: str
    name: str
    version: str | None = None


class ProcedureStep(BaseModel):
    id: str
    description: str
    step_type: str

    operation_domain: str
    operation_kind: OperationKind

    operation_action: OperationAction | None = None

    #
    # Identidad y policy de la capability
    # resueltas exclusivamente por Python.
    #
    # No proceden del Procedure Agent.
    #
    capability_id: str | None = None

    hitl_required: bool | None = None

    target_resource: str | None = None

    required_parameters: list[str] = Field(
        default_factory=list
    )

    preconditions: list[str] = Field(
        default_factory=list
    )

    expected_result: str | None = None
    verification: str | None = None


class StepEvidence(BaseModel):
    success: bool

    result: Any | None = None
    error: str | None = None

    collected_at: datetime = Field(
        default_factory=utc_now
    )


class ProcedureExecutionResult(BaseModel):
    next_action: NextAction

    evidence: StepEvidence | None = None

    escalation_required: bool = False
    escalation_team: str | None = None
    escalation_level: str | None = None
    escalation_criteria: str | None = None


class ResolvedParameter(BaseModel):
    name: str
    value: str
    source: str


class ProcedureRuntimeState(BaseModel):
    workflow_id: str
    alert_id: str

    correlation_id: str | None = None

    #
    # Se asigna exactamente una vez cuando
    # el paso entra en WAITING_APPROVAL.
    #
    approval_id: str | None = None

    conversation_id: str | None = None

    procedure: ProcedureReference

    total_steps: int
    current_step: int

    step: ProcedureStep

    resolved_parameters: list[
        ResolvedParameter
    ] = Field(
        default_factory=list
    )

    workflow_status: WorkflowStatus = (
        WorkflowStatus.INITIALIZED
    )

    step_status: StepStatus = (
        StepStatus.PENDING
    )

    approval_status: ApprovalStatus = (
        ApprovalStatus.PENDING
    )

    operation_result: StepEvidence | None = None
    verification_result: StepEvidence | None = None

    retry_count: int = 0

    recheck_count: int = Field(
        default=0,
        ge=0,
    )

    escalation_required: bool = False
    escalation_team: str | None = None
    escalation_level: str | None = None
    escalation_criteria: str | None = None

    created_at: datetime = Field(
        default_factory=utc_now
    )

    updated_at: datetime = Field(
        default_factory=utc_now
    )


class ApprovedProcedureStep(BaseModel):
    """
    Snapshot exacto de la operación autorizada
    después de HITL.

    description forma parte de la operación que
    el operador humano vio y aprobó.

    No puede reconstruirse, reinterpretarse ni
    sustituirse después de HITL.
    """

    workflow_id: str

    approval_id: str

    alert_id: str

    correlation_id: str | None = None

    conversation_id: str | None = None

    procedure_id: str
    procedure_version: str | None = None

    current_step: int
    step_id: str

    description: str

    operation_domain: str
    operation_kind: OperationKind

    operation_action: OperationAction | None = None

    #
    # Capability exacta que autorizó este paso.
    #
    # Forma parte del snapshot aprobado y no debe
    # reconstruirse después del HITL.
    #
    capability_id: str | None = None

    hitl_required: bool | None = None

    next_action: NextAction

    target_resource: str | None = None

    required_parameters: list[str] = Field(
        default_factory=list
    )

    resolved_parameters: list[
        ResolvedParameter
    ] = Field(
        default_factory=list
    )

    approved: bool = True