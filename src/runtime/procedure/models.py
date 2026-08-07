from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StepStatus(StrEnum):
    PENDING = "pending"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    RUNNING = "running"
    WAITING_VALIDATION = "waiting_validation"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


class WorkflowStatus(StrEnum):
    INITIALIZED = "initialized"
    RUNNING = "running"
    WAITING_HUMAN = "waiting_human"
    WAITING_OPERATION = "waiting_operation"
    WAITING_VALIDATION = "waiting_validation"
    RESOLVED = "resolved"
    ESCALATION_REQUIRED = "escalation_required"
    BLOCKED = "blocked"
    FAILED = "failed"


class ApprovalStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class OperationKind(StrEnum):
    READ = "read"
    WRITE = "write"
    WAIT = "wait"
    HUMAN = "human"
    NONE = "none"


class NextAction(StrEnum):
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

    target_resource: str | None = None

    required_parameters: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)

    expected_result: str | None = None
    verification: str | None = None


class StepEvidence(BaseModel):
    success: bool
    result: Any | None = None
    error: str | None = None
    collected_at: datetime = Field(default_factory=utc_now)


class ProcedureExecutionResult(BaseModel):
    next_action: NextAction

    evidence: StepEvidence | None = None

    escalation_required: bool = False
    escalation_team: str | None = None
    escalation_level: str | None = None
    escalation_criteria: str | None = None


class ProcedureRuntimeState(BaseModel):
    workflow_id: str
    alert_id: str

    conversation_id: str | None = None

    procedure: ProcedureReference

    total_steps: int
    current_step: int

    step: ProcedureStep

    workflow_status: WorkflowStatus = WorkflowStatus.INITIALIZED
    step_status: StepStatus = StepStatus.PENDING
    approval_status: ApprovalStatus = ApprovalStatus.PENDING

    operation_result: StepEvidence | None = None
    verification_result: StepEvidence | None = None

    retry_count: int = 0

    escalation_required: bool = False
    escalation_team: str | None = None
    escalation_level: str | None = None
    escalation_criteria: str | None = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)