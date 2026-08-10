from datetime import datetime, timezone

import pytest

from src.agents.contracts import (
    AlertTriageResult,
    ClassificationResult,
    KnowledgeResult,
)
from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)
from src.workflows.incident_resolution.models import (
    KnowledgeEnrichedAlertContext,
    TriagedAlertContext,
)
from src.workflows.incident_resolution.routing import (
    route_to_knowledge_review,
    route_to_manual_analysis,
    route_to_procedure_execution,
)


def create_context(
    *,
    procedure_match: str,
    execution_eligible: bool,
    recommended_next_step: str,
    procedure_found: bool,
) -> TriagedAlertContext:
    alert = NormalizedAlert(
        alert_id="ALT-TEST-001",
        source="scom",
        name="Test Alert",
        description="Alerta de prueba.",
        source_severity="Critical",
        timestamp=datetime(
            2026,
            8,
            8,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        affected_resource="SERVER01",
        resource_type="TestResource",
        correlation_id="corr-test-001",
    )

    classification = ClassificationResult.model_validate(
        {
            "alert_id": "ALT-TEST-001",
            "alert_classification": "test_alert",
            "technical_domain": "database",
            "affected_resource": "SERVER01",
            "affected_service": "Test Service",
            "classification_summary": "Test.",
            "requires_clarification": False,
            "missing_information": [],
            "confidence": 0.9,
        }
    )

    knowledge = KnowledgeResult.model_validate(
        {
            "alert_id": "ALT-TEST-001",
            "knowledge_found": procedure_found,
            "documents": (
                [
                    {
                        "id": "PROC-001",
                        "name": "Test Procedure",
                        "version": "v1",
                        "relevance_summary":
                            "Procedimiento de prueba.",
                    }
                ]
                if procedure_found
                else []
            ),
            "knowledge_summary": (
                "Existe conocimiento."
                if procedure_found
                else None
            ),
            "limitations": [],
            "confidence": (
                0.9
                if procedure_found
                else 0.0
            ),
        }
    )

    procedure = (
        {
            "id": "PROC-001",
            "name": "Test Procedure",
            "version": "v1",
            "resolution_criteria": None,
        }
        if procedure_found
        else None
    )

    triage = AlertTriageResult.model_validate(
        {
            "alert_classification": "test_alert",
            "technical_domain": "database",
            "affected_resource": "SERVER01",
            "affected_service": "Test Service",
            "technical_summary": "Test.",
            "source_severity": "Critical",
            "corporate_criticality": "unknown",
            "criticality_source": "unknown",
            "procedure_found": procedure_found,
            "procedure_match": procedure_match,
            "execution_eligible": execution_eligible,
            "knowledge_coverage": (
                "complete"
                if procedure_match == "exact"
                else (
                    "partial"
                    if procedure_match == "partial"
                    else "none"
                )
            ),
            "recommended_next_step":
                recommended_next_step,
            "procedure": procedure,
            "escalation": {
                "required": (
                    recommended_next_step
                    == "human_escalation"
                ),
                "team": None,
                "level": None,
                "criteria": None,
            },
            "possible_false_positive": "unknown",
            "missing_context": [],
            "source_documents": (
                ["PROC-001"]
                if procedure_found
                else []
            ),
            "confidence": 0.9,
            "ai_opinion": None,
        }
    )

    return TriagedAlertContext(
        alert=alert,
        classification=classification,
        knowledge=knowledge,
        triage=triage,
    )


def test_exact_routes_only_to_procedure_execution():
    context = create_context(
        procedure_match="exact",
        execution_eligible=True,
        recommended_next_step=
            "procedure_execution",
        procedure_found=True,
    )

    assert (
        route_to_procedure_execution(context)
        is True
    )

    assert (
        route_to_knowledge_review(context)
        is False
    )

    assert (
        route_to_manual_analysis(context)
        is False
    )


def test_partial_routes_only_to_knowledge_review():
    context = create_context(
        procedure_match="partial",
        execution_eligible=False,
        recommended_next_step=
            "knowledge_review",
        procedure_found=True,
    )

    assert (
        route_to_procedure_execution(context)
        is False
    )

    assert (
        route_to_knowledge_review(context)
        is True
    )

    assert (
        route_to_manual_analysis(context)
        is False
    )


def test_none_routes_only_to_manual_analysis():
    context = create_context(
        procedure_match="none",
        execution_eligible=False,
        recommended_next_step=
            "manual_analysis",
        procedure_found=False,
    )

    assert (
        route_to_procedure_execution(context)
        is False
    )

    assert (
        route_to_knowledge_review(context)
        is False
    )

    assert (
        route_to_manual_analysis(context)
        is True
    )


def test_non_eligible_exact_does_not_route_to_execution():
    context = create_context(
        procedure_match="exact",
        execution_eligible=False,
        recommended_next_step=
            "knowledge_review",
        procedure_found=True,
    )

    assert (
        route_to_procedure_execution(context)
        is False
    )


def test_routes_are_mutually_exclusive():
    contexts = [
        create_context(
            procedure_match="exact",
            execution_eligible=True,
            recommended_next_step=
                "procedure_execution",
            procedure_found=True,
        ),
        create_context(
            procedure_match="partial",
            execution_eligible=False,
            recommended_next_step=
                "knowledge_review",
            procedure_found=True,
        ),
        create_context(
            procedure_match="none",
            execution_eligible=False,
            recommended_next_step=
                "manual_analysis",
            procedure_found=False,
        ),
    ]

    for context in contexts:
        routes = [
            route_to_procedure_execution(
                context
            ),
            route_to_knowledge_review(
                context
            ),
            route_to_manual_analysis(
                context
            ),
        ]

        assert sum(routes) == 1
def test_partial_human_escalation_routes_only_to_manual_analysis():
    context = create_context(
        procedure_match="partial",
        execution_eligible=False,
        recommended_next_step=
            "human_escalation",
        procedure_found=True,
    )

    assert (
        route_to_procedure_execution(context)
        is False
    )

    assert (
        route_to_knowledge_review(context)
        is False
    )

    assert (
        route_to_manual_analysis(context)
        is True
    )


def test_partial_manual_analysis_does_not_route_to_knowledge_review():
    context = create_context(
        procedure_match="partial",
        execution_eligible=False,
        recommended_next_step=
            "manual_analysis",
        procedure_found=True,
    )

    assert (
        route_to_procedure_execution(context)
        is False
    )

    assert (
        route_to_knowledge_review(context)
        is False
    )

    assert (
        route_to_manual_analysis(context)
        is True
    )