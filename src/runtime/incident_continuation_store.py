"""Channel-independent job and persistence port for an authorized HITL handoff."""
from __future__ import annotations

from enum import Enum
from typing import Generic, Protocol
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from src.runtime.incident_continuation_codec import InvocationT
from src.runtime.procedure.approval_correlation import PendingApprovalCorrelation


MAX_PREAPPROVAL_RECOVERY_ATTEMPTS = 3


def require_continuation_attempt(value: object) -> int:
    """Require the generation returned by claim_next, never infer a current one."""
    if type(value) is not int or value < 1:
        raise ValueError("expected_attempt_count must be a positive exact integer.")
    return value


class IncidentContinuationConflictError(
    RuntimeError
):
    """
    El mismo approval_id ya fue persistido con
    un payload autorizado diferente.
    """

    pass


class IncidentContinuationClaimError(
    RuntimeError
):
    """
    Transición inválida del lifecycle durable.
    """

    pass


class IncidentContinuationStatus(
    str,
    Enum,
):
    PENDING = "pending"
    CLAIMED = "claimed"
    COMPLETED = "completed"
    FAILED = "failed"


class IncidentContinuationJob(
    BaseModel, Generic[InvocationT]
):
    """
    Unidad durable posterior al ACK del canal.

    Contiene exclusivamente una decisión HITL
    ya autenticada y autorizada.

    NO contiene autoridad operacional Azure.
    NO contiene ProcedureRuntimeState.
    NO contiene parámetros reconstruidos desde el canal.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
    )

    approval_id: str

    invocation: (
        InvocationT
    )

    status: IncidentContinuationStatus

    attempt_count: int = 0

    claimed_by: str | None = None

    last_error: str | None = None

    created_at: float

    updated_at: float

    @field_validator(
        "approval_id"
    )
    @classmethod
    def validate_approval_id(
        cls,
        value: str,
    ) -> str:
        if (
            not isinstance(
                value,
                str,
            )
            or not value
            or not value.strip()
            or value != value.strip()
        ):
            raise ValueError(
                "approval_id debe ser un string "
                "no vacío y exacto."
            )

        return value

    @field_validator(
        "attempt_count"
    )
    @classmethod
    def validate_attempt_count(
        cls,
        value: int,
    ) -> int:
        if (
            isinstance(
                value,
                bool,
            )
            or not isinstance(
                value,
                int,
            )
            or value < 0
        ):
            raise ValueError(
                "attempt_count debe ser un entero "
                "mayor o igual que cero."
            )

        return value

    @model_validator(
        mode="after"
    )
    def validate_identity_and_state(
        self,
    ):
        if (
            self.approval_id
            !=
            self.invocation
            .action
            .approval_id
        ):
            raise ValueError(
                "approval_id no coincide con "
                "la invocación autorizada."
            )

        if (
            self.status
            == IncidentContinuationStatus.CLAIMED
        ):
            if self.claimed_by is None:
                raise ValueError(
                    "claimed requiere claimed_by."
                )

        elif self.claimed_by is not None:
            raise ValueError(
                "claimed_by sólo puede existir "
                "cuando status=claimed."
            )

        return self


class IncidentContinuationStore(
    Protocol[InvocationT]
):
    """Queue transitions compare owner and the generation returned by claim_next.

    Callers must retain that generation. Reading a newer attempt to retry a
    rejected transition would adopt another execution's ownership.
    These guards cover queue rows, not the separate HITL claim or remote effects.
    """

    def claim_approval(
        self, *, approval_id: str, worker_id: str, expected_attempt_count: int,
        approved: bool, approval_store: object,
    ) -> PendingApprovalCorrelation:
        """Claim HITL with ownership checked in the same persistence transaction.

        No response may be delivered until this returns after commit. An error
        must not be retried by inferring permission from a subsequent read.
        """
        ...

    def enqueue(
        self,
        invocation: (
            InvocationT
        ),
    ) -> IncidentContinuationJob[InvocationT]:
        ...

    def get(
        self,
        approval_id: str,
    ) -> IncidentContinuationJob[InvocationT]:
        ...

    def claim_next(
        self,
        *,
        worker_id: str,
    ) -> IncidentContinuationJob[InvocationT] | None:
        ...

    def complete(
        self,
        *,
        approval_id: str,
        worker_id: str,
        expected_attempt_count: int,
    ) -> IncidentContinuationJob[InvocationT]:
        ...

    def fail(
        self,
        *,
        approval_id: str,
        worker_id: str,
        expected_attempt_count: int,
        error: str,
    ) -> IncidentContinuationJob[InvocationT]:
        ...

    def recover_claimed_before_approval(
        self,
        *,
        approval_id: str,
        worker_id: str,
        expected_attempt_count: int,
        approval_store: object,
    ) -> IncidentContinuationJob[InvocationT]:
        ...
