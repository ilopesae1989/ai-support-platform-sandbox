from __future__ import annotations

import pytest

from src.agents.contracts import (
    AlertTriageResult,
    ClassificationResult,
    EscalationInfo,
    KnowledgeDocument,
    KnowledgeResult,
    ProcedureReference,
)

from src.channels.teams.incident_notification import (
    TeamsIncidentNotification,
    build_teams_incident_notification,
    render_teams_incident_notification,
)

from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)

from src.workflows.incident_resolution.models import (
    TriagedAlertContext,
)


ALERT_ID = "ALERT-SYNTHETIC-001"


def _context() -> TriagedAlertContext:
    return TriagedAlertContext(
        alert=NormalizedAlert(
            alert_id=ALERT_ID,
            source="azure_monitor",
            source_event_id="synthetic-event-001",
            name="Synthetic infrastructure incident",
            description=(
                "Synthetic incident used only to validate "
                "the governed Teams notification path."
            ),
            source_severity="Sev2",
            affected_resource=(
                "/subscriptions/00000000-0000-0000-0000-000000000000/"
                "resourceGroups/rg-synthetic/"
                "providers/Microsoft.Compute/"
                "virtualMachines/vm-synthetic"
            ),
            resource_type=(
                "Microsoft.Compute/virtualMachines"
            ),
            service="compute",
            environment="sandbox",
        ),
        classification=ClassificationResult(
            alert_id=ALERT_ID,
            alert_classification=(
                "infrastructure_availability"
            ),
            technical_domain="azure",
            affected_resource="vm-synthetic",
            affected_service="compute",
            classification_summary=(
                "Synthetic Azure availability incident."
            ),
            requires_clarification=False,
            missing_information=[],
            confidence=0.99,
        ),
        knowledge=KnowledgeResult(
            alert_id=ALERT_ID,
            knowledge_found=True,
            documents=[
                KnowledgeDocument(
                    id="PROC-SYNTHETIC-001",
                    name="Synthetic recovery procedure",
                    version="1.0",
                    relevance_summary=(
                        "Procedure applicable to this "
                        "synthetic validation."
                    ),
                )
            ],
            knowledge_summary=(
                "A matching synthetic procedure exists."
            ),
            limitations=[],
            confidence=0.99,
        ),
        triage=AlertTriageResult(
            alert_classification=(
                "infrastructure_availability"
            ),
            technical_domain="azure",
            affected_resource="vm-synthetic",
            affected_service="compute",
            technical_summary=(
                "Synthetic service availability incident."
            ),
            source_severity="Sev2",
            corporate_criticality="high",
            criticality_source="procedure",
            procedure_found=True,
            procedure_match="exact",
            execution_eligible=True,
            knowledge_coverage="complete",
            recommended_next_step=(
                "procedure_execution"
            ),
            procedure=ProcedureReference(
                id="PROC-SYNTHETIC-001",
                name="Synthetic recovery procedure",
                version="1.0",
                resolution_criteria=(
                    "Synthetic service restored."
                ),
            ),
            escalation=EscalationInfo(
                required=False,
            ),
            possible_false_positive="unlikely",
            missing_context=[],
            source_documents=[
                "PROC-SYNTHETIC-001"
            ],
            confidence=0.99,
            ai_opinion=None,
        ),
    )


def test_builds_notification_from_typed_triaged_context():
    notification = (
        build_teams_incident_notification(
            _context()
        )
    )

    assert notification == TeamsIncidentNotification(
        alert_id=ALERT_ID,
        technical_domain="azure",
        corporate_criticality="high",
        affected_resource="vm-synthetic",
        technical_summary=(
            "Synthetic service availability incident."
        ),
        procedure_id="PROC-SYNTHETIC-001",
        procedure_name=(
            "Synthetic recovery procedure"
        ),
        recommended_next_step=(
            "procedure_execution"
        ),
        escalation_required=False,
    )


def test_renderer_contains_business_information():
    notification = (
        build_teams_incident_notification(
            _context()
        )
    )

    rendered = (
        render_teams_incident_notification(
            notification
        )
    )

    assert "ALERT-SYNTHETIC-001" in rendered
    assert "HIGH" in rendered
    assert "azure" in rendered
    assert "vm-synthetic" in rendered
    assert "PROC-SYNTHETIC-001" in rendered
    assert "Synthetic recovery procedure" in rendered


def test_notification_contains_no_operational_authority():
    notification = (
        build_teams_incident_notification(
            _context()
        )
    )

    fields = set(
        notification.__dataclass_fields__
    )

    forbidden = {
        "subscription_id",
        "resource_group",
        "operation_action",
        "capability_id",
        "resolved_parameters",
        "approved",
        "approval_id",
        "checkpoint_id",
    }

    assert forbidden.isdisjoint(
        fields
    )


def test_exact_procedure_is_required_for_procedure_fields():
    context = _context()

    context.triage.procedure = None

    with pytest.raises(
        ValueError
    ):
        build_teams_incident_notification(
            context
        )


def test_requires_triaged_alert_context():
    with pytest.raises(
        TypeError
    ):
        build_teams_incident_notification(
            object()
        )
