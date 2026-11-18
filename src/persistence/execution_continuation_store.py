"""Candidate execution ledger and isolated queue, with one transaction per action.

SQLite and Azure SQL share invariants, not a claim of equivalent concurrency.
Concrete adapters own connections/schema. Legacy queue tables are never accessed.
"""
from contextlib import contextmanager
import json
import re
import time
from typing import Generic

from src.runtime.execution_affinity import ExecutionAffinity, require_digest, require_identifier
from src.runtime.incident_execution import IncidentExecution, IncidentExecutionConflictError
from src.runtime.incident_continuation_codec import ContinuationPayloadCodec, InvocationT
from src.runtime.incident_continuation_store import (
    IncidentContinuationJob, IncidentContinuationStatus, IncidentContinuationClaimError,
    IncidentContinuationConflictError, MAX_PREAPPROVAL_RECOVERY_ATTEMPTS, require_continuation_attempt,
)
from src.runtime.incident_continuation_recovery import (
    ContinuationRecoveryCandidate, validate_recovery_candidate, validate_recovery_selection,
)
from src.runtime.procedure.approval_correlation import PendingApprovalCorrelation
from src.runtime.procedure.approval_store import ApprovalAlreadyConsumedError
from src.runtime.procedure.approval_channel import ApprovalDecision


class AffinedIncidentContinuationJob(IncidentContinuationJob[InvocationT], Generic[InvocationT]):
    execution_id: str


class ExecutionContinuationStore:
    """Internal shared implementation. Only the concrete adapters construct it."""

    def _configure(self, *, execution_affinity, payload_codec, approval_store, sql_server):
        if type(execution_affinity) is not ExecutionAffinity:
            raise TypeError("Explicit execution affinity required.")
        if not isinstance(payload_codec, ContinuationPayloadCodec):
            raise TypeError("Explicit continuation codec required.")
        self._execution_affinity = execution_affinity
        self._codec = payload_codec
        self._approvals = approval_store
        self._sql_server = sql_server
        prefix = "dbo." if sql_server else ""
        self._executions = prefix + "incident_executions"
        self._closures = prefix + "incident_rejection_closures"
        self._jobs = prefix + "incident_affine_continuation_jobs"
        self._pending = prefix + "pending_approvals"

    @property
    def execution_affinity(self):
        return self._execution_affinity

    def uses_approval_store(self, store):
        return store is self._approvals

    @contextmanager
    def _transaction(self):
        connection = self._connect()
        cursor = None
        try:
            if self._sql_server and getattr(connection, "autocommit", None) is not False:
                raise RuntimeError("Execution persistence requires autocommit=False.")
            cursor = connection.cursor()
            if not self._sql_server:
                cursor.execute("BEGIN IMMEDIATE")
            yield cursor
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            try:
                if cursor is not None:
                    cursor.close()
            finally:
                connection.close()

    def _execute(self, cursor, sql, params=None):
        if not self._sql_server:
            sql = re.sub(r"%\(([a-z_][a-z_0-9]*)\)s", r":\1", sql)
        cursor.execute(sql, params or {})
        return cursor

    def _lock(self, *, queue=False):
        if not self._sql_server:
            return ""
        return ("WITH (UPDLOCK, READPAST, READCOMMITTEDLOCK)" if queue
                else "WITH (UPDLOCK, HOLDLOCK)")

    def _execution(self, cursor, execution_id):
        row = self._execute(cursor, f"""
SELECT execution_id, input_sha256, affinity_sha256, affinity_json
FROM {self._executions} {self._lock()} WHERE execution_id = %(execution_id)s
""", {"execution_id": execution_id}).fetchone()
        if row is None:
            raise KeyError("Execution was not admitted.")
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise IncidentExecutionConflictError("Duplicate affinity key.")
                result[key] = value
            return result
        affinity = ExecutionAffinity.from_document(json.loads(row[3], object_pairs_hook=unique))
        if row[2] != affinity.fingerprint or affinity != self.execution_affinity:
            raise IncidentExecutionConflictError("Execution belongs to a different affinity.")
        if row[0] != execution_id:
            raise IncidentExecutionConflictError("Execution identity changed.")
        return IncidentExecution(execution_id=row[0], input_sha256=row[1], affinity=affinity)

    def admit(self, *, execution_id, input_sha256):
        require_identifier(execution_id, "execution_id")
        require_digest(input_sha256, "input_sha256")
        with self._transaction() as cursor:
            try:
                existing = self._execution(cursor, execution_id)
            except KeyError:
                self._execute(cursor, f"""
INSERT INTO {self._executions} (execution_id, input_sha256, affinity_sha256, affinity_json)
VALUES (%(execution_id)s, %(input_sha256)s, %(affinity_sha256)s, %(affinity_json)s)
""", dict(execution_id=execution_id, input_sha256=input_sha256,
          affinity_sha256=self.execution_affinity.fingerprint,
          affinity_json=json.dumps(self.execution_affinity.to_document(), sort_keys=True, separators=(",", ":"))))
                existing = IncidentExecution(execution_id=execution_id, input_sha256=input_sha256,
                                             affinity=self.execution_affinity)
            if existing.input_sha256 != input_sha256:
                raise IncidentExecutionConflictError("Execution was admitted with a different input.")
        return existing

    def get_execution(self, execution_id):
        require_identifier(execution_id, "execution_id")
        with self._transaction() as cursor:
            return self._execution(cursor, execution_id)

    @staticmethod
    def _identifier(value):
        if type(value) is not str or not value or value != value.strip() or len(value) > 256:
            raise ValueError("Exact bounded identifier required.")
        return value

    def _approval(self, cursor, approval_id):
        row = self._execute(cursor, f"""
SELECT approval_id, workflow_id, request_id, checkpoint_id, consumption_status, approved_decision
FROM {self._pending} {self._lock()} WHERE approval_id = %(approval_id)s
""", {"approval_id": approval_id}).fetchone()
        if row is None:
            raise IncidentContinuationClaimError("Approval correlation is absent.")
        correlation = PendingApprovalCorrelation(approval_id=row[0], workflow_id=row[1],
                                                 request_id=row[2], checkpoint_id=row[3])
        if correlation.approval_id != approval_id:
            raise IncidentContinuationClaimError("Approval identity changed.")
        return correlation, row[4], row[5]

    def _job(self, cursor, approval_id):
        row = self._execute(cursor, f"""
SELECT approval_id, payload_json, status, attempt_count, claimed_by, last_error,
       created_at, updated_at, execution_id
FROM {self._jobs} {self._lock()} WHERE approval_id = %(approval_id)s
""", {"approval_id": approval_id}).fetchone()
        if row is None:
            raise KeyError("Continuation is absent from the candidate queue.")
        self._execution(cursor, row[8])
        if row[0] != approval_id:
            raise IncidentContinuationClaimError("Continuation identity changed.")
        invocation = self._codec.decode(row[1])
        return AffinedIncidentContinuationJob[self._codec.invocation_type](
            approval_id=row[0], invocation=invocation, status=row[2], attempt_count=row[3],
            claimed_by=row[4], last_error=row[5], created_at=row[6], updated_at=row[7],
            execution_id=row[8])

    def enqueue(self, invocation):
        if not isinstance(invocation, self._codec.invocation_type):
            raise TypeError("Invocation does not match the configured codec.")
        approval_id = self._identifier(invocation.action.approval_id)
        payload = self._codec.encode(invocation)
        with self._transaction() as cursor:
            # Same lock order as HITL: queue/generation before approval. In SQL,
            # the absent-key range is held as well, making duplicate enqueue serial.
            try:
                job = self._job(cursor, approval_id)
            except KeyError:
                job = None
            correlation, status, decision = self._approval(cursor, approval_id)
            self._execution(cursor, correlation.workflow_id)
            if job is None:
                if status != "pending" or decision is not None:
                    raise ApprovalAlreadyConsumedError("Only pending approvals can enter the queue.")
                now = time.time()
                self._execute(cursor, f"""
INSERT INTO {self._jobs} (approval_id, payload_json, status, attempt_count, claimed_by,
                        last_error, created_at, updated_at, execution_id)
VALUES (%(approval_id)s, %(payload)s, 'pending', 0, NULL, NULL, %(now)s, %(now)s, %(execution_id)s)
""", dict(approval_id=approval_id, payload=payload, now=now, execution_id=correlation.workflow_id))
                job = self._job(cursor, approval_id)
            if (job.execution_id != correlation.workflow_id or self._codec.encode(job.invocation) != payload):
                raise IncidentContinuationConflictError("Continuation identity or decision conflicts.")
        return job

    def get(self, approval_id):
        self._identifier(approval_id)
        with self._transaction() as cursor:
            return self._job(cursor, approval_id)

    def _scope(self):
        return f"""EXISTS (SELECT 1 FROM {self._executions} e
WHERE e.execution_id = q.execution_id AND e.affinity_sha256 = %(affinity)s)"""

    def claim_next(self, *, worker_id):
        self._identifier(worker_id)
        with self._transaction() as cursor:
            top, limit = ("TOP (1) ", "") if self._sql_server else ("", "LIMIT 1")
            row = self._execute(cursor, f"""
SELECT {top}q.approval_id FROM {self._jobs} q {self._lock(queue=True)}
WHERE q.status = 'pending' AND {self._scope()}
ORDER BY q.created_at ASC, q.approval_id ASC {limit}
""", {"affinity": self.execution_affinity.fingerprint}).fetchone()
            if row is None:
                return None
            job = self._job(cursor, row[0])
            if job.status != IncidentContinuationStatus.PENDING:
                raise IncidentContinuationClaimError("Selected continuation changed.")
            self._execute(cursor, f"""
UPDATE {self._jobs} SET status = 'claimed', attempt_count = attempt_count + 1,
claimed_by = %(worker)s, updated_at = %(now)s
WHERE approval_id = %(approval)s AND status = 'pending' AND attempt_count = %(attempt)s
AND execution_id = %(execution)s AND updated_at = %(updated)s
""", dict(worker=worker_id, now=time.time(), approval=job.approval_id, attempt=job.attempt_count,
          execution=job.execution_id, updated=job.updated_at))
            claimed = self._job(cursor, job.approval_id)
            if (claimed.status != IncidentContinuationStatus.CLAIMED or claimed.claimed_by != worker_id
                    or claimed.attempt_count != job.attempt_count + 1):
                raise IncidentContinuationClaimError("Claim did not retain its generation.")
        return claimed

    def _owned(self, cursor, approval_id, worker_id, expected_attempt_count):
        self._identifier(approval_id)
        self._identifier(worker_id)
        require_continuation_attempt(expected_attempt_count)
        try:
            job = self._job(cursor, approval_id)
        except (KeyError, IncidentExecutionConflictError) as exc:
            raise IncidentContinuationClaimError("Continuation is outside this affinity.") from exc
        if (job.status != IncidentContinuationStatus.CLAIMED or job.claimed_by != worker_id
                or job.attempt_count != expected_attempt_count):
            raise IncidentContinuationClaimError("Continuation ownership was lost.")
        return job

    def _transition(self, cursor, job, status, error=None):
        self._execute(cursor, f"""
UPDATE {self._jobs} SET status = %(status)s, claimed_by = NULL, last_error = %(error)s,
updated_at = %(now)s WHERE approval_id = %(approval)s AND status = 'claimed'
AND claimed_by = %(worker)s AND attempt_count = %(attempt)s
AND execution_id = %(execution)s AND updated_at = %(updated)s
""", dict(status=status, error=error, now=time.time(), approval=job.approval_id,
          worker=job.claimed_by, attempt=job.attempt_count, execution=job.execution_id, updated=job.updated_at))
        result = self._job(cursor, job.approval_id)
        if result.status.value != status or result.attempt_count != job.attempt_count:
            raise IncidentContinuationClaimError("Continuation transition was not retained.")
        return result

    def rejection_closure(self, execution_id):
        """Return the terminal approval ID for this affinity, if committed."""
        with self._transaction() as cursor:
            self._execution(cursor, execution_id)
            row = self._execute(cursor, f"SELECT approval_id FROM {self._closures} "
                                "WHERE execution_id = %(id)s", {"id": execution_id}).fetchone()
            return None if row is None else row[0]

    def complete_rejection(self, *, approval_id, worker_id, expected_attempt_count, outcome):
        from src.runtime.procedure.workflow import ApprovalOutcome

        self._identifier(worker_id)
        require_continuation_attempt(expected_attempt_count)
        if type(outcome) is not ApprovalOutcome or outcome.approved is not False or outcome.status != "blocked":
            raise IncidentExecutionConflictError("Expected a terminal human rejection.")
        with self._transaction() as cursor:
            job = self._job(cursor, approval_id)
            correlation, status, approved = self._approval(cursor, approval_id)
            if (outcome.workflow_id != job.execution_id or correlation.workflow_id != job.execution_id
                    or status != "completed" or approved != 0):
                raise IncidentExecutionConflictError("Rejected execution lacks completed decision evidence.")
            params = dict(id=job.execution_id, approval=approval_id, worker=worker_id, attempt=expected_attempt_count)
            row = self._execute(cursor, f"SELECT approval_id, worker_id, attempt FROM {self._closures} "
                                f"{self._lock()} WHERE execution_id = %(id)s", {"id": job.execution_id}).fetchone()
            if row is not None:
                if (tuple(row) != (approval_id, worker_id, expected_attempt_count)
                        or job.status.value != "completed" or job.attempt_count != expected_attempt_count):
                    raise IncidentExecutionConflictError("Closure conflicts with the recorded attempt.")
                return job
            owned = self._owned(cursor, approval_id, worker_id, expected_attempt_count)
            completed = self._transition(cursor, owned, "completed")
            self._execute(cursor, f"INSERT INTO {self._closures} (execution_id, approval_id, worker_id, attempt) "
                          "VALUES (%(id)s, %(approval)s, %(worker)s, %(attempt)s)", params)
            return completed

    def complete(self, *, approval_id, worker_id, expected_attempt_count):
        with self._transaction() as cursor:
            return self._transition(cursor, self._owned(cursor, approval_id, worker_id, expected_attempt_count), "completed")

    def fail(self, *, approval_id, worker_id, expected_attempt_count, error):
        if type(error) is not str or not error:
            raise ValueError("Error description required.")
        with self._transaction() as cursor:
            return self._transition(cursor, self._owned(cursor, approval_id, worker_id, expected_attempt_count), "failed", error)

    def _require_approval_store(self, store):
        if store is not self._approvals:
            raise TypeError("The co-located approval store from composition is required.")

    def _pending_for_job(self, cursor, job):
        correlation, status, decision = self._approval(cursor, job.approval_id)
        if correlation.workflow_id != job.execution_id or status != "pending" or decision is not None:
            raise ApprovalAlreadyConsumedError("Approval is not pending for this execution.")
        return correlation

    def claim_approval(self, *, approval_id, worker_id, expected_attempt_count, approved, approval_store):
        self._require_approval_store(approval_store)
        if type(approved) is not bool:
            raise TypeError("approved must be bool.")
        with self._transaction() as cursor:
            job = self._owned(cursor, approval_id, worker_id, expected_attempt_count)
            if (job.invocation.action.decision == ApprovalDecision.APPROVE) is not approved:
                raise IncidentContinuationClaimError("Decision differs from the durable invocation.")
            correlation = self._pending_for_job(cursor, job)
            self._execute(cursor, f"""
UPDATE {self._pending} SET consumption_status = 'claimed', approved_decision = %(decision)s
WHERE approval_id = %(approval)s AND workflow_id = %(execution)s
AND request_id = %(request)s AND checkpoint_id = %(checkpoint)s
AND consumption_status = 'pending' AND approved_decision IS NULL
""", dict(decision=bool(approved), approval=approval_id, execution=job.execution_id,
          request=correlation.request_id, checkpoint=correlation.checkpoint_id))
            check, status, decision = self._approval(cursor, approval_id)
            if check != correlation or status != "claimed" or decision != approved:
                raise IncidentContinuationClaimError("HITL claim did not retain its correlation.")
        return correlation

    def _recover(self, cursor, job):
        if job.attempt_count >= MAX_PREAPPROVAL_RECOVERY_ATTEMPTS:
            raise IncidentContinuationClaimError("Recovery budget exhausted.")
        try:
            self._pending_for_job(cursor, job)
        except ApprovalAlreadyConsumedError as exc:
            raise IncidentContinuationClaimError("Approval is not recoverable.") from exc
        return self._transition(cursor, job, "pending")

    def recover_claimed_before_approval(self, *, approval_id, worker_id, expected_attempt_count, approval_store):
        self._require_approval_store(approval_store)
        with self._transaction() as cursor:
            return self._recover(cursor, self._owned(cursor, approval_id, worker_id, expected_attempt_count))

    def list_stale_claims(self, *, stale_before, limit, after_id=None):
        cutoff = validate_recovery_selection(stale_before=stale_before, limit=limit, after_id=after_id)
        with self._transaction() as cursor:
            top, tail = ("TOP (%(limit)s) ", "") if self._sql_server else ("", "LIMIT %(limit)s")
            rows = self._execute(cursor, f"""
SELECT {top}q.approval_id, q.claimed_by, q.attempt_count, q.updated_at
FROM {self._jobs} q WHERE q.status = 'claimed' AND q.updated_at < %(cutoff)s
AND (%(after)s IS NULL OR q.approval_id > %(after)s) AND {self._scope()}
ORDER BY q.approval_id ASC {tail}
""", dict(limit=limit, cutoff=cutoff, after=after_id, affinity=self.execution_affinity.fingerprint)).fetchall()
            return tuple(ContinuationRecoveryCandidate(*row) for row in rows)

    def recover_stale_before_approval(self, *, candidate, stale_before, approval_store):
        cutoff = validate_recovery_candidate(candidate, stale_before)
        self._require_approval_store(approval_store)
        with self._transaction() as cursor:
            job = self._owned(cursor, candidate.approval_id, candidate.worker_id, candidate.attempt_count)
            if job.updated_at != candidate.updated_at or job.updated_at >= cutoff:
                raise IncidentContinuationClaimError("Recovery candidate changed.")
            self._recover(cursor, job)
