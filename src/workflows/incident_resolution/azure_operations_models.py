from __future__ import annotations

from typing import Literal

from .operation_models import (
    OperationRequest,
    OperationResult,
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


class AzureOperationResult(
    OperationResult
):
    """
    Especialización Azure del contrato común
    OperationResult.

    FASE 15.3 no añade todavía campos específicos
    de proveedor ni evidencia técnica.
    """

    pass
