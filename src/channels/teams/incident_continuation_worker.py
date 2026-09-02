from __future__ import annotations

import asyncio

from collections.abc import (
    Awaitable,
    Callable,
)

from dataclasses import (
    dataclass,
)

from enum import (
    Enum,
)

from typing import Any

from src.runtime.procedure.approval_store import (
    PendingApprovalStore,
)

from .incident_continuation_store import (
    IncidentContinuationClaimError,
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


@dataclass(
    frozen=True
)
class IncidentContinuationWorkerDependencies:
    """
    Dependencias del worker posterior al ACK.

    El worker NO recibe autoridad operacional
    desde Teams.

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

    worker_id: str

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

    - claim SQLite atómico;
    - nunca reconstruye autoridad;
    - usa el incident processor existente;
    - si falla antes del approval claim puede
      recuperar únicamente mediante el gate
      certificado de 4E.4.3.3;
    - si la aprobación ya fue consumida,
      falla cerrado y NO reintenta;
    - el mensaje terminal se envía antes de
      marcar el continuation job completed.
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

    async def process_next_once(
        self,
    ) -> IncidentContinuationWorkerOutcome:
        dependencies = (
            self._dependencies
        )

        job = (
            dependencies
            .continuation_store
            .claim_next(
                worker_id=(
                    dependencies.worker_id
                )
            )
        )

        if job is None:
            return (
                IncidentContinuationWorkerOutcome
                .IDLE
            )

        approval_id = (
            job.approval_id
        )

        try:
            workflow = (
                dependencies
                .workflow_factory()
            )

            processed = (
                await dependencies.processor(
                    invocation=(
                        job.invocation
                    ),
                    store=(
                        dependencies
                        .approval_store
                    ),
                    workflow=(
                        workflow
                    ),
                )
            )

            await dependencies.terminal_notifier(
                invocation=(
                    job.invocation
                ),
                processed=(
                    processed
                ),
            )

            dependencies.continuation_store.complete(
                approval_id=(
                    approval_id
                ),
                worker_id=(
                    dependencies.worker_id
                ),
            )

            return (
                IncidentContinuationWorkerOutcome
                .COMPLETED
            )

        except Exception as exc:
            #
            # Sólo intentamos recuperación si
            # approval_store demuestra que el
            # processor todavía NO cruzó
            # store.claim().
            #
            try:
                dependencies.continuation_store.recover_claimed_before_approval(
                    approval_id=(
                        approval_id
                    ),
                    worker_id=(
                        dependencies.worker_id
                    ),
                    approval_store=(
                        dependencies
                        .approval_store
                    ),
                )

            except IncidentContinuationClaimError:
                #
                # La aprobación ya fue consumida
                # o el claim no pertenece al worker.
                #
                # No existe replay automático.
                #
                dependencies.continuation_store.fail(
                    approval_id=(
                        approval_id
                    ),
                    worker_id=(
                        dependencies.worker_id
                    ),
                    error=(
                        type(exc).__name__
                    ),
                )

                return (
                    IncidentContinuationWorkerOutcome
                    .FAILED_CLOSED
                )

            else:
                return (
                    IncidentContinuationWorkerOutcome
                    .REQUEUED_PREAPPROVAL
                )

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