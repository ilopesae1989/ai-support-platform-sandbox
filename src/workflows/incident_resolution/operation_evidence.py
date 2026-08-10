from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
)


class OperationEvidence(BaseModel):
    """
    Envelope vendor-neutral de evidencia técnica
    asociada a una operación.

    FASE 15.4 establece exclusivamente la frontera
    contractual.

    El modelo permanece deliberadamente vacío en
    esta subfase.

    Las siguientes fases incorporarán de forma
    explícita y controlada:

    - operation_id;
    - correlación;
    - identidad del procedimiento;
    - identidad operacional;
    - evidencia de herramienta;
    - evidencia MCP;
    - resultado técnico.

    No se permiten campos arbitrarios mientras esos
    contratos no hayan sido definidos.
    """

    model_config = ConfigDict(
        extra="forbid"
    )
