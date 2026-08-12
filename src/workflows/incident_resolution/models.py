from typing import Literal

from pydantic import BaseModel

from src.agents.contracts import (
    AlertTriageResult,
    ClassificationResult,
    KnowledgeResult,
    ProcedureExecutionResult,
)

from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)

from src.workflows.incident_resolution.operational_context import (
    OperationalContext,
)


class ClassifiedAlertContext(BaseModel):
    alert: NormalizedAlert
    classification: ClassificationResult


class KnowledgeEnrichedAlertContext(BaseModel):
    alert: NormalizedAlert
    classification: ClassificationResult
    knowledge: KnowledgeResult


class TriagedAlertContext(BaseModel):
    alert: NormalizedAlert
    classification: ClassificationResult
    knowledge: KnowledgeResult
    triage: AlertTriageResult


class ExecutionIdentity(BaseModel):
    """
    Identidad de ESTA ejecución.

    workflow_id:
        ejecución concreta.

    alert_id:
        alerta origen.

    correlation_id:
        correlación operacional original.

    No procede de ningún LLM.
    """

    workflow_id: str
    alert_id: str

    correlation_id: str | None = None


class ProcedureExecutionRequest(BaseModel):
    """
    Solicitud cognitiva hacia Procedure v6.

    No contiene autoridad operacional.
    """

    alert_id: str

    procedure_found: bool
    procedure_match: str
    execution_eligible: bool

    procedure_id: str
    procedure_name: str
    procedure_version: str | None = None

    affected_resource: str
    incident_description: str


class ProcedureExecutionInput(BaseModel):
    """
    Envelope previo a Procedure v6.

    Mantiene separados:

    - request cognitivo;
    - identidad de ejecución;
    - OperationalContext autoritativo.
    """

    request: ProcedureExecutionRequest

    execution_identity: ExecutionIdentity

    operational_context: OperationalContext


class ProcedureExecutionContext(BaseModel):
    """
    Envelope posterior a Procedure v6.

    execution_identity y operational_context
    sobreviven en paralelo al agente.
    """

    request: ProcedureExecutionRequest

    result: ProcedureExecutionResult

    execution_identity: ExecutionIdentity

    operational_context: OperationalContext


class KnowledgeReviewRequest(BaseModel):
    alert_id: str

    reason: Literal[
        "partial_procedure_match",
        "insufficient_knowledge",
    ]

    procedure_id: str | None = None
    procedure_name: str | None = None
    procedure_version: str | None = None

    affected_resource: str | None = None

    missing_context: list[str]


class ManualAnalysisRequest(BaseModel):
    alert_id: str

    reason: Literal[
        "no_procedure",
        "manual_analysis_required",
        "human_escalation_required",
    ]

    technical_domain: str

    affected_resource: str | None = None

    missing_context: list[str]
