from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    model_validator,
)


CommunicationEventType = Literal[
    "incident_detected",
    "waiting_validation",
    "resolved",
    "escalation_required",
    "blocked",
    "failed",
    "operation_rejected",
]


class CommunicationRequest(BaseModel):
    """
    Proyección gobernada y agnóstica de canal que puede
    entregarse al boundary cognitivo de comunicación.

    Representa únicamente información autorizada para
    presentación humana.

    No contiene autoridad operacional, autorización,
    routing de canal ni selección de destinatario.
    """

    model_config = {
        "extra": "forbid",
        "frozen": True,
        "revalidate_instances": "always",
    }

    event_type: CommunicationEventType

    alert_id: str

    technical_domain: str

    corporate_criticality: str

    affected_resource: str | None

    technical_summary: str

    procedure_id: str | None

    procedure_name: str | None

    status_summary: str

    escalation_required: bool

    escalation_team: str | None

    @model_validator(mode="after")
    def validate_projection_consistency(
        self,
    ):
        procedure_id_present = (
            self.procedure_id is not None
        )

        procedure_name_present = (
            self.procedure_name is not None
        )

        if (
            procedure_id_present
            != procedure_name_present
        ):
            raise ValueError(
                "procedure_id y procedure_name "
                "deben estar ambos presentes "
                "o ambos ausentes."
            )

        if (
            not self.escalation_required
            and self.escalation_team is not None
        ):
            raise ValueError(
                "escalation_team requiere "
                "escalation_required=true."
            )

        if (
            self.event_type
            == "escalation_required"
            and not self.escalation_required
        ):
            raise ValueError(
                "event_type=escalation_required "
                "requiere escalation_required=true."
            )

        return self


class CommunicationResult(BaseModel):
    """
    Resultado exclusivamente de presentación producido
    por el boundary cognitivo de comunicación.

    No representa verdad operacional.

    No puede modificar:
    - event_type;
    - criticidad;
    - escalado;
    - autorización;
    - operación;
    - capability;
    - target;
    - parámetros;
    - destinatario;
    - canal.
    """

    model_config = {
        "extra": "forbid",
        "frozen": True,
        "revalidate_instances": "always",
    }

    headline: str

    summary: str

    details: list[str]