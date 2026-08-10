from __future__ import annotations

import json

from agent_framework import (
    WorkflowContext,
)

from .models import (
    ProcedureRuntimeState,
)


PROCEDURE_RUNTIME_STATE_KEY = (
    "procedure_runtime_state"
)


def store_procedure_runtime_state(
    ctx: WorkflowContext,
    state: ProcedureRuntimeState,
) -> None:
    """
    Guarda el ProcedureRuntimeState autoritativo
    en el workflow state de Agent Framework.

    El valor almacenado es un snapshot JSON-native,
    no la instancia Pydantic recibida.

    Esto NO implica por sí mismo persistencia durable:
    la durabilidad depende de que el workflow utilice
    checkpoint storage.
    """

    snapshot = state.model_dump(
        mode="json"
    )

    # Fail-closed:
    # debe ser JSON estricto.
    json.dumps(
        snapshot,
        allow_nan=False,
    )

    # Fail-closed:
    # debe reconstruir exactamente
    # el contrato autoritativo.
    restored = (
        ProcedureRuntimeState
        .model_validate(
            snapshot
        )
    )

    if restored != state:
        raise ValueError(
            "El snapshot de ProcedureRuntimeState "
            "no conserva exactamente el estado "
            "autoritativo."
        )

    ctx.set_state(
        PROCEDURE_RUNTIME_STATE_KEY,
        snapshot,
    )

def load_procedure_runtime_state(
    ctx: WorkflowContext,
) -> ProcedureRuntimeState:
    """
    Recupera el ProcedureRuntimeState autoritativo
    desde workflow state y lo revalida.

    Sólo se acepta el snapshot JSON-native exacto
    producido por store_procedure_runtime_state().
    """

    snapshot = ctx.get_state(
        PROCEDURE_RUNTIME_STATE_KEY,
        None,
    )

    if snapshot is None:
        raise RuntimeError(
            "No existe ProcedureRuntimeState "
            "autoritativo en workflow state."
        )

    if not isinstance(
        snapshot,
        dict,
    ):
        raise TypeError(
            "ProcedureRuntimeState debe estar "
            "almacenado como snapshot dict JSON-native."
        )

    json.dumps(
        snapshot,
        allow_nan=False,
    )

    state = (
        ProcedureRuntimeState
        .model_validate(
            snapshot
        )
    )

    canonical_snapshot = (
        state.model_dump(
            mode="json"
        )
    )

    if canonical_snapshot != snapshot:
        raise ValueError(
            "El snapshot autoritativo almacenado "
            "no coincide exactamente con el contrato "
            "ProcedureRuntimeState canónico."
        )

    return state
