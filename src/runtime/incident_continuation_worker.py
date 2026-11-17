from __future__ import annotations

import asyncio
from uuid import uuid4

from collections.abc import (
    Awaitable,
    Callable,
)

from dataclasses import (
    dataclass,
    field,
)

from enum import (
    Enum,
)

from typing import Any

from src.runtime.continuation_approval_store import ContinuationApprovalStore

from src.runtime.procedure.approval_store import (
    PendingApprovalStore,
)

from src.runtime.incident_continuation_store import (
    IncidentContinuationClaimError,
    IncidentContinuationJob,
    IncidentContinuationStatus,
    MAX_PREAPPROVAL_RECOVERY_ATTEMPTS,
    require_continuation_attempt,
    IncidentContinuationStore,
)


WorkflowFactory = Callable[
    [],
    Any,
]


IncidentProcessor = Callable[
    ...,
    Awaitable[Any],
]


TerminalNotifier = Callable[
    ...,
    Awaitable[Any],
]


class IncidentContinuationWorkerOutcome(
    str,
    Enum,
):
    IDLE = "idle"
    COMPLETED = "completed"
    REQUEUED_PREAPPROVAL = (
        "requeued_preapproval"
    )
    FAILED_CLOSED = "failed_closed"
    CLAIM_LOST = "claim_lost"


@dataclass(
    frozen=True
)
class IncidentContinuationWorkerDependencies:
    """
    Dependencias del worker posterior al ACK.

    El worker NO recibe autoridad operacional
    desde el canal.

    La autoridad seguirá procediendo del
    checkpoint + runtime Python original.
    """

    continuation_store: (
        IncidentContinuationStore
    )

    approval_store: PendingApprovalStore

    workflow_factory: WorkflowFactory

    processor: IncidentProcessor

    terminal_notifier: TerminalNotifier

    # Generated once per dependency bundle. Hosts may supply an explicit unique
    # instance identity; the database generation also fences reuse of that ID.
    worker_id: str = field(default_factory=lambda: f"continuation-{uuid4().hex}")

    poll_interval_seconds: float = 0.25

    def __post_init__(
        self,
    ) -> None:
        if (
            not isinstance(
                self.worker_id,
                str,
            )
            or not self.worker_id
            or not self.worker_id.strip()
            or self.worker_id
            != self.worker_id.strip()
        ):
            raise ValueError(
                "worker_id debe ser un string "
                "no vacío y exacto."
            )

        if (
            isinstance(
                self.poll_interval_seconds,
                bool,
            )
            or not isinstance(
                self.poll_interval_seconds,
                (
                    int,
                    float,
                ),
            )
            or self.poll_interval_seconds <= 0
        ):
            raise ValueError(
                "poll_interval_seconds debe ser "
                "mayor que cero."
            )


class IncidentContinuationWorker:
    """
    Consume el handoff durable posterior al ACK.

    Propiedades:

    - claim delegado al almacén inyectado;
    - nunca reconstruye autoridad;
    - usa el incident processor existente;
    - si falla antes del approval claim puede
      recuperar únicamente mediante el gate
      certificado de 4E.4.3.3;
    - si la aprobación ya fue consumida,
      falla cerrado y NO reintenta;
    - el mensaje terminal se envía antes de
      marcar el continuation job completed.
    - las transiciones de cola conservan el intento reclamado;
      el claim HITL usa el almacén ligado a ese intento.
    - no constituye una lease ni recuperación automática de huérfanos.
    """

    def __init__(
        self,
        dependencies: (
            IncidentContinuationWorkerDependencies
        ),
    ) -> None:
        if not isinstance(
            dependencies,
            IncidentContinuationWorkerDependencies,
        ):
            raise TypeError(
                "dependencies debe ser "
                "IncidentContinuationWorkerDependencies."
            )

        self._dependencies = (
            dependencies
        )

    def _fail_owned_job(
        self, job: IncidentContinuationJob, error: str,
    ) -> IncidentContinuationWorkerOutcome:
        try:
            self._dependencies.continuation_store.fail(
                approval_id=job.approval_id,
                worker_id=self._dependencies.worker_id,
                expected_attempt_count=job.attempt_count,
                error=error,
            )
        except IncidentContinuationClaimError:
            # Another attempt owns the row, or it is already terminal. Never
            # fetch a newer generation and use it to overwrite that attempt.
            return IncidentContinuationWorkerOutcome.CLAIM_LOST
        return IncidentContinuationWorkerOutcome.FAILED_CLOSED

    async def process_next_once(
        self,
    ) -> IncidentContinuationWorkerOutcome:
        dependencies = self._dependencies
        job = dependencies.continuation_store.claim_next(
            worker_id=dependencies.worker_id,
        )
        if job is None:
            return IncidentContinuationWorkerOutcome.IDLE
        if (job.status != IncidentContinuationStatus.CLAIMED
                or job.claimed_by != dependencies.worker_id):
            return IncidentContinuationWorkerOutcome.CLAIM_LOST
        try:
            require_continuation_attempt(job.attempt_count)
        except ValueError:
            return IncidentContinuationWorkerOutcome.CLAIM_LOST

        scoped_store = ContinuationApprovalStore(
            job=job, continuation_store=dependencies.continuation_store,
            approval_store=dependencies.approval_store,
        )
        try:
            workflow = dependencies.workflow_factory()
            processed = await dependencies.processor(
                invocation=job.invocation,
                store=scoped_store,
                workflow=workflow,
            )
            await dependencies.terminal_notifier(
                invocation=job.invocation,
                processed=processed,
            )
            dependencies.continuation_store.complete(
                approval_id=job.approval_id,
                worker_id=dependencies.worker_id,
                expected_attempt_count=job.attempt_count,
            )
            return IncidentContinuationWorkerOutcome.COMPLETED
        except Exception as exc:
            error_name = type(exc).__name__
            if scoped_store.claim_attempted:
                # The claim may have committed even when its acknowledgement
                # failed. Never turn a readback into authority for another try.
                return self._fail_owned_job(job, error_name)
            try:
                status, decision = dependencies.approval_store.get_consumption_record(
                    job.approval_id,
                )
            except Exception:
                return self._fail_owned_job(job, error_name)

            if status == "pending" and decision is None:
                if job.attempt_count >= MAX_PREAPPROVAL_RECOVERY_ATTEMPTS:
                    return self._fail_owned_job(job, error_name)
                try:
                    dependencies.continuation_store.recover_claimed_before_approval(
                        approval_id=job.approval_id,
                        worker_id=dependencies.worker_id,
                        expected_attempt_count=job.attempt_count,
                        approval_store=dependencies.approval_store,
                    )
                except IncidentContinuationClaimError:
                    # The approval may have been consumed, or ownership changed.
                    # fail() must still match our original attempt in either case.
                    return self._fail_owned_job(job, error_name)
                return IncidentContinuationWorkerOutcome.REQUEUED_PREAPPROVAL

            return self._fail_owned_job(job, error_name)

    async def run(
        self,
        *,
        stop_event: asyncio.Event,
    ) -> None:
        """
        Loop single-host.

        El loop no constituye persistencia.

        La persistencia reside exclusivamente
        en IncidentContinuationStore.
        """

        if not isinstance(
            stop_event,
            asyncio.Event,
        ):
            raise TypeError(
                "stop_event debe ser asyncio.Event."
            )

        interval = (
            float(
                self
                ._dependencies
                .poll_interval_seconds
            )
        )

        while not stop_event.is_set():
            outcome = await (
                self.process_next_once()
            )

            if (
                outcome
                == IncidentContinuationWorkerOutcome
                .COMPLETED
            ):
                continue

            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=interval,
                )

            except TimeoutError:
                pass
