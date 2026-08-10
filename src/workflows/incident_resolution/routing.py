from src.workflows.incident_resolution.models import (
    TriagedAlertContext,
)


def route_to_procedure_execution(
    context: TriagedAlertContext,
) -> bool:
    """
    Ruta hacia Procedure Execution.

    Solo puede activarse cuando:
    - existe procedimiento;
    - el match es exact;
    - la ejecución es elegible;
    - existe procedimiento concreto;
    - Triage solicita procedure_execution.
    """

    triage = context.triage

    return (
        triage.procedure_found
        and triage.procedure_match == "exact"
        and triage.execution_eligible
        and triage.procedure is not None
        and (
            triage.recommended_next_step
            == "procedure_execution"
        )
    )


def route_to_knowledge_review(
    context: TriagedAlertContext,
) -> bool:
    """
    Ruta hacia Knowledge Review.

    Solo debe activarse cuando:
    - existe match parcial;
    - no es elegible;
    - Triage solicita knowledge_review.

    Esto mantiene la ruta mutuamente exclusiva
    respecto a manual_analysis/human_escalation.
    """

    triage = context.triage

    return (
        triage.procedure_match == "partial"
        and not triage.execution_eligible
        and (
            triage.recommended_next_step
            == "knowledge_review"
        )
    )


def route_to_manual_analysis(
    context: TriagedAlertContext,
) -> bool:
    """
    Ruta segura para:
    - análisis manual;
    - escalado humano.

    Nunca conduce a ejecución técnica.
    """

    triage = context.triage

    return (
        triage.recommended_next_step
        in {
            "manual_analysis",
            "human_escalation",
        }
    )