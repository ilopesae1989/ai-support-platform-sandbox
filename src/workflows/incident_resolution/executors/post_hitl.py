from typing import Literal

from agent_framework import (
    Executor,
    WorkflowContext,
    handler,
)
from pydantic import BaseModel

from src.runtime.procedure.models import (
    ApprovedProcedureStep,
)


class PostHitlRouteResult(BaseModel):
    """
    Resultado terminal temporal de FASE 12.

    No ejecuta ninguna operación técnica.

    Permite demostrar qué ruta operativa habría sido
    seleccionada después de HITL.
    """

    workflow_id: str
    alert_id: str

    procedure_id: str
    procedure_version: str | None = None

    current_step: int
    step_id: str

    route: Literal[
        "azure",
        "database",
        "itsm",
        "windows",
        "linux",
        "networking",
        "microsoft365",
        "blocked",
    ]

    operation_kind: str
    target_resource: str | None = None

    blocked_reason: str | None = None


class _BasePostHitlRouteExecutor(Executor):
    """
    Base de los placeholders post-HITL.

    Estos executors NO realizan operaciones reales.
    """

    route_name: str

    def __init__(
        self,
        *,
        executor_id: str,
        route_name: str,
    ) -> None:
        super().__init__(
            id=executor_id
        )

        self.route_name = route_name

    @handler
    async def handle(
        self,
        step: ApprovedProcedureStep,
        ctx: WorkflowContext[
            None,
            PostHitlRouteResult,
        ],
    ) -> None:
        await ctx.yield_output(
            PostHitlRouteResult(
                workflow_id=step.workflow_id,
                alert_id=step.alert_id,
                procedure_id=step.procedure_id,
                procedure_version=(
                    step.procedure_version
                ),
                current_step=step.current_step,
                step_id=step.step_id,
                route=self.route_name,
                operation_kind=(
                    step.operation_kind.value
                ),
                target_resource=(
                    step.target_resource
                ),
                blocked_reason=None,
            )
        )


class AzureRouteExecutor(
    _BasePostHitlRouteExecutor
):
    def __init__(self) -> None:
        super().__init__(
            executor_id="post_hitl_azure",
            route_name="azure",
        )


class DatabaseRouteExecutor(
    _BasePostHitlRouteExecutor
):
    def __init__(self) -> None:
        super().__init__(
            executor_id="post_hitl_database",
            route_name="database",
        )


class ItsmRouteExecutor(
    _BasePostHitlRouteExecutor
):
    def __init__(self) -> None:
        super().__init__(
            executor_id="post_hitl_itsm",
            route_name="itsm",
        )


class WindowsRouteExecutor(
    _BasePostHitlRouteExecutor
):
    def __init__(self) -> None:
        super().__init__(
            executor_id="post_hitl_windows",
            route_name="windows",
        )


class LinuxRouteExecutor(
    _BasePostHitlRouteExecutor
):
    def __init__(self) -> None:
        super().__init__(
            executor_id="post_hitl_linux",
            route_name="linux",
        )


class NetworkingRouteExecutor(
    _BasePostHitlRouteExecutor
):
    def __init__(self) -> None:
        super().__init__(
            executor_id="post_hitl_networking",
            route_name="networking",
        )


class Microsoft365RouteExecutor(
    _BasePostHitlRouteExecutor
):
    def __init__(self) -> None:
        super().__init__(
            executor_id="post_hitl_microsoft365",
            route_name="microsoft365",
        )


class BlockedRouteExecutor(Executor):
    """
    Destino fail-closed.

    No ejecuta ninguna operación.
    """

    def __init__(self) -> None:
        super().__init__(
            id="post_hitl_blocked"
        )

    @handler
    async def handle(
        self,
        step: ApprovedProcedureStep,
        ctx: WorkflowContext[
            None,
            PostHitlRouteResult,
        ],
    ) -> None:
        await ctx.yield_output(
            PostHitlRouteResult(
                workflow_id=step.workflow_id,
                alert_id=step.alert_id,
                procedure_id=step.procedure_id,
                procedure_version=(
                    step.procedure_version
                ),
                current_step=step.current_step,
                step_id=step.step_id,
                route="blocked",
                operation_kind=(
                    step.operation_kind.value
                ),
                target_resource=(
                    step.target_resource
                ),
                blocked_reason=(
                    "El paso aprobado no satisface "
                    "las reglas deterministas de "
                    "routing post-HITL."
                ),
            )
        )