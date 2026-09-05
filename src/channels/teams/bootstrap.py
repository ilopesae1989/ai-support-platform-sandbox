from __future__ import annotations

import os

from dataclasses import (
    dataclass,
    field,
)

from pathlib import (
    Path,
)

from uuid import (
    UUID,
)

from microsoft_teams.apps import (
    App,
)

from src.runtime.procedure.approval_store import (
    PendingApprovalStore,
    SqlitePendingApprovalStore,
)

from src.runtime.procedure.workflow import (
    build_procedure_approval_workflow,
)

from src.workflows.incident_resolution.azure_vm_instance_view import (
    AzureVmPowerStateReader,
)

from src.workflows.incident_resolution.checkpoint_storage import (
    build_incident_checkpoint_storage,
)

from src.workflows.incident_resolution.operation_dispatch_ledger import (
    OperationDispatchLedger,
    SqliteOperationDispatchLedger,
)

from src.workflows.incident_resolution.wait_recheck_consumption_ledger import (
    SqliteWaitRecheckConsumptionLedger,
    WaitRecheckConsumptionLedger,
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
    IncidentContinuationStore,
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
    TeamsConversationBindingStore,
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
class TeamsHitlAppSettings:
    """
    Configuración del boundary de aplicación Teams.

    Contiene exclusivamente configuración de:

    - autenticación/transporte Teams;
    - tenant del canal;
    - principal HITL autorizado;
    - endpoint HTTP de mensajería.

    No contiene configuración de persistencia.

    La persistencia debe ser inyectada
    explícitamente cuando se use este contrato.
    """

    client_id: str

    client_secret: str = field(
        repr=False
    )

    bot_tenant_id: str

    teams_channel_tenant_id: str

    approver_aad_object_id: str

    messaging_endpoint: str = (
        "/api/messages"
    )

    @classmethod
    def from_environment(
        cls,
    ) -> "TeamsHitlAppSettings":
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
        )


@dataclass(
    frozen=True
)
class TeamsManagedIdentityAppSettings:
    """
    Configuración de aplicación Teams autenticada
    mediante Managed Identity.

    No contiene client_secret.

    managed_identity_client_id acepta únicamente:

    - "system" para system-assigned identity;
    - client ID UUID canónico para user-assigned
      identity.

    No lee entorno ni selecciona credenciales.
    """

    client_id: str

    managed_identity_client_id: str

    bot_tenant_id: str

    teams_channel_tenant_id: str

    approver_aad_object_id: str

    messaging_endpoint: str = (
        "/api/messages"
    )

    def __post_init__(
        self,
    ) -> None:
        value = (
            self.managed_identity_client_id
        )

        if value == "system":
            return

        if (
            not isinstance(
                value,
                str,
            )
            or not value
            or not value.strip()
            or value != value.strip()
        ):
            raise ValueError(
                "managed_identity_client_id debe "
                "ser 'system' o un UUID canónico."
            )

        try:
            parsed = UUID(
                value
            )
        except (
            ValueError,
            AttributeError,
            TypeError,
        ):
            raise ValueError(
                "managed_identity_client_id debe "
                "ser 'system' o un UUID canónico."
            ) from None

        if str(parsed) != value:
            raise ValueError(
                "managed_identity_client_id debe "
                "usar representación UUID canónica."
            )


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
class TeamsHitlPersistence:
    store: PendingApprovalStore

    checkpoint_storage: object

    operation_dispatch_ledger: (
        OperationDispatchLedger
    )

    wait_recheck_consumption_ledger: (
        WaitRecheckConsumptionLedger
    )

    continuation_store: (
        IncidentContinuationStore
    )

    conversation_store: (
        TeamsConversationBindingStore
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

    store: PendingApprovalStore

    checkpoint_storage: object

    operation_dispatch_ledger: (
        OperationDispatchLedger
    )

    wait_recheck_consumption_ledger: (
        WaitRecheckConsumptionLedger
    )

    continuation_store: (
        IncidentContinuationStore
    )

    continuation_worker: (
        IncidentContinuationWorker
    )
    dependencies: TeamsApprovalHandlerDependencies

    conversation_store: (
        TeamsConversationBindingStore
    )

    conversation_dependencies: (
        TeamsConversationHandlerDependencies
    )

    outbound: TeamsOutboundDependencies


def build_local_teams_hitl_persistence(
    settings: TeamsHitlSettings,
) -> TeamsHitlPersistence:
    if not isinstance(
        settings,
        TeamsHitlSettings,
    ):
        raise TypeError(
            "settings debe ser TeamsHitlSettings."
        )

    store = (
        SqlitePendingApprovalStore(
            settings.pending_database_path
        )
    )

    checkpoint_storage = (
        build_incident_checkpoint_storage(
            settings.checkpoint_path
        )
    )

    operation_dispatch_ledger = (
        SqliteOperationDispatchLedger(
            settings.operation_dispatch_database_path
        )
    )

    wait_recheck_consumption_ledger = (
        SqliteWaitRecheckConsumptionLedger(
            settings.pending_database_path.parent
            / "wait-recheck-consumption.db"
        )
    )

    continuation_store = (
        SqliteIncidentContinuationStore(
            settings.pending_database_path.parent
            / "incident-continuations.db"
        )
    )

    conversation_store = (
        SqliteTeamsConversationBindingStore(
            settings.conversation_binding_database_path
        )
    )

    return TeamsHitlPersistence(
        store=store,
        checkpoint_storage=(
            checkpoint_storage
        ),
        operation_dispatch_ledger=(
            operation_dispatch_ledger
        ),
        wait_recheck_consumption_ledger=(
            wait_recheck_consumption_ledger
        ),
        continuation_store=(
            continuation_store
        ),
        conversation_store=(
            conversation_store
        ),
    )

def build_teams_hitl_app(
    settings: (
        TeamsHitlSettings
        | TeamsHitlAppSettings
        | TeamsManagedIdentityAppSettings
    ),
    *,
    persistence: (
        TeamsHitlPersistence | None
    ) = None,
    azure_vm_power_state_reader: (
        AzureVmPowerStateReader | None
    ) = None,
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
        (
            TeamsHitlSettings,
            TeamsHitlAppSettings,
            TeamsManagedIdentityAppSettings,
        ),
    ):
        raise TypeError(
            "settings debe ser TeamsHitlSettings, "
            "TeamsHitlAppSettings o "
            "TeamsManagedIdentityAppSettings."
        )

    if persistence is None:
        if isinstance(
            settings,
            TeamsManagedIdentityAppSettings,
        ):
            raise TeamsHitlConfigurationError(
                "TeamsManagedIdentityAppSettings "
                "requiere persistence inyectada "
                "explícitamente."
            )

        if not isinstance(
            settings,
            TeamsHitlSettings,
        ):
            raise TeamsHitlConfigurationError(
                "TeamsHitlAppSettings requiere "
                "persistence inyectada explícitamente."
            )

        persistence = (
            build_local_teams_hitl_persistence(
                settings
            )
        )

    elif not isinstance(
        persistence,
        TeamsHitlPersistence,
    ):
        raise TypeError(
            "persistence debe ser TeamsHitlPersistence."
        )

    store = persistence.store

    checkpoint_storage = (
        persistence.checkpoint_storage
    )

    operation_dispatch_ledger = (
        persistence.operation_dispatch_ledger
    )

    wait_recheck_consumption_ledger = (
        persistence
        .wait_recheck_consumption_ledger
    )

    continuation_store = (
        persistence.continuation_store
    )

    conversation_store = (
        persistence.conversation_store
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




    def workflow_factory():
        return (
            build_incident_resolution_workflow(
                operation_dispatch_ledger=(
                    operation_dispatch_ledger
                ),
                wait_recheck_consumption_ledger=(
                    wait_recheck_consumption_ledger
                ),
                azure_vm_power_state_reader=(
                    azure_vm_power_state_reader
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

    if isinstance(
        settings,
        TeamsManagedIdentityAppSettings,
    ):
        app = App(
            client_id=(
                settings.client_id
            ),

            managed_identity_client_id=(
                settings
                .managed_identity_client_id
            ),

            tenant_id=(
                settings.bot_tenant_id
            ),

            messaging_endpoint=(
                settings.messaging_endpoint
            ),
        )

    else:
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
        wait_recheck_consumption_ledger=(
            wait_recheck_consumption_ledger
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
