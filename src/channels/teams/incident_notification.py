from __future__ import annotations

from dataclasses import (
    dataclass,
)

from src.workflows.incident_resolution.models import (
    TriagedAlertContext,
)


@dataclass(
    frozen=True
)
class TeamsIncidentNotification:
    """
    Proyección informativa de un incidente
    gobernado hacia el canal Microsoft Teams.

    Contiene información para comunicación humana.

    NO contiene:

        subscription_id
        resource_group
        operation_action
        capability_id
        resolved_parameters
        approval_id
        approved
        checkpoint_id

    Por tanto, esta estructura no constituye
    autoridad operacional.
    """

    alert_id: str

    technical_domain: str

    corporate_criticality: str

    affected_resource: str

    technical_summary: str

    procedure_id: str

    procedure_name: str

    recommended_next_step: str

    escalation_required: bool


def _require_exact_non_empty_string(
    *,
    name: str,
    value: object,
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
            f"{name} debe ser un string "
            "exacto no vacío."
        )

    return value


def build_teams_incident_notification(
    context: TriagedAlertContext,
) -> TeamsIncidentNotification:
    """
    Construye una notificación Teams exclusivamente
    desde el contexto tipado posterior a Triage.

    No interpreta texto libre.

    No reconstruye parámetros operacionales.

    Para esta ruta de demo se exige un procedimiento
    exacto y elegible cuyo siguiente paso sea
    procedure_execution.
    """

    if not isinstance(
        context,
        TriagedAlertContext,
    ):
        raise TypeError(
            "context debe ser "
            "TriagedAlertContext."
        )

    triage = (
        context.triage
    )

    if (
        triage.procedure_match
        != "exact"
    ):
        raise ValueError(
            "La notificación de procedimiento "
            "requiere procedure_match=exact."
        )

    if not triage.procedure_found:
        raise ValueError(
            "La notificación de procedimiento "
            "requiere procedure_found=true."
        )

    if triage.procedure is None:
        raise ValueError(
            "La notificación de procedimiento "
            "requiere un procedimiento identificado."
        )

    if not triage.execution_eligible:
        raise ValueError(
            "La notificación de procedimiento "
            "requiere execution_eligible=true."
        )

    if (
        triage.recommended_next_step
        != "procedure_execution"
    ):
        raise ValueError(
            "La notificación de procedimiento "
            "requiere recommended_next_step="
            "procedure_execution."
        )

    affected_resource = (
        _require_exact_non_empty_string(
            name="affected_resource",
            value=triage.affected_resource,
        )
    )

    return TeamsIncidentNotification(
        alert_id=(
            _require_exact_non_empty_string(
                name="alert_id",
                value=context.alert.alert_id,
            )
        ),

        technical_domain=(
            _require_exact_non_empty_string(
                name="technical_domain",
                value=triage.technical_domain,
            )
        ),

        corporate_criticality=(
            _require_exact_non_empty_string(
                name="corporate_criticality",
                value=triage.corporate_criticality,
            )
        ),

        affected_resource=(
            affected_resource
        ),

        technical_summary=(
            _require_exact_non_empty_string(
                name="technical_summary",
                value=triage.technical_summary,
            )
        ),

        procedure_id=(
            _require_exact_non_empty_string(
                name="procedure_id",
                value=triage.procedure.id,
            )
        ),

        procedure_name=(
            _require_exact_non_empty_string(
                name="procedure_name",
                value=triage.procedure.name,
            )
        ),

        recommended_next_step=(
            _require_exact_non_empty_string(
                name="recommended_next_step",
                value=triage.recommended_next_step,
            )
        ),

        escalation_required=(
            triage.escalation.required
        ),
    )


def render_teams_incident_notification(
    notification: TeamsIncidentNotification,
) -> str:
    """
    Renderiza únicamente contenido informativo.

    El texto resultante nunca debe utilizarse
    posteriormente como fuente de autoridad
    operacional.
    """

    if not isinstance(
        notification,
        TeamsIncidentNotification,
    ):
        raise TypeError(
            "notification debe ser "
            "TeamsIncidentNotification."
        )

    escalation = (
        "Sí"
        if notification.escalation_required
        else "No"
    )

    return (
        "AI Support Platform - Incidente detectado\n\n"
        f"Alerta: {notification.alert_id}\n"
        f"Criticidad: "
        f"{notification.corporate_criticality.upper()}\n"
        f"Dominio técnico: "
        f"{notification.technical_domain}\n"
        f"Recurso afectado: "
        f"{notification.affected_resource}\n\n"
        f"Resumen técnico: "
        f"{notification.technical_summary}\n\n"
        f"Procedimiento: "
        f"{notification.procedure_id} - "
        f"{notification.procedure_name}\n"
        f"Siguiente paso: "
        f"{notification.recommended_next_step}\n"
        f"Escalado requerido: "
        f"{escalation}"
    )
