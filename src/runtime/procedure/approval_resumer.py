from __future__ import annotations

from typing import (
    Any,
)

from .approval_resolution import (
    ApprovalResumeInstruction,
)

from .approval_store import (
    PendingApprovalStore,
)

from .models import (
    ApprovedProcedureStep,
)

from .workflow import (
    ApprovalOutcome,
    ApprovalRequest,
)


class ApprovalResumeError(
    RuntimeError
):
    """
    Error general durante la reanudación de una
    aprobación HITL.
    """

    pass


class ApprovalResumeMismatchError(
    ApprovalResumeError
):
    """
    El checkpoint restaurado no coincide
    exactamente con la identidad de aprobación
    que pretendemos reanudar.

    Esta condición es de seguridad y debe
    producir fail-closed.
    """

    pass


async def restore_and_verify_pending_request(
    *,
    workflow: Any,
    instruction: ApprovalResumeInstruction,
    expected_conversation_id: str | None = None,
    checkpoint_storage: Any | None = None,
) -> ApprovalRequest:
    """
    Restaura el checkpoint pero NO responde todavía.

    Primero exige que Agent Framework reemita
    exactamente la solicitud HITL esperada.

    Se comprueban:

        request_id
        approval_id
        workflow_id

    contra la identidad recuperada previamente
    del PendingApprovalStore.

    Si existe cualquier discrepancia:

        NO se envía respuesta.
    """

    pending_events = []
    unexpected_outputs = []

    run_kwargs = {
        "checkpoint_id": (
            instruction.checkpoint_id
        ),
        "stream": True,
    }

    if checkpoint_storage is not None:
        run_kwargs[
            "checkpoint_storage"
        ] = checkpoint_storage

    async for event in workflow.run(
        **run_kwargs
    ):
        if (
            event.type
            == "request_info"
        ):
            pending_events.append(
                event
            )

        elif (
            event.type
            == "output"
        ):
            unexpected_outputs.append(
                event.data
            )

    if unexpected_outputs:
        raise ApprovalResumeMismatchError(
            "El checkpoint restaurado produjo "
            "output antes de recibir la decisión "
            "HITL."
        )

    if not pending_events:
        raise ApprovalResumeMismatchError(
            "El checkpoint restaurado no contiene "
            "ninguna solicitud HITL pendiente."
        )

    if len(
        pending_events
    ) != 1:
        raise ApprovalResumeMismatchError(
            "El checkpoint restaurado contiene "
            "un número inesperado de solicitudes "
            "HITL pendientes."
        )

    event = (
        pending_events[0]
    )

    if (
        event.request_id
        != instruction.request_id
    ):
        raise ApprovalResumeMismatchError(
            "request_id restaurado no coincide "
            "con la correlación HITL persistida."
        )

    request = (
        event.data
    )

    if not isinstance(
        request,
        ApprovalRequest,
    ):
        raise ApprovalResumeMismatchError(
            "La solicitud HITL restaurada no es "
            "un ApprovalRequest válido."
        )

    if (
        request.approval_id
        != instruction.approval_id
    ):
        raise ApprovalResumeMismatchError(
            "approval_id restaurado no coincide "
            "con la correlación HITL persistida."
        )

    if (
        request.workflow_id
        != instruction.workflow_id
    ):
        raise ApprovalResumeMismatchError(
            "workflow_id restaurado no coincide "
            "con la correlación HITL persistida."
        )

    if (
        expected_conversation_id
        is not None
    ):
        if (
            not isinstance(
                expected_conversation_id,
                str,
            )
            or not expected_conversation_id
            or not expected_conversation_id.strip()
            or (
                expected_conversation_id
                != expected_conversation_id.strip()
            )
        ):
            raise ValueError(
                "expected_conversation_id debe ser "
                "un string no vacío y exacto."
            )

        if (
            request.conversation_id
            != expected_conversation_id
        ):
            raise ApprovalResumeMismatchError(
                "conversation_id restaurado no "
                "coincide con la conversación "
                "autenticada del canal."
            )

    return request


async def resume_approval_workflow(
    *,
    workflow: Any,
    instruction: ApprovalResumeInstruction,
    store: PendingApprovalStore,
    expected_conversation_id: str | None = None,
) -> (
    ApprovedProcedureStep
    | ApprovalOutcome
):
    """
    Reanuda exactamente una aprobación HITL.

    Secuencia obligatoria:

        1. restaurar checkpoint;
        2. obtener RequestInfoEvent real;
        3. verificar identidad exacta;
        4. sólo entonces responder;
        5. validar el resultado producido.

    Nunca construye ni modifica autoridad
    operacional.

    La respuesta enviada a Agent Framework es
    exclusivamente el booleano derivado de la
    decisión humana validada.
    """

    if not isinstance(
        instruction,
        ApprovalResumeInstruction,
    ):
        raise TypeError(
            "instruction debe ser "
            "ApprovalResumeInstruction."
        )

    await restore_and_verify_pending_request(
        workflow=workflow,
        instruction=instruction,
        expected_conversation_id=(
            expected_conversation_id
        ),
    )

    claimed = (
        store.claim(
            approval_id=(
                instruction.approval_id
            ),

            approved=(
                instruction.approved
            ),
        )
    )

    # Defensa adicional:
    # el registro reclamado debe corresponder
    # exactamente con la instrucción verificada.
    if (
        claimed.workflow_id
        != instruction.workflow_id
        or claimed.request_id
        != instruction.request_id
        or claimed.checkpoint_id
        != instruction.checkpoint_id
    ):
        raise ApprovalResumeMismatchError(
            "La correlación HITL reclamada no "
            "coincide con la instrucción de "
            "reanudación verificada."
        )

    outputs = []
    unexpected_requests = []

    async for event in workflow.run(
        responses={
            instruction.request_id:
                instruction.approved,
        },

        stream=True,
    ):
        if (
            event.type
            == "output"
        ):
            outputs.append(
                event.data
            )

        elif (
            event.type
            == "request_info"
        ):
            unexpected_requests.append(
                event
            )

    if unexpected_requests:
        raise ApprovalResumeError(
            "La aprobación generó una nueva "
            "solicitud HITL inesperada."
        )

    if len(
        outputs
    ) != 1:
        raise ApprovalResumeError(
            "La reanudación HITL no produjo "
            "exactamente un resultado."
        )

    result = (
        outputs[0]
    )

    if instruction.approved:
        if not isinstance(
            result,
            ApprovedProcedureStep,
        ):
            raise ApprovalResumeError(
                "Una aprobación positiva no produjo "
                "ApprovedProcedureStep."
            )

        if (
            result.workflow_id
            != instruction.workflow_id
        ):
            raise ApprovalResumeMismatchError(
                "El workflow_id post-HITL no "
                "coincide con el workflow aprobado."
            )

        if (
            result.approval_id
            != instruction.approval_id
        ):
            raise ApprovalResumeMismatchError(
                "El approval_id post-HITL no "
                "coincide con la aprobación "
                "procesada."
            )

        if (
            result.approved
            is not True
        ):
            raise ApprovalResumeError(
                "ApprovedProcedureStep no está "
                "marcado como aprobado."
            )

        store.complete(
            instruction.approval_id
        )

        return result

    if not isinstance(
        result,
        ApprovalOutcome,
    ):
        raise ApprovalResumeError(
            "Un rechazo HITL no produjo "
            "ApprovalOutcome."
        )

    if (
        result.workflow_id
        != instruction.workflow_id
    ):
        raise ApprovalResumeMismatchError(
            "El workflow_id del rechazo no "
            "coincide con el workflow esperado."
        )

    if (
        result.approved
        is not False
    ):
        raise ApprovalResumeError(
            "ApprovalOutcome de rechazo contiene "
            "approved distinto de False."
        )

    store.complete(
        instruction.approval_id
    )

    return result