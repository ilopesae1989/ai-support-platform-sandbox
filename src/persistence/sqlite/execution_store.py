"""Candidate SQLite admission/queue; co-location is explicit and mandatory."""
from pathlib import Path
import sqlite3

from src.persistence.execution_continuation_store import ExecutionContinuationStore
from src.runtime.procedure.approval_store import SqlitePendingApprovalStore


class SqliteExecutionStore(ExecutionContinuationStore):
    def __init__(self, database_path, *, execution_affinity, payload_codec, approval_store):
        self._path = Path(database_path).resolve()
        if not isinstance(approval_store, SqlitePendingApprovalStore) or approval_store.database_path != self._path:
            raise TypeError("Candidate execution, queue and approval must share one SQLite file.")
        self._configure(execution_affinity=execution_affinity, payload_codec=payload_codec,
                        approval_store=approval_store, sql_server=False)
        with self._transaction() as cursor:
            cursor.execute("""
CREATE TABLE IF NOT EXISTS incident_executions (
execution_id TEXT PRIMARY KEY, input_sha256 TEXT NOT NULL,
affinity_sha256 TEXT NOT NULL, affinity_json TEXT NOT NULL)
""")
            cursor.execute("""
CREATE TABLE IF NOT EXISTS incident_affine_continuation_jobs (
approval_id TEXT PRIMARY KEY REFERENCES pending_approvals(approval_id),
payload_json TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','claimed','completed','failed')),
attempt_count INTEGER NOT NULL CHECK(attempt_count >= 0), claimed_by TEXT NULL,
last_error TEXT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL,
execution_id TEXT NOT NULL REFERENCES incident_executions(execution_id),
CHECK((status='claimed' AND claimed_by IS NOT NULL) OR (status<>'claimed' AND claimed_by IS NULL)))
""")
            cursor.execute("""
CREATE TABLE IF NOT EXISTS incident_rejection_closures (
execution_id TEXT NOT NULL PRIMARY KEY REFERENCES incident_executions(execution_id),
approval_id TEXT NOT NULL UNIQUE REFERENCES incident_affine_continuation_jobs(approval_id),
worker_id TEXT NOT NULL, attempt INTEGER NOT NULL CHECK(attempt > 0))
""")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_execution_affinity ON incident_executions(affinity_sha256, execution_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_affine_queue ON incident_affine_continuation_jobs(status, created_at, approval_id)")

    def _connect(self):
        connection = sqlite3.connect(self._path.as_uri() + "?mode=rw", uri=True, timeout=30)
        try:
            connection.execute("PRAGMA foreign_keys=ON")
        except BaseException:
            connection.close()
            raise
        return connection
