from __future__ import annotations

import json

from uuid import (
    NAMESPACE_URL,
    uuid4,
    uuid5,
)


_OPERATION_ID_NAMESPACE = (
    uuid5(
        NAMESPACE_URL,
        (
            "https://ai-support-platform.invalid/"
            "operation-id"
        ),
    )
)


def create_workflow_id() -> str:
    """
    Identificador único de una ejecución concreta.

    Una misma alerta puede tener varias ejecuciones;
    cada una debe recibir un workflow_id diferente.
    """

    return f"wf-{uuid4()}"


def create_approval_id() -> str:
    """
    Identificador único de una solicitud HITL.

    No sustituye todavía al nonce durable de
    producción.
    """

    return f"apr-{uuid4()}"


def create_operation_id(
    *,
    workflow_id: str,
    approval_id: str,
    alert_id: str,
    procedure_id: str,
    current_step: int,
    step_id: str,
) -> str:
    """
    Identidad estable de una operación concreta.

    Se deriva exclusivamente de identidad
    determinista ya existente.

    No procede de LLM, Foundry, MCP ni herramienta.

    La misma operación aprobada produce siempre el
    mismo operation_id.
    """

    required_values = {
        "workflow_id": workflow_id,
        "approval_id": approval_id,
        "alert_id": alert_id,
        "procedure_id": procedure_id,
        "step_id": step_id,
    }

    missing = [
        name
        for name, value
        in required_values.items()
        if not value
    ]

    if missing:
        raise ValueError(
            "No puede generarse operation_id. "
            "Identidad incompleta: "
            + ", ".join(missing)
        )

    if current_step < 1:
        raise ValueError(
            "current_step debe ser mayor que cero "
            "para generar operation_id."
        )

    canonical_identity = json.dumps(
        {
            "workflow_id":
                workflow_id,

            "approval_id":
                approval_id,

            "alert_id":
                alert_id,

            "procedure_id":
                procedure_id,

            "current_step":
                current_step,

            "step_id":
                step_id,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return (
        "op-"
        + str(
            uuid5(
                _OPERATION_ID_NAMESPACE,
                canonical_identity,
            )
        )
    )
