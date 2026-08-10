from __future__ import annotations

from pydantic import (
    BaseModel,
    Field,
)

from src.runtime.procedure.models import (
    NextAction,
    OperationKind,
    ResolvedParameter,
)


class OperationRequest(BaseModel):
    """
    Contrato común vendor-neutral de una operación
    candidata.

    Conserva exactamente la identidad operacional
    necesaria entre:

        ApprovedProcedureStep
            ↓
        operación candidata del dominio
            ↓
        verificación pre-call específica
            ↓
        operación verificada

    IMPORTANTE:

    OperationRequest NO representa autorización.

    Su existencia no permite ejecutar ninguna
    operación por sí misma.

    La autoridad operacional continúa dependiendo
    de la verificación determinista específica del
    dominio antes de alcanzar su executor.
    """

    workflow_id: str
    approval_id: str

    alert_id: str

    correlation_id: str | None = None
    conversation_id: str | None = None

    procedure_id: str
    procedure_version: str | None = None

    current_step: int
    step_id: str

    operation_domain: str
    operation_kind: OperationKind

    next_action: NextAction

    target_resource: str | None = None

    required_parameters: list[str] = Field(
        default_factory=list
    )

    resolved_parameters: list[
        ResolvedParameter
    ] = Field(
        default_factory=list
    )


class OperationResult(BaseModel):
    """
    Contrato común vendor-neutral del resultado
    actualmente producido por un executor de
    operaciones.

    FASE 15.3 realiza únicamente la extracción del
    contrato existente.

    No incorpora todavía:

    - operation_id;
    - identidad de correlación adicional;
    - identidad operacional completa;
    - evidencia de herramienta;
    - evidencia MCP;
    - evidencia técnica estructurada.

    Esos elementos pertenecen a las siguientes
    subfases de FASE 15.
    """

    workflow_id: str
    approval_id: str

    alert_id: str

    correlation_id: str | None = None

    procedure_id: str
    procedure_version: str | None = None

    current_step: int
    step_id: str

    operation_kind: OperationKind

    target_resource: str | None = None

    success: bool

    response_text: str | None = None
    error: str | None = None
