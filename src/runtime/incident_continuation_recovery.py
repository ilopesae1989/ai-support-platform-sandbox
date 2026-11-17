"""Bounded, explicit recovery before HITL consumption; no scheduler or effects."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Protocol

from src.runtime.incident_continuation_store import (
    IncidentContinuationClaimError, require_continuation_attempt,
)


MAX_RECOVERY_BATCH_SIZE = 100


def _exact_identifier(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("Recovery identifiers must be nonempty exact strings.")
    return value


def _timestamp(value: object) -> float:
    if type(value) not in (int, float) or value < 0 or not isfinite(value):
        raise ValueError("Recovery timestamps must be finite nonnegative numbers.")
    return float(value)


def validate_recovery_selection(*, stale_before: float, limit: int,
                                after_id: str | None) -> float:
    """Validate before opening persistence; never accept an unbounded batch."""
    cutoff = _timestamp(stale_before)
    if type(limit) is not int or not 1 <= limit <= MAX_RECOVERY_BATCH_SIZE:
        raise ValueError("Recovery limit must be an integer between 1 and 100.")
    if after_id is not None:
        _exact_identifier(after_id)
    return cutoff


@dataclass(frozen=True)
class ContinuationRecoveryCandidate:
    approval_id: str
    worker_id: str
    attempt_count: int
    updated_at: float

    def __post_init__(self) -> None:
        _exact_identifier(self.approval_id)
        _exact_identifier(self.worker_id)
        require_continuation_attempt(self.attempt_count)
        object.__setattr__(self, "updated_at", _timestamp(self.updated_at))


def validate_recovery_candidate(candidate: ContinuationRecoveryCandidate,
                                stale_before: float) -> float:
    cutoff = _timestamp(stale_before)
    if not isinstance(candidate, ContinuationRecoveryCandidate):
        raise TypeError("An original recovery candidate is required.")
    if candidate.updated_at >= cutoff:
        raise ValueError("The candidate must precede the explicit cutoff.")
    return cutoff


class IncidentContinuationRecoveryStore(Protocol):
    """Optional adapter capability, separate from the existing worker port."""

    def list_stale_claims(self, *, stale_before: float, limit: int,
                         after_id: str | None = None) -> tuple[ContinuationRecoveryCandidate, ...]:
        """Return at most limit claimed rows, ordered by persisted approval_id.

        after_id is an exclusive cursor in that backend's ordering. Selection
        grants no authority. It must not decode invocation payloads.
        """
        ...

    def recover_stale_before_approval(self, *, candidate: ContinuationRecoveryCandidate,
                                      stale_before: float, approval_store: object) -> None:
        """Requeue only after checking all guards in one transaction.

        Require original owner, attempt, timestamp, claimed state, cutoff,
        remaining attempt budget and pending/NULL approval. Return after commit.
        No claim, workflow response, notification, readback retry or new owner.
        """
        ...


class ContinuationRecoveryOutcome(str, Enum):
    REQUEUED = "requeued"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class ContinuationRecoveryResult:
    candidate: ContinuationRecoveryCandidate
    outcome: ContinuationRecoveryOutcome
    error_type: str | None = None


@dataclass(frozen=True)
class ContinuationRecoveryBatch:
    stale_before: float
    results: tuple[ContinuationRecoveryResult, ...]
    halted: bool
    next_after_id: str | None


class IncidentContinuationRecovery:
    def __init__(self, *, continuation_store: IncidentContinuationRecoveryStore,
                 approval_store: object) -> None:
        self._store = continuation_store
        self._approval_store = approval_store

    def run_batch(self, *, stale_before: float, limit: int,
                  after_id: str | None = None) -> ContinuationRecoveryBatch:
        """Run once. The trusted caller supplies a fixed cutoff for each sweep.

        Age is eligibility, not proof of death. A paused worker is fenced by the
        coordinated HITL claim. On any unclassified error, stop without retry,
        readback or cursor advancement: even a commit acknowledgement can fail.
        """
        cutoff = validate_recovery_selection(stale_before=stale_before,
                                             limit=limit, after_id=after_id)
        candidates = self._store.list_stale_claims(stale_before=cutoff,
                                                  limit=limit, after_id=after_id)
        if not isinstance(candidates, tuple) or len(candidates) > limit:
            raise ValueError("Recovery adapter returned an invalid bounded page.")
        seen = set()
        # Validate the whole page before making any transition. Ordering belongs
        # to the backend collation, so do not compare identifiers in Python.
        for candidate in candidates:
            validate_recovery_candidate(candidate, cutoff)
            if candidate.approval_id in seen or candidate.approval_id == after_id:
                raise ValueError("Recovery adapter repeated a candidate or cursor.")
            seen.add(candidate.approval_id)
        results = []
        for candidate in candidates:
            try:
                self._store.recover_stale_before_approval(
                    candidate=candidate, stale_before=cutoff, approval_store=self._approval_store,
                )
            except IncidentContinuationClaimError:
                results.append(ContinuationRecoveryResult(candidate, ContinuationRecoveryOutcome.REJECTED))
            except Exception as error:
                results.append(ContinuationRecoveryResult(
                    candidate, ContinuationRecoveryOutcome.UNCERTAIN, type(error).__name__,
                ))
                return ContinuationRecoveryBatch(cutoff, tuple(results), True, None)
            else:
                results.append(ContinuationRecoveryResult(candidate, ContinuationRecoveryOutcome.REQUEUED))
        next_id = candidates[-1].approval_id if len(candidates) == limit else None
        return ContinuationRecoveryBatch(cutoff, tuple(results), False, next_id)
