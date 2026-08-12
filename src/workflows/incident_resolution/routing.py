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

    Puede activarse cuando existe un procedimiento
    identificado pero todavía no es elegible para
    ejecución:

    - match partial; o
    - match exact con contexto insuficiente.

    En ambos casos Triage debe solicitar
    explícitamente knowledge_review.

    La ruta permanece mutuamente exclusiva respecto
    a Procedure Execution y Manual Analysis.
    """

    triage = context.triage

    return (
        triage.procedure_found
        and triage.procedure is not None
        and (
            triage.procedure_match
            in {
                "exact",
                "partial",
            }
        )
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