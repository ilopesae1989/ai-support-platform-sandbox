from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from src.runtime.procedure.models import (
    OperationKind,
)

from .operation_models import (
    OperationRequest,
)


class AzureOperationRequest(
    OperationRequest
):
    """
    Especialización Azure del contrato común
    OperationRequest.

    No añade autoridad operacional.

    Sigue representando únicamente una operación
    Azure candidata que debe atravesar
    PreCallSecurityVerifier antes de poder llegar
    a AzureOperationsExecutor.
    """

    pass


class VerifiedAzureOperationRequest(
    AzureOperationRequest
):
    """
    Operación Azure que ha superado la frontera
    determinista de seguridad pre-call.

    Sólo PreCallSecurityVerifier debe construir
    este contrato dentro del flujo productivo.
    """

    security_verified: Literal[
        True
    ] = True

    verification_source: Literal[
        "pre_call_security_verifier"
    ] = "pre_call_security_verifier"


class AzureOperationResult(BaseModel):
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
