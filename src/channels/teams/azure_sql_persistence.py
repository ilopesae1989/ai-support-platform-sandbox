from __future__ import annotations

from dataclasses import (
    dataclass,
)

from src.channels.teams.bootstrap import (
    TeamsHitlPersistence,
)

from src.persistence.azure_sql.checkpoint_storage import (
    AzureSqlCheckpointStorage,
)

from src.persistence.azure_sql.connection_provider import (
    AzureSqlManagedIdentitySettings,
    build_mssql_python_connection_factory,
)

from src.persistence.azure_sql.conversation_binding_store import (
    AzureSqlTeamsConversationBindingStore,
)

from src.persistence.azure_sql.incident_continuation_store import (
    AzureSqlIncidentContinuationStore,
)

from src.persistence.azure_sql.operation_dispatch_ledger import (
    AzureSqlOperationDispatchLedger,
)

from src.persistence.azure_sql.pending_approval_store import (
    AzureSqlPendingApprovalStore,
)

from src.persistence.azure_sql.session_store import (
    AzureSqlSessionStore,
)

from src.workflows.incident_resolution.checkpoint_storage import (
    incident_checkpoint_allowed_types,
)


@dataclass(
    frozen=True
)
class AzureSqlTeamsHitlPersistence(
    TeamsHitlPersistence
):
    """
    Bundle productivo de persistencia Azure SQL.

    Extiende el contrato histórico Teams/HITL con
    persistencia durable de AgentSession.

    No modifica el contrato local/sandbox y no
    concede autoridad de runtime conversacional.
    """

    session_store: AzureSqlSessionStore


def build_azure_sql_teams_hitl_persistence(
    settings: AzureSqlManagedIdentitySettings,
) -> AzureSqlTeamsHitlPersistence:
    """
    Compone la persistencia durable productiva
    sobre Azure SQL.

    El composition root:

    - recibe configuración estructurada;
    - construye una única connection factory;
    - comparte esa factory entre seis adapters;
    - conserva la allowlist explícita del workflow;
    - no abre conexiones;
    - no ejecuta DDL;
    - no descubre configuración;
    - no ejecuta AgentSession ni runtime multi-turn.
    """
    if not isinstance(
        settings,
        AzureSqlManagedIdentitySettings,
    ):
        raise TypeError(
            "settings debe ser "
            "AzureSqlManagedIdentitySettings."
        )

    connection_factory = (
        build_mssql_python_connection_factory(
            settings
        )
    )

    allowed_checkpoint_types = sorted(
        incident_checkpoint_allowed_types()
    )

    store = AzureSqlPendingApprovalStore(
        connection_factory=connection_factory,
    )

    checkpoint_storage = (
        AzureSqlCheckpointStorage(
            connection_factory=(
                connection_factory
            ),
            allowed_checkpoint_types=(
                allowed_checkpoint_types
            ),
        )
    )

    operation_dispatch_ledger = (
        AzureSqlOperationDispatchLedger(
            connection_factory=(
                connection_factory
            ),
        )
    )

    continuation_store = (
        AzureSqlIncidentContinuationStore(
            connection_factory=(
                connection_factory
            ),
        )
    )

    conversation_store = (
        AzureSqlTeamsConversationBindingStore(
            connection_factory=(
                connection_factory
            ),
        )
    )

    session_store = (
        AzureSqlSessionStore(
            connection_factory=(
                connection_factory
            ),
        )
    )

    return AzureSqlTeamsHitlPersistence(
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
        conversation_store=(
            conversation_store
        ),
        session_store=(
            session_store
        ),
    )
