from __future__ import annotations

from dataclasses import (
    dataclass,
)

from typing import (
    Any,
)

from src.runtime.procedure.approval_resolution import (
    resolve_approval_channel_action,
)

from src.runtime.procedure.approval_resumer import (
    restore_and_verify_pending_request,
)

from src.runtime.procedure.approval_store import (
    PendingApprovalStore,
)

from .approval_authorization import (
    AuthorizedTeamsApprovalInvocation,
)

from .approval_evidence import (
    ApprovalDecisionEvidence,
    build_teams_approval_evidence_from_request,
)


class IncidentApprovalProcessingError(
    RuntimeError
):
    """
    Error fail-closed durante la continuación
    del incident workflow tras una decisión Teams.

    No concede autoridad operacional.
    """

    pass


@dataclass(
    frozen=True
)
class TeamsIncidentApprovalProcessingResult:
    """
    Resultado application-level de procesar una
    decisión HITL sobre el incident workflow.

    workflow_result:
        output terminal producido por el mismo
        workflow de incidente tras consumir la
        respuesta HITL.

    approval_evidence:
        evidencia independiente de la decisión
        humana autenticada y autorizada.
    """

    workflow_result: Any

    approval_evidence: (
        ApprovalDecisionEvidence
    )


async def process_authorized_teams_incident_approval(
    *,
    invocation: AuthorizedTeamsApprovalInvocation,
    store: PendingApprovalStore,
    workflow: Any,
    checkpoint_storage: Any,
) -> TeamsIncidentApprovalProcessingResult:
    """
    Continúa exactamente el incident workflow
    autorizado por una decisión Teams ya validada.

    Orden obligatorio:

        AuthorizedTeamsApprovalInvocation
            ↓
        resolución técnica desde pending store
            ↓
        restore + verificación ApprovalRequest
            ↓
        claim monotónico
            ↓
        verificar correlación reclamada
            ↓
        workflow.run(responses=...)
            ↓
        output terminal único
            ↓
        evidence de decisión humana
            ↓
        complete

    No reconstruye autoridad desde Teams.
    """

    if not isinstance(
        invocation,
        AuthorizedTeamsApprovalInvocation,
    ):
        raise TypeError(
            "invocation debe ser "
            "AuthorizedTeamsApprovalInvocation."
        )

    instruction = (
        resolve_approval_channel_action(
            action=(
                invocation.action
            ),
            store=store,
        )
    )

    if (
        instruction.approval_id
        != invocation.action.approval_id
    ):
        raise IncidentApprovalProcessingError(
            "La instrucción HITL no corresponde "
            "al approval_id autorizado."
        )

    restored_request = await (
        restore_and_verify_pending_request(
            workflow=workflow,
            instruction=instruction,
            expected_conversation_id=(
                invocation
                .operator
                .conversation_id
            ),
            checkpoint_storage=(
                checkpoint_storage
            ),
        )
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

    if (
        claimed.approval_id
        != instruction.approval_id
        or claimed.workflow_id
        != instruction.workflow_id
        or claimed.request_id
        != instruction.request_id
        or claimed.checkpoint_id
        != instruction.checkpoint_id
    ):
        raise IncidentApprovalProcessingError(
            "La correlación HITL reclamada no "
            "coincide exactamente con la "
            "instrucción verificada."
        )

    outputs = []
    unexpected_requests = []

    async for event in workflow.run(
        responses={
            instruction.request_id:
                instruction.approved,
        },
        checkpoint_storage=(
            checkpoint_storage
        ),
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
        raise IncidentApprovalProcessingError(
            "La continuación HITL produjo una "
            "nueva solicitud HITL inesperada."
        )

    if len(outputs) != 1:
        raise IncidentApprovalProcessingError(
            "La continuación del incident workflow "
            "debe producir exactamente un output. "
            f"Actual={len(outputs)}."
        )

    workflow_result = (
        outputs[0]
    )

    if (
        getattr(
            workflow_result,
            "workflow_id",
            instruction.workflow_id,
        )
        != instruction.workflow_id
    ):
        raise IncidentApprovalProcessingError(
            "El workflow_id del resultado no "
            "coincide con la aprobación procesada."
        )

    if (
        instruction.approved
        and hasattr(
            workflow_result,
            "approval_id",
        )
        and (
            workflow_result.approval_id
            != instruction.approval_id
        )
    ):
        raise IncidentApprovalProcessingError(
            "El approval_id del resultado no "
            "coincide con la aprobación procesada."
        )

    approval_evidence = (
        build_teams_approval_evidence_from_request(
            invocation=invocation,
            request=restored_request,
        )
    )

    store.complete(
        instruction.approval_id
    )

    return (
        TeamsIncidentApprovalProcessingResult(
            workflow_result=(
                workflow_result
            ),
            approval_evidence=(
                approval_evidence
            ),
        )
    )
