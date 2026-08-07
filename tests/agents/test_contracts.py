import pytest
from pydantic import ValidationError

from src.agents.contracts import (
    AlertTriageResult,
    ProcedureExecutionResult,
)


def test_valid_triage_exact():
    result = AlertTriageResult.model_validate(
        {
            "alert_classification":
                "availability_group_replica_out_of_sync",
            "technical_domain": "database",
            "affected_resource": "SQLPROD01",
            "affected_service":
                "Microsoft SQL Server Always On Availability Group",
            "technical_summary":
                "La réplica secundaria no está sincronizada.",
            "source_severity": "Critical",
            "corporate_criticality": "unknown",
            "criticality_source": "unknown",
            "procedure_found": True,
            "procedure_match": "exact",
            "execution_eligible": True,
            "knowledge_coverage": "complete",
            "recommended_next_step": "procedure_execution",
            "procedure": {
                "id": "NTTSY-PRO-020",
                "name": "Alertas SQL Server",
                "version": "v1.1",
                "resolution_criteria": None,
            },
            "escalation": {
                "required": False,
                "team": None,
                "level": None,
                "criteria": None,
            },
            "possible_false_positive": "unknown",
            "missing_context": [],
            "source_documents": [
                "NTTSY-PRO-020 - Alertas SQL Server v1.1"
            ],
            "confidence": 0.86,
            "ai_opinion": None,
        }
    )

    assert result.procedure_match == "exact"
    assert result.execution_eligible is True


def test_triage_none_cannot_be_executable():
    with pytest.raises(ValidationError):
        AlertTriageResult.model_validate(
            {
                "alert_classification": "unknown_alert",
                "technical_domain": "unknown",
                "affected_resource": "resource-01",
                "affected_service": None,
                "technical_summary": "Alerta desconocida.",
                "source_severity": "Critical",
                "corporate_criticality": "unknown",
                "criticality_source": "unknown",
                "procedure_found": False,
                "procedure_match": "none",
                "execution_eligible": True,
                "knowledge_coverage": "none",
                "recommended_next_step":
                    "procedure_execution",
                "procedure": None,
                "escalation": {
                    "required": False,
                    "team": None,
                    "level": None,
                    "criteria": None,
                },
                "possible_false_positive": "unknown",
                "missing_context": [],
                "source_documents": [],
                "confidence": 0.40,
                "ai_opinion": "Opinión IA.",
            }
        )


def test_partial_procedure_cannot_execute():
    with pytest.raises(ValidationError):
        AlertTriageResult.model_validate(
            {
                "alert_classification": "cpu_high",
                "technical_domain": "azure",
                "affected_resource": "vm-demo-01",
                "affected_service":
                    "Microsoft Azure Virtual Machine",
                "technical_summary": "CPU elevada.",
                "source_severity": "Sev2",
                "corporate_criticality": "unknown",
                "criticality_source": "unknown",
                "procedure_found": True,
                "procedure_match": "partial",
                "execution_eligible": True,
                "knowledge_coverage": "partial",
                "recommended_next_step":
                    "procedure_execution",
                "procedure": {
                    "id": "NTTSY-PRO-017",
                    "name":
                        "Revisión de infraestructura genérica",
                    "version": "v1.3",
                },
                "escalation": {
                    "required": False,
                    "team": None,
                    "level": None,
                    "criteria": None,
                },
                "possible_false_positive": "unknown",
                "missing_context": [],
                "source_documents": [],
                "confidence": 0.78,
                "ai_opinion": None,
            }
        )


def test_valid_procedure_execution():
    result = ProcedureExecutionResult.model_validate(
        {
            "alert_id": "ALT-SQL-AG-001",
            "procedure": {
                "id": "NTTSY-PRO-020",
                "name": "Alertas SQL Server",
                "version": "v1.1",
            },
            "execution_allowed": True,
            "blocked_by_policy": False,
            "total_steps": 5,
            "current_step": 1,
            "step": {
                "id": "1",
                "description":
                    "Comprobar el estado actual de la réplica.",
                "step_type": "validation",
                "operation_domain": "database",
                "operation_kind": "read",
                "target_resource": "SQLPROD01",
                "required_parameters": [],
                "preconditions": [],
                "expected_result":
                    "El estado queda identificado.",
                "verification":
                    "Validar mediante el mecanismo documentado.",
            },
            "resolution_criteria": None,
            "next_action": "execute_step",
            "escalation": {
                "required": False,
                "team": None,
                "level": None,
                "criteria": None,
            },
            "requires_clarification": False,
            "missing_information": [],
            "source_documents": [
                "NTTSY-PRO-020 - Alertas SQL Server v1.1"
            ],
            "confidence": 0.95,
        }
    )

    assert result.next_action == "execute_step"
    assert result.step.operation_domain == "database"


def test_blocked_policy_cannot_execute():
    with pytest.raises(ValidationError):
        ProcedureExecutionResult.model_validate(
            {
                "alert_id": "ALT-001",
                "procedure": {
                    "id": "PROC-001",
                    "name": "Test",
                    "version": "v1",
                },
                "execution_allowed": True,
                "blocked_by_policy": True,
                "total_steps": 1,
                "current_step": 1,
                "step": None,
                "resolution_criteria": None,
                "next_action": "execute_step",
                "escalation": {
                    "required": False,
                    "team": None,
                    "level": None,
                    "criteria": None,
                },
                "requires_clarification": False,
                "missing_information": [],
                "source_documents": [],
                "confidence": 0.90,
            }
        )