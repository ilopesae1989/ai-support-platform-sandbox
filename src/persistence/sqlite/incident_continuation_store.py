from __future__ import annotations

from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3
import time

from src.runtime.procedure.approval_store import SqlitePendingApprovalStore, ApprovalAlreadyConsumedError
from src.runtime.procedure.approval_correlation import PendingApprovalCorrelation
from src.runtime.procedure.approval_channel import ApprovalDecision

from src.runtime.procedure.authorized_approval import AuthorizedApprovalInvocation
from src.runtime.incident_continuation_codec import ContinuationPayloadCodec
from src.runtime.incident_continuation_recovery import (
    ContinuationRecoveryCandidate, validate_recovery_candidate, validate_recovery_selection,
)
from src.runtime.incident_continuation_store import (
    MAX_PREAPPROVAL_RECOVERY_ATTEMPTS, require_continuation_attempt,
    IncidentContinuationClaimError, IncidentContinuationConflictError,
    IncidentContinuationJob, IncidentContinuationStatus,
)


class SqliteIncidentContinuationStore:
    """
    Handoff durable mínimo para sandbox/MVP.

    Lifecycle monotónico:

        pending
            -> claimed
                -> completed
                -> failed

    Un job claimed NO vuelve automáticamente
    a pending.

    Esto es deliberadamente fail-closed:
    una caída del worker jamás habilita por sí
    sola una segunda ejecución operacional.

    La recuperación de un claim interrumpido
    debe correlacionarse posteriormente contra
    checkpoints y dispatch ledger durable.
    """

    def __init__(
        self,
        database_path: str | Path,
        *,
        payload_codec: ContinuationPayloadCodec,
    ) -> None:
        if not isinstance(payload_codec, ContinuationPayloadCodec):
            raise TypeError("Explicit continuation payload codec required.")
        self._payload_codec = payload_codec

        self._database_path = Path(
            database_path
        )

        self._database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize()

    def _connect(
        self,
    ) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._database_path,
            timeout=30,
        )

        connection.row_factory = (
            sqlite3.Row
        )

        return connection

    def _initialize(
        self,
    ) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                incident_continuation_jobs (
                    approval_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    claimed_by TEXT NULL,
                    last_error TEXT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )

    @staticmethod
    def _validate_exact_string(
        *,
        name: str,
        value: str,
    ) -> str:
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
                f"{name} debe ser un string "
                "no vacío y exacto."
            )

        return value

    def _canonical_payload(self, invocation: AuthorizedApprovalInvocation) -> str:
        return self._payload_codec.encode(invocation)

    def _from_row(self, row: sqlite3.Row) -> IncidentContinuationJob:
        invocation = self._payload_codec.decode(row["payload_json"])

        return IncidentContinuationJob[self._payload_codec.invocation_type](
            approval_id=(
                row["approval_id"]
            ),

            invocation=(
                invocation
            ),

            status=(
                IncidentContinuationStatus(
                    row["status"]
                )
            ),

            attempt_count=(
                int(
                    row["attempt_count"]
                )
            ),

            claimed_by=(
                row["claimed_by"]
            ),

            last_error=(
                row["last_error"]
            ),

            created_at=(
                float(
                    row["created_at"]
                )
            ),

            updated_at=(
                float(
                    row["updated_at"]
                )
            ),
        )

    def enqueue(
        self,
        invocation: (
            AuthorizedApprovalInvocation
        ),
    ) -> IncidentContinuationJob:
        """
        Persiste antes del ACK.

        Repetir exactamente el mismo invoke
        autorizado es idempotente.

        Reutilizar approval_id con una identidad
        o decisión diferente falla cerrado.
        """

        if not isinstance(
            invocation,
            self._payload_codec.invocation_type,
        ):
            raise TypeError(
                "invocation must match the configured authorized model."
            )

        approval_id = (
            invocation
            .action
            .approval_id
        )

        payload_json = (
            self._canonical_payload(
                invocation
            )
        )

        now = time.time()

        connection = (
            self._connect()
        )

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            row = connection.execute(
                """
                SELECT
                    approval_id,
                    payload_json,
                    status,
                    attempt_count,
                    claimed_by,
                    last_error,
                    created_at,
                    updated_at
                FROM incident_continuation_jobs
                WHERE approval_id = ?
                """,
                (
                    approval_id,
                ),
            ).fetchone()

            if row is not None:
                if (
                    row["payload_json"]
                    != payload_json
                ):
                    raise (
                        IncidentContinuationConflictError(
                            "approval_id ya existe con "
                            "un payload autorizado "
                            "diferente."
                        )
                    )

                connection.commit()

                return self._from_row(
                    row
                )

            connection.execute(
                """
                INSERT INTO
                incident_continuation_jobs (
                    approval_id,
                    payload_json,
                    status,
                    attempt_count,
                    claimed_by,
                    last_error,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval_id,
                    payload_json,
                    (
                        IncidentContinuationStatus
                        .PENDING
                        .value
                    ),
                    0,
                    None,
                    None,
                    now,
                    now,
                ),
            )

            row = connection.execute(
                """
                SELECT
                    approval_id,
                    payload_json,
                    status,
                    attempt_count,
                    claimed_by,
                    last_error,
                    created_at,
                    updated_at
                FROM incident_continuation_jobs
                WHERE approval_id = ?
                """,
                (
                    approval_id,
                ),
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    "El job no quedó persistido."
                )

            connection.commit()

            return self._from_row(
                row
            )

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def get(
        self,
        approval_id: str,
    ) -> IncidentContinuationJob:
        approval_id = (
            self._validate_exact_string(
                name="approval_id",
                value=approval_id,
            )
        )

        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                """
                SELECT
                    approval_id,
                    payload_json,
                    status,
                    attempt_count,
                    claimed_by,
                    last_error,
                    created_at,
                    updated_at
                FROM incident_continuation_jobs
                WHERE approval_id = ?
                """,
                (
                    approval_id,
                ),
            ).fetchone()

        if row is None:
            raise KeyError(
                "No existe continuation job para "
                f"approval_id={approval_id!r}."
            )

        return self._from_row(
            row
        )

    def claim_next(
        self,
        *,
        worker_id: str,
    ) -> IncidentContinuationJob | None:
        """
        Reclama atómicamente un job PENDING.

        Un job CLAIMED nunca se reclama de nuevo
        automáticamente, ni siquiera tras restart.
        """

        worker_id = (
            self._validate_exact_string(
                name="worker_id",
                value=worker_id,
            )
        )

        connection = (
            self._connect()
        )

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            row = connection.execute(
                """
                SELECT
                    approval_id
                FROM incident_continuation_jobs
                WHERE status = ?
                ORDER BY
                    created_at ASC,
                    approval_id ASC
                LIMIT 1
                """,
                (
                    IncidentContinuationStatus
                    .PENDING
                    .value,
                ),
            ).fetchone()

            if row is None:
                connection.commit()
                return None

            approval_id = (
                row["approval_id"]
            )

            now = time.time()

            cursor = connection.execute(
                """
                UPDATE incident_continuation_jobs
                SET
                    status = ?,
                    attempt_count =
                        attempt_count + 1,
                    claimed_by = ?,
                    updated_at = ?
                WHERE
                    approval_id = ?
                    AND status = ?
                """,
                (
                    IncidentContinuationStatus
                    .CLAIMED
                    .value,
                    worker_id,
                    now,
                    approval_id,
                    IncidentContinuationStatus
                    .PENDING
                    .value,
                ),
            )

            if cursor.rowcount != 1:
                raise (
                    IncidentContinuationClaimError(
                        "El job fue reclamado "
                        "concurrentemente."
                    )
                )

            claimed = connection.execute(
                """
                SELECT
                    approval_id,
                    payload_json,
                    status,
                    attempt_count,
                    claimed_by,
                    last_error,
                    created_at,
                    updated_at
                FROM incident_continuation_jobs
                WHERE approval_id = ?
                """,
                (
                    approval_id,
                ),
            ).fetchone()

            if claimed is None:
                raise RuntimeError(
                    "El job reclamado desapareció."
                )

            connection.commit()

            return self._from_row(
                claimed
            )

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def complete(
        self,
        *,
        approval_id: str,
        worker_id: str,
        expected_attempt_count: int,
    ) -> IncidentContinuationJob:
        expected_attempt_count = require_continuation_attempt(expected_attempt_count)

        approval_id = (
            self._validate_exact_string(
                name="approval_id",
                value=approval_id,
            )
        )

        worker_id = (
            self._validate_exact_string(
                name="worker_id",
                value=worker_id,
            )
        )

        now = time.time()

        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE incident_continuation_jobs
                SET
                    status = ?,
                    claimed_by = NULL,
                    last_error = NULL,
                    updated_at = ?
                WHERE
                    approval_id = ?
                    AND status = ?
                    AND claimed_by = ?
                    AND attempt_count = ?
                """,
                (
                    IncidentContinuationStatus
                    .COMPLETED
                    .value,
                    now,
                    approval_id,
                    IncidentContinuationStatus
                    .CLAIMED
                    .value,
                    worker_id,
                    expected_attempt_count,
                ),
            )

        if cursor.rowcount != 1:
            raise (
                IncidentContinuationClaimError(
                    "El job no está claimed por "
                    "el worker indicado."
                )
            )

        return self.get(
            approval_id
        )

    def fail(
        self,
        *,
        approval_id: str,
        worker_id: str,
        expected_attempt_count: int,
        error: str,
    ) -> IncidentContinuationJob:
        expected_attempt_count = require_continuation_attempt(expected_attempt_count)

        approval_id = (
            self._validate_exact_string(
                name="approval_id",
                value=approval_id,
            )
        )

        worker_id = (
            self._validate_exact_string(
                name="worker_id",
                value=worker_id,
            )
        )

        error = (
            self._validate_exact_string(
                name="error",
                value=error,
            )
        )

        now = time.time()

        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE incident_continuation_jobs
                SET
                    status = ?,
                    claimed_by = NULL,
                    last_error = ?,
                    updated_at = ?
                WHERE
                    approval_id = ?
                    AND status = ?
                    AND claimed_by = ?
                    AND attempt_count = ?
                """,
                (
                    IncidentContinuationStatus
                    .FAILED
                    .value,
                    error,
                    now,
                    approval_id,
                    IncidentContinuationStatus
                    .CLAIMED
                    .value,
                    worker_id,
                    expected_attempt_count,
                ),
            )

        if cursor.rowcount != 1:
            raise (
                IncidentContinuationClaimError(
                    "El job no está claimed por "
                    "el worker indicado."
                )
            )

        return self.get(
            approval_id
        )
    def list_stale_claims(self, *, stale_before: float, limit: int,
                         after_id: str | None = None) -> tuple[ContinuationRecoveryCandidate, ...]:
        cutoff = validate_recovery_selection(stale_before=stale_before,
                                             limit=limit, after_id=after_id)
        # A scan must not recreate an absent database or decode an invocation.
        with closing(sqlite3.connect(
            self._database_path.resolve().as_uri() + "?mode=rw", uri=True, timeout=30,
        )) as connection:
            rows = connection.execute("""
SELECT approval_id, claimed_by, attempt_count, updated_at
FROM incident_continuation_jobs
WHERE status = 'claimed' AND updated_at < ?
  AND (? IS NULL OR approval_id > ?)
ORDER BY approval_id ASC LIMIT ?
""", (cutoff, after_id, after_id, limit)).fetchall()
            return tuple(ContinuationRecoveryCandidate(*row) for row in rows)

    def recover_stale_before_approval(self, *, candidate: ContinuationRecoveryCandidate,
                                      stale_before: float, approval_store: object) -> None:
        cutoff = validate_recovery_candidate(candidate, stale_before)
        with self._approval_transaction(approval_store) as (connection, schema):
            row = connection.execute(f"""
SELECT consumption_status, approved_decision FROM {schema}.pending_approvals
WHERE approval_id = ?
""", (candidate.approval_id,)).fetchone()
            if row is None or row[0] != "pending" or row[1] is not None:
                raise IncidentContinuationClaimError("Approval absent, consumed or inconsistent.")
            cursor = connection.execute("""
UPDATE incident_continuation_jobs
SET status = 'pending', claimed_by = NULL, last_error = NULL, updated_at = ?
WHERE approval_id = ? AND status = 'claimed' AND claimed_by = ?
  AND attempt_count = ? AND attempt_count < ?
  AND updated_at = ? AND updated_at < ?
""", (time.time(), candidate.approval_id, candidate.worker_id, candidate.attempt_count,
      MAX_PREAPPROVAL_RECOVERY_ATTEMPTS, candidate.updated_at, cutoff))
            if cursor.rowcount != 1:
                raise IncidentContinuationClaimError("Recovery candidate changed or exhausted its attempts.")
        # No post-commit read: it could observe a newly claimed generation.

    @contextmanager
    def _approval_transaction(self, approval_store):
        if not isinstance(approval_store, SqlitePendingApprovalStore):
            raise TypeError("Coordinated SQLite approval store required.")
        path = approval_store.database_path
        # Open existing files only. Fixed aliases; the configured path is bound.
        with closing(sqlite3.connect(
            self._database_path.resolve().as_uri() + "?mode=rw", uri=True, timeout=30,
        )) as connection:
            connection.row_factory = sqlite3.Row
            schema = "main"
            if path != self._database_path.resolve():
                connection.execute("ATTACH DATABASE ? AS approval_side",
                                   (path.as_uri() + "?mode=rw",))
                schema = "approval_side"
            try:
                connection.execute("BEGIN IMMEDIATE")
                yield connection, schema
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def claim_approval(self, *, approval_id: str, worker_id: str,
                       expected_attempt_count: int, approved: bool,
                       approval_store) -> PendingApprovalCorrelation:
        expected_attempt_count = require_continuation_attempt(expected_attempt_count)
        self._validate_exact_string(name="approval_id", value=approval_id)
        self._validate_exact_string(name="worker_id", value=worker_id)
        if type(approved) is not bool:
            raise TypeError("approved must be bool.")
        with self._approval_transaction(approval_store) as (connection, schema):
            job = connection.execute(
                "SELECT payload_json FROM main.incident_continuation_jobs "
                "WHERE approval_id=? AND status='claimed' AND claimed_by=? AND attempt_count=?",
                (approval_id, worker_id, expected_attempt_count),
            ).fetchone()
            if job is None:
                raise IncidentContinuationClaimError("Continuation ownership lost before HITL claim.")
            invocation = self._payload_codec.decode(job["payload_json"])
            if (invocation.action.approval_id != approval_id or
                    (invocation.action.decision == ApprovalDecision.APPROVE) is not approved):
                raise IncidentContinuationClaimError("Decision differs from durable invocation.")
            row = connection.execute(
                f"SELECT * FROM {schema}.pending_approvals WHERE approval_id=?",
                (approval_id,),
            ).fetchone()
            if row is None or row["consumption_status"] != "pending" or row["approved_decision"] is not None:
                raise ApprovalAlreadyConsumedError("Approval absent, consumed or inconsistent.")
            result = PendingApprovalCorrelation(
                approval_id=row["approval_id"], workflow_id=row["workflow_id"],
                request_id=row["request_id"], checkpoint_id=row["checkpoint_id"],
            )
            changed = connection.execute(
                f"UPDATE {schema}.pending_approvals SET consumption_status='claimed', approved_decision=? "
                "WHERE approval_id=? AND consumption_status='pending' AND approved_decision IS NULL",
                (int(approved), approval_id),
            )
            if changed.rowcount != 1:
                raise ApprovalAlreadyConsumedError("Approval was consumed concurrently.")
        return result

    def recover_claimed_before_approval(self, *, approval_id: str, worker_id: str,
                                       expected_attempt_count: int, approval_store):
        """Serialize recovery with the HITL claim on the configured database pair.

        The transaction writes only the queue; claim_approval writes only the
        approval file. No multi-file atomic write or orphan sweep is introduced.
        """
        expected_attempt_count = require_continuation_attempt(expected_attempt_count)
        self._validate_exact_string(name="approval_id", value=approval_id)
        self._validate_exact_string(name="worker_id", value=worker_id)
        with self._approval_transaction(approval_store) as (connection, schema):
            row = connection.execute(
                f"SELECT consumption_status, approved_decision FROM {schema}.pending_approvals WHERE approval_id=?",
                (approval_id,),
            ).fetchone()
            if row is None or row[0] != "pending" or row[1] is not None:
                raise IncidentContinuationClaimError("Recovery requires pending approval without decision.")
            changed = connection.execute(
                "UPDATE main.incident_continuation_jobs SET status='pending', claimed_by=NULL, "
                "last_error=NULL, updated_at=? WHERE approval_id=? AND status='claimed' "
                "AND claimed_by=? AND attempt_count=? AND attempt_count < ?",
                (time.time(), approval_id, worker_id, expected_attempt_count,
                 MAX_PREAPPROVAL_RECOVERY_ATTEMPTS),
            )
            if changed.rowcount != 1:
                raise IncidentContinuationClaimError("Recovery ownership lost or budget exhausted.")
        return self.get(approval_id)
