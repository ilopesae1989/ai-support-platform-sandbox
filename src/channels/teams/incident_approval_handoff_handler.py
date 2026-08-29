from __future__ import annotations

from collections.abc import Callable

from dataclasses import dataclass

from typing import Any

from microsoft_teams.api import (
    AdaptiveCardInvokeActivity,
    AdaptiveCardInvokeResponse,
)

from microsoft_teams.apps import (
    ActivityContext,
    App,
)

from src.runtime.procedure.approval_correlation import (
    ApprovalCorrelationNotFoundError,
)

from src.runtime.procedure.approval_resolution import (
    resolve_approval_channel_action,
)

from src.runtime.procedure.approval_store import (
    PendingApprovalStore,
)

from .action_parser import (
    TeamsApprovalActionError,
)

from .activity_identity import (
    TeamsActivityIdentityError,
)

from .approval_authorization import (
    AuthorizedTeamsApprovalInvocation,
    ExactTeamsApprovalPolicy,
    TeamsApprovalAuthorizationError,
    authorize_teams_approval_invocation,
)

from .approval_handler import (
    _build_error_response,
    _build_success_response,
)

from .approval_invocation import (
    build_teams_approval_invocation,
)

from .incident_continuation_store import (
    IncidentContinuationConflictError,
    SqliteIncidentContinuationStore,
)


WorkflowFactory = Callable[
    [],
    Any,
]

Processor = Callable[
    ...,
    Any,
]


@dataclass(
    frozen=True
)
class TeamsApprovalHandlerDependencies:
    """
    Boundary rápido Teams -> durable handoff.

    workflow_factory y processor se conservan como
    dependencias del bootstrap/worker, pero este
    handler NO los ejecuta.

    El Action.Execute únicamente:

        autentica
        autoriza
        valida approval_id existente
        persiste AuthorizedTeamsApprovalInvocation
        devuelve ACK

    No restaura checkpoints.
    No ejecuta workflows.
    No llama Foundry/MCP/Azure.
    """

    policy: ExactTeamsApprovalPolicy

    store: PendingApprovalStore

    continuation_store: (
        SqliteIncidentContinuationStore
    )

    workflow_factory: WorkflowFactory

    processor: Processor


def enqueue_authorized_teams_incident_approval(
    *,
    invocation: AuthorizedTeamsApprovalInvocation,
    store: PendingApprovalStore,
    continuation_store: (
        SqliteIncidentContinuationStore
    ),
) -> bool:
    """
    Handoff durable previo al ACK.

    Primero demuestra que approval_id corresponde
    a una correlación HITL ya registrada.

    Después persiste exclusivamente la decisión
    Teams autenticada/autorizada.

    No consume la aprobación HITL.
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
        raise RuntimeError(
            "approval_id resuelto no coincide "
            "con la invocación autorizada."
        )

    continuation_store.enqueue(
        invocation
    )

    return instruction.approved


async def handle_teams_approval_action(
    *,
    ctx: ActivityContext[
        AdaptiveCardInvokeActivity
    ],
    dependencies: TeamsApprovalHandlerDependencies,
) -> AdaptiveCardInvokeResponse:
    """
    Boundary síncrono-rápido para Action.Execute.

    IMPORTANTE:
    no existe await operacional dentro de este
    handler.

    El trabajo largo comienza posteriormente
    en IncidentContinuationWorker.
    """

    if not isinstance(
        dependencies,
        TeamsApprovalHandlerDependencies,
    ):
        raise TypeError(
            "dependencies debe ser "
            "TeamsApprovalHandlerDependencies."
        )

    try:
        invocation = (
            build_teams_approval_invocation(
                ctx.activity
            )
        )

        authorized = (
            authorize_teams_approval_invocation(
                invocation=invocation,
                policy=(
                    dependencies.policy
                ),
            )
        )

        approved = (
            enqueue_authorized_teams_incident_approval(
                invocation=authorized,
                store=(
                    dependencies.store
                ),
                continuation_store=(
                    dependencies
                    .continuation_store
                ),
            )
        )

        return (
            _build_success_response(
                approved=approved
            )
        )

    except (
        TeamsActivityIdentityError,
        TeamsApprovalActionError,
        TeamsApprovalAuthorizationError,
        ApprovalCorrelationNotFoundError,
        IncidentContinuationConflictError,
    ):
        return (
            _build_error_response(
                status_code=400,
                code="ApprovalRejected",
                message=(
                    "La aprobación no puede "
                    "procesarse."
                ),
            )
        )

    except Exception:
        return (
            _build_error_response(
                status_code=500,
                code="InternalError",
                message=(
                    "No se pudo registrar "
                    "la aprobación."
                ),
            )
        )


def register_teams_approval_handler(
    *,
    app: App,
    dependencies: TeamsApprovalHandlerDependencies,
):
    @app.on_card_action_execute(
        "approval_decision"
    )
    async def handle(
        ctx: ActivityContext[
            AdaptiveCardInvokeActivity
        ],
    ) -> AdaptiveCardInvokeResponse:
        return await (
            handle_teams_approval_action(
                ctx=ctx,
                dependencies=dependencies,
            )
        )

    return handle