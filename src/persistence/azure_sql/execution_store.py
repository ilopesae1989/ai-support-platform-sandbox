"""Candidate Azure SQL adapter. Schema installation is a separate reviewed step."""
from src.persistence.execution_continuation_store import ExecutionContinuationStore
from src.persistence.azure_sql.pending_approval_store import AzureSqlPendingApprovalStore


class AzureSqlExecutionStore(ExecutionContinuationStore):
    def __init__(self, *, connection_factory, execution_affinity, payload_codec, approval_store):
        if (not callable(connection_factory) or not isinstance(approval_store, AzureSqlPendingApprovalStore)
                or not approval_store.uses_connection_factory(connection_factory)):
            raise TypeError("Candidate execution and approval require the same SQL connection factory.")
        self._connection_factory = connection_factory
        self._configure(execution_affinity=execution_affinity, payload_codec=payload_codec,
                        approval_store=approval_store, sql_server=True)

    def _connect(self):
        return self._connection_factory()
