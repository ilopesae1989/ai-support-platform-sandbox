from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)

from src.workflows.incident_resolution.models import (
    TriagedAlertContext,
)


class SafeCommunicationContext(BaseModel):
    """
    Snapshot inmutable exclusivamente comunicable.

    No representa autoridad operacional.

    No contiene:
    - identidad de workflow;
    - correlación operacional;
    - aprobación;
    - identidad de canal;
    - parámetros de infraestructura;
    - capabilities;
    - resultados de operación o validación.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
    )

    alert_id: str

    technical_domain: str
    corporate_criticality: str

    affected_resource: str | None

    technical_summary: str

    procedure_id: str | None
    procedure_name: str | None

    @model_validator(mode="after")
    def validate_procedure_pair(
        self,
    ):
        has_id = self.procedure_id is not None
        has_name = self.procedure_name is not None

        if has_id != has_name:
            raise ValueError(
                "procedure_id y procedure_name "
                "deben existir juntos o ser ambos null."
            )

        return self


def build_safe_communication_context(
    context: TriagedAlertContext,
) -> SafeCommunicationContext:
    """
    Congela exclusivamente hechos comunicables
    gobernados por el resultado de Triage.

    No reconstruye ni completa valores desde
    NormalizedAlert, OperationalContext o Runtime.
    """

    if type(context) is not TriagedAlertContext:
        raise TypeError(
            "context debe ser exactamente "
            "TriagedAlertContext."
        )

    triage = context.triage

    procedure = triage.procedure

    if procedure is None:
        procedure_id = None
        procedure_name = None
    else:
        procedure_id = procedure.id
        procedure_name = procedure.name

    technical_domain = getattr(
        triage.technical_domain,
        "value",
        triage.technical_domain,
    )

    corporate_criticality = getattr(
        triage.corporate_criticality,
        "value",
        triage.corporate_criticality,
    )

    return SafeCommunicationContext(
        alert_id=context.alert.alert_id,
        technical_domain=technical_domain,
        corporate_criticality=(
            corporate_criticality
        ),
        affected_resource=(
            triage.affected_resource
        ),
        technical_summary=(
            triage.technical_summary
        ),
        procedure_id=procedure_id,
        procedure_name=procedure_name,
    )