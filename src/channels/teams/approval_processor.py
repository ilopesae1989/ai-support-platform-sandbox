from __future__ import annotations

from dataclasses import (
    dataclass,
)

from typing import (
    Any,
)

from src.runtime.procedure.approval_evidence import (
    ApprovalDecisionEvidence,
)

from src.runtime.procedure.approval_resolution import (
    resolve_approval_channel_action,
)

from src.runtime.procedure.approval_resumer import (
    resume_approval_workflow,
)

from src.runtime.procedure.approval_store import (
    PendingApprovalStore,
)

from src.runtime.procedure.models import (
    ApprovedProcedureStep,
)

from src.runtime.procedure.workflow import (
    ApprovalOutcome,
)

from .approval_authorization import (
    AuthorizedTeamsApprovalInvocation,
)

from .approval_evidence import (
    build_teams_approval_evidence,
)


@dataclass(
    frozen=True
)
class TeamsApprovalProcessingResult:
    """
    Resultado completo del boundary Teams HITL.

    workflow_result:
        resultado gobernado producido por
        Agent Framework.

    approval_evidence:
        evidencia inmutable de quién tomó
        la decisión humana.
    """

    workflow_result: (
        ApprovedProcedureStep
        | ApprovalOutcome
    )

    approval_evidence: (
        ApprovalDecisionEvidence
    )


async def process_authorized_teams_approval(
    *,
    invocation: AuthorizedTeamsApprovalInvocation,
    store: PendingApprovalStore,
    workflow: Any,
) -> TeamsApprovalProcessingResult:
    """
    Procesa una decisión Teams que ya ha superado:

        Activity identity extraction
                ↓
        Action.Execute parsing
                ↓
        Teams approval authorization

    Esta función NO recibe:

        procedure_id
        capability_id
        operation_action
        target_resource
        parámetros operacionales
        request_id
        checkpoint_id

    La identidad técnica de reanudación procede
    exclusivamente del PendingApprovalStore.

    La identidad operacional continúa procediendo
    del ApprovalRequest original contenido en el
    checkpoint.
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

            store=(
                store
            ),
        )
    )

    # Defensa explícita.
    #
    # La resolución del store ya es exacta,
    # pero nunca continuamos si la aprobación
    # recuperada no corresponde literalmente
    # a la acción autorizada.
    if (
        instruction.approval_id
        != invocation.action.approval_id
    ):
        raise RuntimeError(
            "La resolución HITL no corresponde "
            "al approval_id autorizado en Teams."
        )

    workflow_result = (
        await resume_approval_workflow(
            workflow=(
                workflow
            ),

            instruction=(
                instruction
            ),

            store=(
                store
            ),

            expected_conversation_id=(
                invocation
                .operator
                .conversation_id
            ),
        )
    )

    approval_evidence = (
        build_teams_approval_evidence(
            invocation=(
                invocation
            ),

            workflow_result=(
                workflow_result
            ),
        )
    )

    return TeamsApprovalProcessingResult(
        workflow_result=(
            workflow_result
        ),

        approval_evidence=(
            approval_evidence
        ),
    )