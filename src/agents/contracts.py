from typing import Literal

from pydantic import BaseModel, Field, model_validator


TechnicalDomain = Literal[
    "azure",
    "windows",
    "linux",
    "database",
    "networking",
    "security",
    "microsoft365",
    "application",
    "unknown",
]

CorporateCriticality = Literal[
    "critical",
    "high",
    "medium",
    "low",
    "informational",
    "unknown",
]

CriticalitySource = Literal[
    "procedure",
    "escalation_matrix",
    "corporate_matrix",
    "unknown",
]

ProcedureMatch = Literal[
    "exact",
    "partial",
    "none",
]

KnowledgeCoverage = Literal[
    "complete",
    "partial",
    "none",
]

RecommendedNextStep = Literal[
    "procedure_execution",
    "knowledge_review",
    "manual_analysis",
    "human_escalation",
]

FalsePositiveAssessment = Literal[
    "unlikely",
    "possible",
    "likely",
    "unknown",
]


# ============================================================
# CLASSIFICATION AGENT CONTRACT
# ============================================================

class ClassificationResult(BaseModel):
    """
    Contrato de salida del agente de clasificación.

    Responsabilidad:
    representar exclusivamente la clasificación técnica
    inicial de una alerta.

    No contiene:
    - routing;
    - nombres de otros agentes;
    - decisiones de aprobación;
    - procedimientos;
    - criticidad corporativa;
    - escalado;
    - operaciones.
    """

    alert_id: str

    alert_classification: str

    technical_domain: TechnicalDomain

    affected_resource: str | None = None

    affected_service: str | None = None

    classification_summary: str

    requires_clarification: bool

    missing_information: list[str] = Field(
        default_factory=list
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    @model_validator(mode="after")
    def validate_classification_consistency(
        self,
    ):
        """
        Valida coherencia determinista del resultado
        del Classification Agent.

        Estas reglas pertenecen al contrato Python
        y no dependen del LLM.
        """

        if (
            self.requires_clarification
            and not self.missing_information
        ):
            raise ValueError(
                "requires_clarification=true requiere "
                "missing_information."
            )

        if (
            not self.requires_clarification
            and self.missing_information
        ):
            raise ValueError(
                "requires_clarification=false requiere "
                "missing_information=[]."
            )

        return self

# ============================================================
# KNOWLEDGE AGENT CONTRACT
# ============================================================

class KnowledgeDocument(BaseModel):
    """
    Documento corporativo recuperado mediante Foundry IQ.

    id representa exclusivamente el identificador
    documental corporativo cuando esté disponible.
    """

    id: str | None = None
    name: str
    version: str | None = None
    relevance_summary: str


class KnowledgeResult(BaseModel):
    """
    Contrato de salida del Knowledge Agent.

    Representa únicamente conocimiento corporativo
    recuperado y fundamentado.

    No decide:
    - procedure_match;
    - knowledge_coverage;
    - criticidad;
    - escalado;
    - ejecución;
    - routing.
    """

    alert_id: str | None = None

    knowledge_found: bool

    documents: list[KnowledgeDocument] = Field(
        default_factory=list
    )

    knowledge_summary: str | None = None

    limitations: list[str] = Field(
        default_factory=list
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    @model_validator(mode="after")
    def validate_knowledge_consistency(
        self,
    ):
        """
        Reglas deterministas del contrato Knowledge.
        """

        if self.knowledge_found:
            if not self.documents:
                raise ValueError(
                    "knowledge_found=true requiere "
                    "al menos un documento."
                )

            if self.knowledge_summary is None:
                raise ValueError(
                    "knowledge_found=true requiere "
                    "knowledge_summary."
                )

        else:
            if self.documents:
                raise ValueError(
                    "knowledge_found=false requiere "
                    "documents=[]."
                )

            if self.knowledge_summary is not None:
                raise ValueError(
                    "knowledge_found=false requiere "
                    "knowledge_summary=null."
                )

            if self.confidence != 0.0:
                raise ValueError(
                    "knowledge_found=false requiere "
                    "confidence=0.0."
                )

        #
        # Evitar duplicados cuando existe un identificador
        # documental corporativo.
        #
        document_ids = [
            document.id
            for document in self.documents
            if document.id is not None
        ]

        if len(document_ids) != len(set(document_ids)):
            raise ValueError(
                "documents contiene identificadores "
                "documentales duplicados."
            )

        return self

# ============================================================
# TRIAGE AGENT CONTRACT
# ============================================================

class ProcedureReference(BaseModel):
    id: str
    name: str
    version: str | None = None
    resolution_criteria: str | None = None


class EscalationInfo(BaseModel):
    required: bool
    team: str | None = None
    level: str | None = None
    criteria: str | None = None


class AlertTriageResult(BaseModel):
    alert_classification: str
    technical_domain: TechnicalDomain

    affected_resource: str | None = None
    affected_service: str | None = None

    technical_summary: str

    source_severity: str | None = None

    corporate_criticality: CorporateCriticality
    criticality_source: CriticalitySource

    procedure_found: bool
    procedure_match: ProcedureMatch
    execution_eligible: bool
    knowledge_coverage: KnowledgeCoverage

    recommended_next_step: RecommendedNextStep

    procedure: ProcedureReference | None = None

    escalation: EscalationInfo

    possible_false_positive: FalsePositiveAssessment

    missing_context: list[str] = Field(
        default_factory=list
    )

    source_documents: list[str] = Field(
        default_factory=list
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    ai_opinion: str | None = None

    @model_validator(mode="after")
    def validate_triage_consistency(self):
        """
        Valida coherencia determinista del resultado de Triage.

        Estas reglas no dependen del LLM.
        """

        if self.procedure_found is False:
            if self.procedure is not None:
                raise ValueError(
                    "procedure debe ser null cuando "
                    "procedure_found=false."
                )

        if self.procedure_match == "none":
            if self.procedure is not None:
                raise ValueError(
                    "procedure debe ser null cuando "
                    "procedure_match=none."
                )

            if self.execution_eligible:
                raise ValueError(
                    "execution_eligible no puede ser true "
                    "cuando procedure_match=none."
                )

            if self.knowledge_coverage != "none":
                raise ValueError(
                    "knowledge_coverage debe ser none "
                    "cuando procedure_match=none."
                )

        if self.procedure_match == "partial":
            if not self.procedure_found:
                raise ValueError(
                    "procedure_match=partial requiere "
                    "procedure_found=true."
                )

            if self.procedure is None:
                raise ValueError(
                    "procedure_match=partial requiere "
                    "un procedimiento identificado."
                )

            if self.execution_eligible:
                raise ValueError(
                    "Un procedimiento partial no puede "
                    "ser elegible para ejecución."
                )

            if self.knowledge_coverage != "partial":
                raise ValueError(
                    "procedure_match=partial requiere "
                    "knowledge_coverage=partial."
                )

        if self.procedure_match == "exact":
            if not self.procedure_found:
                raise ValueError(
                    "procedure_match=exact requiere "
                    "procedure_found=true."
                )

            if self.procedure is None:
                raise ValueError(
                    "procedure_match=exact requiere "
                    "un procedimiento identificado."
                )

        if (
            self.recommended_next_step
            == "procedure_execution"
        ):
            if not (
                self.procedure_match == "exact"
                and self.execution_eligible
            ):
                raise ValueError(
                    "procedure_execution requiere "
                    "procedure_match=exact y "
                    "execution_eligible=true."
                )

        if (
            self.recommended_next_step
            == "knowledge_review"
            and self.procedure_match == "none"
        ):
            raise ValueError(
                "knowledge_review no es coherente "
                "cuando procedure_match=none."
            )

        if (
            self.recommended_next_step
            == "human_escalation"
            and not self.escalation.required
        ):
            raise ValueError(
                "human_escalation requiere "
                "escalation.required=true."
            )

        if self.criticality_source == "unknown":
            if self.corporate_criticality != "unknown":
                raise ValueError(
                    "criticality_source=unknown requiere "
                    "corporate_criticality=unknown."
                )

        return self


# ============================================================
# PROCEDURE EXECUTION AGENT CONTRACT
# ============================================================

ProcedureStepType = Literal[
    "information",
    "validation",
    "human_action",
    "technical_operation",
    "wait",
    "decision",
    "escalation",
    "unknown",
]

OperationDomain = Literal[
    "azure",
    "windows",
    "linux",
    "database",
    "networking",
    "microsoft365",
    "itsm",
    "human",
    "unknown",
]

OperationKind = Literal[
    "read",
    "write",
    "wait",
    "human",
    "none",
]

ProcedureNextAction = Literal[
    "execute_step",
    "continue",
    "repeat",
    "wait",
    "resolved",
    "escalate",
    "blocked",
]


class ProcedureExecutionReference(BaseModel):
    id: str
    name: str
    version: str | None = None


class ProcedureExecutionStep(BaseModel):
    id: str
    description: str

    step_type: ProcedureStepType

    operation_domain: OperationDomain
    operation_kind: OperationKind

    target_resource: str | None = None

    required_parameters: list[str] = Field(
        default_factory=list
    )

    preconditions: list[str] = Field(
        default_factory=list
    )

    expected_result: str | None = None
    verification: str | None = None


class ProcedureExecutionResult(BaseModel):
    alert_id: str

    procedure: ProcedureExecutionReference

    execution_allowed: bool
    blocked_by_policy: bool

    total_steps: int = Field(
        ge=0,
        le=8,
    )

    current_step: int = Field(
        ge=0
    )

    step: ProcedureExecutionStep | None

    resolution_criteria: str | None = None

    next_action: ProcedureNextAction

    escalation: EscalationInfo

    requires_clarification: bool

    missing_information: list[str] = Field(
        default_factory=list
    )

    source_documents: list[str] = Field(
        default_factory=list
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    @model_validator(mode="after")
    def validate_execution_consistency(self):
        """
        Valida que la salida del Procedure Execution Agent
        respete el contrato operativo.
        """

        if self.total_steps == 0:
            if self.step is not None:
                raise ValueError(
                    "step debe ser null cuando total_steps=0."
                )

        if self.current_step > self.total_steps:
            raise ValueError(
                "current_step no puede ser mayor "
                "que total_steps."
            )

        if self.blocked_by_policy:
            if self.execution_allowed:
                raise ValueError(
                    "Una operación bloqueada por política "
                    "no puede estar permitida."
                )

            if self.next_action != "blocked":
                raise ValueError(
                    "blocked_by_policy=true requiere "
                    "next_action=blocked."
                )

        if self.next_action == "execute_step":
            if not self.execution_allowed:
                raise ValueError(
                    "execute_step requiere "
                    "execution_allowed=true."
                )

            if self.blocked_by_policy:
                raise ValueError(
                    "execute_step no puede utilizarse "
                    "cuando blocked_by_policy=true."
                )

            if self.step is None:
                raise ValueError(
                    "execute_step requiere un step."
                )

        if self.next_action in {
            "continue",
            "repeat",
            "wait",
            "resolved",
            "escalate",
        }:
            if self.step is None:
                raise ValueError(
                    f"{self.next_action} requiere "
                    "un paso previamente interpretado."
                )

        if self.next_action == "escalate":
            if not self.escalation.required:
                raise ValueError(
                    "next_action=escalate requiere "
                    "escalation.required=true."
                )

        if self.escalation.required:
            if (
                self.escalation.team is None
                and self.escalation.level is None
                and self.escalation.criteria is None
            ):
                raise ValueError(
                    "escalation.required=true requiere "
                    "algún dato documentado de escalado."
                )

        if self.requires_clarification:
            if not self.missing_information:
                raise ValueError(
                    "requires_clarification=true requiere "
                    "missing_information."
                )

        return self

# ============================================================
# PROCEDURE VALIDATION AGENT CONTRACT
# ============================================================

ProcedureValidationStatus = Literal[
    "satisfied",
    "not_satisfied",
    "indeterminate",
]

ProcedureValidationNextAction = Literal[
    "continue",
    "repeat",
    "wait",
    "resolved",
    "escalate",
    "blocked",
]


class ProcedureValidationEscalation(BaseModel):
    """
    Propuesta cognitiva de escalado.

    No modifica ProcedureRuntimeState
    ni constituye autorización.
    """

    model_config = {
        "extra": "forbid",
        "frozen": True,
        "revalidate_instances": "always",
    }

    required: bool
    team: str | None = None
    level: str | None = None
    criteria: str | None = None

    @model_validator(mode="after")
    def validate_escalation_consistency(
        self,
    ):
        if self.required:
            if (
                self.team is None
                and self.level is None
                and self.criteria is None
            ):
                raise ValueError(
                    "required=true requiere "
                    "algún dato de escalado."
                )

        else:
            if (
                self.team is not None
                or self.level is not None
                or self.criteria is not None
            ):
                raise ValueError(
                    "required=false no puede "
                    "contener datos de escalado."
                )

        return self


class ProcedureValidationResult(BaseModel):
    """
    Salida cognitiva del Procedure Agent
    al interpretar un resultado operacional.

    proposed_next_action es únicamente una
    propuesta. Python decidirá posteriormente
    si la transición es válida.

    Deliberadamente NO contiene:
    - workflow_status;
    - step_status;
    - approval_status;
    - target_resource;
    - resolved_parameters;
    - success;
    - technical_success.
    """

    model_config = {
        "extra": "forbid",
        "frozen": True,
        "revalidate_instances": "always",
    }

    operation_id: str

    validation_status: (
        ProcedureValidationStatus
    )

    proposed_next_action: (
        ProcedureValidationNextAction
    )

    validation_summary: str

    escalation: (
        ProcedureValidationEscalation
    )

    @model_validator(mode="after")
    def validate_result_consistency(
        self,
    ):
        if (
            self.proposed_next_action
            == "escalate"
        ):
            if not self.escalation.required:
                raise ValueError(
                    "proposed_next_action=escalate "
                    "requiere escalation.required=true."
                )

        elif self.escalation.required:
            raise ValueError(
                "Sólo proposed_next_action=escalate "
                "puede declarar escalation.required=true."
            )

        return self
