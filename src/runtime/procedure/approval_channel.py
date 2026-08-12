from __future__ import annotations

from enum import (
    Enum,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
)


class ApprovalDecision(
    str,
    Enum,
):
    """
    Decisión humana mínima aceptada por el
    boundary de un canal HITL.

    No contiene ninguna autoridad operacional.
    """

    APPROVE = "approve"
    REJECT = "reject"


class ApprovalChannelAction(
    BaseModel
):
    """
    Payload mínimo que un canal humano puede
    entregar al backend.

    El canal puede indicar exclusivamente:

        approval_id
        decision

    No puede proporcionar ni modificar:

        workflow_id
        alert_id
        procedure_id
        procedure_version
        step_id
        capability_id
        operation_action
        operation_domain
        operation_kind
        target_resource
        required_parameters
        resolved_parameters

    Esos valores pertenecen al ApprovalRequest
    original congelado por Python.

    La identidad autenticada del operador tampoco
    forma parte de este payload. Debe obtenerse
    posteriormente del contexto confiable del
    adaptador de canal.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    approval_id: str

    decision: ApprovalDecision

    @field_validator(
        "approval_id"
    )
    @classmethod
    def validate_approval_id(
        cls,
        value: str,
    ) -> str:
        if not value:
            raise ValueError(
                "approval_id no puede estar vacío."
            )

        if not value.strip():
            raise ValueError(
                "approval_id no puede contener "
                "únicamente espacios."
            )

        if value != value.strip():
            raise ValueError(
                "approval_id no puede contener "
                "espacios al inicio o al final."
            )

        return value