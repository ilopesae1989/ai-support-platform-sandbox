from __future__ import annotations

from collections.abc import (
    Callable,
)

from dataclasses import (
    dataclass,
)

from typing import (
    Any,
)

from microsoft_teams.api import (
    AdaptiveCardActionErrorResponse,
    AdaptiveCardActionMessageResponse,
    AdaptiveCardInvokeActivity,
    AdaptiveCardInvokeResponse,
    HttpError,
    InnerHttpError,
)

from microsoft_teams.apps import (
    ActivityContext,
    App,
)

from src.runtime.procedure.approval_correlation import (
    ApprovalCorrelationNotFoundError,
)

from src.runtime.procedure.approval_resumer import (
    ApprovalResumeError,
)

from src.runtime.procedure.approval_store import (
    ApprovalAlreadyConsumedError,
    PendingApprovalStore,
)

from .action_parser import (
    TeamsApprovalActionError,
)

from .activity_identity import (
    TeamsActivityIdentityError,
)

from .approval_authorization import (
    ExactTeamsApprovalPolicy,
    TeamsApprovalAuthorizationError,
    authorize_teams_approval_invocation,
)

from .approval_invocation import (
    build_teams_approval_invocation,
)

from .approval_processor import (
    process_authorized_teams_approval,
)


WorkflowFactory = Callable[
    [],
    Any,
]


@dataclass(
    frozen=True
)
class TeamsApprovalHandlerDependencies:
    """
    Dependencias gobernadas del handler Teams.

    Ninguna procede del Action.Execute.

    policy:
        política Python de autorización.

    store:
        correlación HITL durable.

    workflow_factory:
        construye un workflow nuevo capaz de
        restaurar el checkpoint original.
    """

    policy: ExactTeamsApprovalPolicy

    store: PendingApprovalStore

    workflow_factory: WorkflowFactory


def _build_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
) -> AdaptiveCardActionErrorResponse:
    """
    Genera una respuesta de error compatible
    con Universal Actions.

    Nunca expone excepciones internas al cliente.
    """

    if (
        status_code
        not in {
            400,
            500,
        }
    ):
        raise ValueError(
            "status_code debe ser 400 o 500."
        )

    return AdaptiveCardActionErrorResponse(
        status_code=(
            status_code
        ),

        type=(
            "application/vnd.microsoft.error"
        ),

        value=HttpError(
            code=(
                code
            ),

            message=(
                message
            ),

            inner_http_error=(
                InnerHttpError(
                    status_code=(
                        status_code
                    ),

                    body={
                        "error": (
                            message
                        ),
                    },
                )
            ),
        ),
    )


def _build_success_response(
    *,
    approved: bool,
) -> AdaptiveCardActionMessageResponse:
    if approved:
        message = (
            "Aprobación registrada. "
            "El workflow gobernado continuará."
        )

    else:
        message = (
            "Rechazo registrado. "
            "La operación no será autorizada."
        )

    return AdaptiveCardActionMessageResponse(
        status_code=200,

        type=(
            "application/vnd.microsoft.activity.message"
        ),

        value=(
            message
        ),
    )


async def handle_teams_approval_action(
    *,
    ctx: ActivityContext[
        AdaptiveCardInvokeActivity
    ],
    dependencies: TeamsApprovalHandlerDependencies,
) -> AdaptiveCardInvokeResponse:
    """
    Boundary real Teams -> HITL.

    Orden obligatorio:

        Teams Activity
            ↓
        identity extraction
            ↓
        Action.Execute validation
            ↓
        authorization
            ↓
        workflow factory
            ↓
        durable HITL resume
            ↓
        approval evidence
            ↓
        Teams response

    El handler jamás reconstruye autoridad
    operacional desde la tarjeta.
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
                invocation=(
                    invocation
                ),

                policy=(
                    dependencies.policy
                ),
            )
        )

        workflow = (
            dependencies
            .workflow_factory()
        )

        processed = (
            await process_authorized_teams_approval(
                invocation=(
                    authorized
                ),

                store=(
                    dependencies.store
                ),

                workflow=(
                    workflow
                ),
            )
        )

        approved = (
            processed
            .approval_evidence
            .decision
            .value
            == "approve"
        )

        return (
            _build_success_response(
                approved=(
                    approved
                )
            )
        )

    except (
        TeamsActivityIdentityError,
        TeamsApprovalActionError,
        TeamsApprovalAuthorizationError,
        ApprovalCorrelationNotFoundError,
        ApprovalAlreadyConsumedError,
        ApprovalResumeError,
    ):
        # No revelamos:
        #
        # - si approval_id existía;
        # - quién estaba autorizado;
        # - checkpoint_id;
        # - request_id;
        # - motivos internos de seguridad.
        return (
            _build_error_response(
                status_code=400,

                code=(
                    "ApprovalRejected"
                ),

                message=(
                    "La aprobación no puede "
                    "procesarse."
                ),
            )
        )

    except Exception:
        # Error inesperado.
        #
        # El detalle deberá ir posteriormente
        # a observabilidad, nunca a Teams.
        return (
            _build_error_response(
                status_code=500,

                code=(
                    "InternalError"
                ),

                message=(
                    "No se pudo procesar "
                    "la aprobación."
                ),
            )
        )


def register_teams_approval_handler(
    *,
    app: App,
    dependencies: TeamsApprovalHandlerDependencies,
):
    """
    Registra exclusivamente la acción:

        approval_decision

    que coincide con:

        SubmitData("approval_decision", ...)

    de nuestra Adaptive Card.
    """

    @app.on_card_action_execute(
        "approval_decision"
    )
    async def handle(
        ctx: ActivityContext[
            AdaptiveCardInvokeActivity
        ],
    ) -> AdaptiveCardInvokeResponse:
        return (
            await handle_teams_approval_action(
                ctx=ctx,
                dependencies=dependencies,
            )
        )

    return handle