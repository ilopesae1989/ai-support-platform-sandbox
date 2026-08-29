from __future__ import annotations

import os

from dataclasses import (
    dataclass,
    field,
)

from pathlib import (
    Path,
)

from microsoft_teams.apps import (
    App,
)

from src.runtime.procedure.approval_store import (
    SqlitePendingApprovalStore,
)

from src.runtime.procedure.workflow import (
    build_procedure_approval_workflow,
)

from src.workflows.incident_resolution.checkpoint_storage import (
    build_incident_checkpoint_storage,
)

from src.workflows.incident_resolution.operation_dispatch_ledger import (
    SqliteOperationDispatchLedger,
)

from src.workflows.incident_resolution.workflow import (
    build_incident_resolution_workflow,
)

from .approval_authorization import (
    ExactTeamsApprovalPolicy,
    TeamsApprovalPrincipal,
)

from .incident_approval_handoff_handler import (
    TeamsApprovalHandlerDependencies,
    register_teams_approval_handler,
)

from .incident_approval_processor import (
    process_authorized_teams_incident_approval,
)

from .incident_continuation_store import (
    SqliteIncidentContinuationStore,
)

from .incident_continuation_worker import (
    IncidentContinuationWorker,
    IncidentContinuationWorkerDependencies,
)

from .incident_terminal_presenter import (
    notify_teams_incident_terminal_result,
)
from .outbound_adapter import (
    TeamsOutboundDependencies,
)

from .conversation_binding_store import (
    SqliteTeamsConversationBindingStore,
)

from .conversation_handler import (
    TeamsConversationHandlerDependencies,
    register_teams_conversation_handler,
)


class TeamsHitlConfigurationError(
    ValueError
):
    pass


def _required_environment_value(
    name: str,
) -> str:
    value = os.getenv(
        name
    )

    if (
        value is None
        or not value
        or not value.strip()
        or value != value.strip()
    ):
        raise TeamsHitlConfigurationError(
            f"{name} debe existir y contener "
            "un valor exacto no vacío."
        )

    return value


@dataclass(
    frozen=True
)
class TeamsHitlSettings:
    """
    Configuración del boundary Teams de sandbox.

    Contiene únicamente configuración de:

    - autenticación Teams;
    - aprobación HITL;
    - persistencia de bindings de transporte.

    No contiene autoridad operacional sobre Azure.
    """

    client_id: str

    client_secret: str = field(
        repr=False
    )

    bot_tenant_id: str

    teams_channel_tenant_id: str

    approver_aad_object_id: str

    pending_database_path: Path

    checkpoint_path: Path

    operation_dispatch_database_path: Path

    conversation_binding_database_path: Path

    messaging_endpoint: str = (
        "/api/messages"
    )

    @classmethod
    def from_environment(
        cls,
    ) -> "TeamsHitlSettings":
        pending_database_path = Path(
            _required_environment_value(
                "TEAMS_HITL_PENDING_DB"
            )
        )

        checkpoint_path = Path(
            _required_environment_value(
                "TEAMS_HITL_CHECKPOINT_DIR"
            )
        )

        operation_dispatch_database_path = Path(
            _required_environment_value(
                "TEAMS_OPERATION_DISPATCH_DB"
            )
        )

        conversation_binding_database_path = Path(
            _required_environment_value(
                "TEAMS_CONVERSATION_BINDING_DB"
            )
        )

        return cls(
            client_id=(
                _required_environment_value(
                    "CLIENT_ID"
                )
            ),

            client_secret=(
                _required_environment_value(
                    "CLIENT_SECRET"
                )
            ),

            bot_tenant_id=(
                _required_environment_value(
                    "TENANT_ID"
                )
            ),

            teams_channel_tenant_id=(
                _required_environment_value(
                    "TEAMS_CHANNEL_TENANT_ID"
                )
            ),

            approver_aad_object_id=(
                _required_environment_value(
                    "TEAMS_HITL_APPROVER_AAD_OBJECT_ID"
                )
            ),

            pending_database_path=(
                pending_database_path
            ),

            checkpoint_path=(
                checkpoint_path
            ),

            operation_dispatch_database_path=(
                operation_dispatch_database_path
            ),

            conversation_binding_database_path=(
                conversation_binding_database_path
            ),
        )


@dataclass(
    frozen=True
)
class TeamsHitlBootstrap:
    """
    Componentes del boundary Teams.

    Mantiene separados:

    - aprobación HITL;
    - binding conversacional de transporte.

    Ninguno concede autoridad operacional.
    """

    app: App

    policy: ExactTeamsApprovalPolicy

    store: SqlitePendingApprovalStore

    checkpoint_storage: object

    operation_dispatch_ledger: (
        SqliteOperationDispatchLedger
    )

    continuation_store: (
        SqliteIncidentContinuationStore
    )

    continuation_worker: (
        IncidentContinuationWorker
    )
    dependencies: TeamsApprovalHandlerDependencies

    conversation_store: (
        SqliteTeamsConversationBindingStore
    )

    conversation_dependencies: (
        TeamsConversationHandlerDependencies
    )

    outbound: TeamsOutboundDependencies


def build_teams_hitl_app(
    settings: TeamsHitlSettings,
) -> TeamsHitlBootstrap:
    """
    Construye la aplicación Teams y registra
    los boundaries gobernados actualmente:

        Action.Execute
            -> HITL approval

        MessageActivity
            -> conversation binding

    NO arranca el servidor.

    NO realiza operaciones Azure.

    NO concede capacidades operacionales.
    """

    if not isinstance(
        settings,
        TeamsHitlSettings,
    ):
        raise TypeError(
            "settings debe ser TeamsHitlSettings."
        )

    policy = (
        ExactTeamsApprovalPolicy(
            policy_id=(
                "teams-hitl-sandbox-v1"
            ),

            allowed_principals=(
                TeamsApprovalPrincipal(
                    tenant_id=(
                        settings.teams_channel_tenant_id
                    ),

                    aad_object_id=(
                        settings
                        .approver_aad_object_id
                    ),
                ),
            ),
        )
    )

    store = (
        SqlitePendingApprovalStore(
            settings
            .pending_database_path
        )
    )

    continuation_store = (
        SqliteIncidentContinuationStore(
            settings.pending_database_path.parent
            / "incident-continuations.db"
        )
    )
    checkpoint_storage = (
        build_incident_checkpoint_storage(
            settings.checkpoint_path
        )
    )

    operation_dispatch_ledger = (
        SqliteOperationDispatchLedger(
            settings
            .operation_dispatch_database_path
        )
    )

    def workflow_factory():
        return (
            build_incident_resolution_workflow(
                operation_dispatch_ledger=(
                    operation_dispatch_ledger
                ),
            )
        )

    async def incident_processor(
        *,
        invocation,
        store,
        workflow,
    ):
        return await (
            process_authorized_teams_incident_approval(
                invocation=invocation,
                store=store,
                workflow=workflow,
                checkpoint_storage=(
                    checkpoint_storage
                ),
            )
        )

    dependencies = (
        TeamsApprovalHandlerDependencies(
            policy=(
                policy
            ),

            store=(
                store
            ),

            continuation_store=(
                continuation_store
            ),
            workflow_factory=(
                workflow_factory
            ),

            processor=(
                incident_processor
            ),
        )
    )

    conversation_store = (
        SqliteTeamsConversationBindingStore(
            settings
            .conversation_binding_database_path
        )
    )

    conversation_dependencies = (
        TeamsConversationHandlerDependencies(
            expected_tenant_id=(
                settings.teams_channel_tenant_id
            ),

            store=(
                conversation_store
            ),
        )
    )

    app = App(
        client_id=(
            settings.client_id
        ),

        client_secret=(
            settings.client_secret
        ),

        tenant_id=(
            settings.bot_tenant_id
        ),

        messaging_endpoint=(
            settings.messaging_endpoint
        ),
    )

    outbound = (
        TeamsOutboundDependencies(
            app=app,
            store=(
                conversation_store
            ),
        )
    )

    async def terminal_notifier(
        *,
        invocation,
        processed,
    ):
        return await (
            notify_teams_incident_terminal_result(
                invocation=invocation,
                processed=processed,
                outbound=outbound,
            )
        )

    continuation_worker = (
        IncidentContinuationWorker(
            IncidentContinuationWorkerDependencies(
                continuation_store=(
                    continuation_store
                ),
                approval_store=store,
                workflow_factory=(
                    workflow_factory
                ),
                processor=(
                    incident_processor
                ),
                terminal_notifier=(
                    terminal_notifier
                ),
                worker_id=(
                    "teams-incident-worker-sbx"
                ),
            )
        )
    )
    register_teams_approval_handler(
        app=app,
        dependencies=dependencies,
    )

    register_teams_conversation_handler(
        app=app,
        dependencies=(
            conversation_dependencies
        ),
    )

    return TeamsHitlBootstrap(
        app=app,
        policy=policy,
        store=store,
        checkpoint_storage=(
            checkpoint_storage
        ),
        operation_dispatch_ledger=(
            operation_dispatch_ledger
        ),
        continuation_store=(
            continuation_store
        ),
        continuation_worker=(
            continuation_worker
        ),
        dependencies=dependencies,
        conversation_store=(
            conversation_store
        ),
        conversation_dependencies=(
            conversation_dependencies
        ),
        outbound=(
            outbound
        ),
    )
