"""Approval view bound to the generation returned by this worker's claim.

Trusted composition supplies the stores. This is not authentication, a lease,
or permission to recover an abandoned job from a later read of its generation.
"""
from src.runtime.incident_continuation_store import (
    IncidentContinuationClaimError, IncidentContinuationJob,
    IncidentContinuationStore, require_continuation_attempt,
)
from src.runtime.procedure.approval_channel import ApprovalDecision
from src.runtime.procedure.approval_store import PendingApprovalStore


class ContinuationApprovalStore:
    def __init__(self, *, job: IncidentContinuationJob,
                 continuation_store: IncidentContinuationStore,
                 approval_store: PendingApprovalStore):
        self._job = job
        self._queue = continuation_store
        self._store = approval_store
        self.claim_attempted = False
        self._claim_committed = False
        require_continuation_attempt(job.attempt_count)

    def _require_id(self, approval_id: str) -> None:
        if approval_id != self._job.approval_id:
            raise IncidentContinuationClaimError("Approval is outside this continuation.")

    def register(self, correlation):
        raise IncidentContinuationClaimError("Continuation cannot register approvals.")

    def get_by_approval_id(self, approval_id):
        self._require_id(approval_id)
        return self._store.get_by_approval_id(approval_id)

    def get_by_request_id(self, request_id):
        result = self._store.get_by_request_id(request_id)
        self._require_id(result.approval_id)
        return result

    def get_consumption_record(self, approval_id):
        self._require_id(approval_id)
        return self._store.get_consumption_record(approval_id)

    def claim(self, *, approval_id: str, approved: bool):
        # A failing/uncertain commit must not enable recovery by readback.
        self.claim_attempted = True
        self._require_id(approval_id)
        expected = self._job.invocation.action.decision == ApprovalDecision.APPROVE
        if type(approved) is not bool or approved is not expected:
            raise IncidentContinuationClaimError("Decision differs from queued invocation.")
        result = self._queue.claim_approval(
            approval_id=approval_id, worker_id=self._job.claimed_by,
            expected_attempt_count=self._job.attempt_count, approved=approved,
            approval_store=self._store,
        )
        self._claim_committed = True
        return result

    def complete(self, approval_id):
        self._require_id(approval_id)
        if not self._claim_committed:
            raise IncidentContinuationClaimError("This continuation has not committed a claim.")
        return self._store.complete(approval_id)
