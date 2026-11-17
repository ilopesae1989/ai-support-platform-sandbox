"""Optional host-owned scheduling of the existing pre-HITL recovery service."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from math import isfinite
import time
from typing import Callable

from src.runtime.incident_continuation_recovery import (
    ContinuationRecoveryBatch, ContinuationRecoveryOutcome,
    IncidentContinuationRecovery, MAX_RECOVERY_BATCH_SIZE,
)


_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ContinuationRecoveryPolicy:
    min_claim_age_seconds: int
    interval_seconds: int
    batch_size: int
    max_batches_per_cycle: int

    def __post_init__(self) -> None:
        for value in (self.min_claim_age_seconds, self.interval_seconds,
                      self.batch_size, self.max_batches_per_cycle):
            if type(value) is not int or not 1 <= value <= 86400:
                raise ValueError("Recovery settings require integers between 1 and 86400.")
        if self.batch_size > MAX_RECOVERY_BATCH_SIZE or self.max_batches_per_cycle > 100:
            raise ValueError("Recovery batch size and batches per cycle cannot exceed 100.")


@dataclass(frozen=True)
class ContinuationRecoveryCycle:
    cycle: int
    batches: int
    scanned: int
    requeued: int
    rejected: int
    uncertain: int
    reason: str
    error_type: str | None = None


class IncidentContinuationRecoveryRunner:
    """One lifecycle, sequential bounded cycles; an uncertain result latches halt.

    A sweep keeps its cutoff/cursor across capped cycles to avoid starvation.
    Cancellation drains the submitted synchronous batch before propagating.
    Bounds constrain work count, not driver latency or process termination.
    """

    def __init__(self, *, recovery: IncidentContinuationRecovery,
                 policy: ContinuationRecoveryPolicy,
                 clock: Callable[[], float] = time.time) -> None:
        if not isinstance(policy, ContinuationRecoveryPolicy):
            raise TypeError("An explicit continuation recovery policy is required.")
        self._recovery = recovery
        self._policy = policy
        self._clock = clock
        self._used = False
        self.halted = False
        self.last_cycle: ContinuationRecoveryCycle | None = None

    async def _batch(self, **selection) -> tuple[ContinuationRecoveryBatch | None, str | None, bool]:
        # Keep a strong reference and shield every wait, including repeated
        # cancellation. Cancelling to_thread cannot stop its running transaction.
        task = asyncio.create_task(asyncio.to_thread(self._recovery.run_batch, **selection))
        cancelled = False
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                cancelled = True
            except Exception:
                break
        if task.cancelled():
            # The private task should only be cancelled by loop shutdown.
            return None, "CancelledError", True
        try:
            return task.result(), None, cancelled
        except Exception as error:
            return None, type(error).__name__, cancelled

    def _report(self, cycle: int, batches: int, counts: dict[str, int],
                reason: str, error_type: str | None = None) -> None:
        self.last_cycle = ContinuationRecoveryCycle(
            cycle, batches, sum(counts.values()), counts["requeued"],
            counts["rejected"], counts["uncertain"], reason, error_type,
        )
        # Aggregate fields only. Never log payloads, owners, cursors or exception text.
        _LOGGER.log(logging.ERROR if self.halted else logging.INFO,
                    "continuation_recovery_cycle cycle=%s batches=%s scanned=%s requeued=%s "
                    "rejected=%s uncertain=%s reason=%s error_type=%s halted=%s",
                    cycle, batches, self.last_cycle.scanned, counts["requeued"],
                    counts["rejected"], counts["uncertain"], reason, error_type, self.halted,
                    extra={
                        "recovery_cycle": self.last_cycle,
                        "recovery_halted": self.halted,
                    })

    async def run(self, *, stop_event: asyncio.Event) -> None:
        if self._used:
            raise RuntimeError("A recovery runner cannot be restarted or shared by hosts.")
        self._used = True
        cutoff = None
        cursor = None
        cycle = 0
        while not stop_event.is_set():
            cycle += 1
            counts = {outcome.value: 0 for outcome in ContinuationRecoveryOutcome}
            batches = 0
            reason = "cycle_limit"
            error_type = None
            if cutoff is None:
                try:
                    now = self._clock()
                    if type(now) not in (int, float) or not isfinite(now) or now < 0:
                        raise ValueError("Invalid recovery clock.")
                    cutoff = max(0.0, now - self._policy.min_claim_age_seconds)
                except Exception as error:
                    self.halted = True
                    self._report(cycle, 0, counts, "clock_error", type(error).__name__)
                    return
            for _ in range(self._policy.max_batches_per_cycle):
                if stop_event.is_set():
                    reason = "stopped"
                    break
                batch, error_type, cancelled = await self._batch(
                    stale_before=cutoff, limit=self._policy.batch_size, after_id=cursor,
                )
                batches += 1
                if batch is None:
                    self.halted = True
                    reason = "batch_error"
                else:
                    for result in batch.results:
                        counts[result.outcome.value] += 1
                    if batch.halted:
                        self.halted = True
                        reason = "uncertain"
                        error_type = next((r.error_type for r in batch.results if r.error_type), None)
                    elif cancelled:
                        reason = "cancelled"
                    elif stop_event.is_set():
                        reason = "stopped"
                    else:
                        cursor = batch.next_after_id
                        if cursor is None:
                            cutoff = None
                            reason = "sweep_complete"
                if cancelled:
                    self._report(cycle, batches, counts, reason, error_type)
                    raise asyncio.CancelledError
                if self.halted or reason != "cycle_limit":
                    break
            self._report(cycle, batches, counts, reason, error_type)
            if self.halted or stop_event.is_set():
                return
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self._policy.interval_seconds)
            except TimeoutError:
                pass
