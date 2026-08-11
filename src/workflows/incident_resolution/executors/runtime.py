from __future__ import annotations

from agent_framework import (
    Executor,
    WorkflowContext,
    handler,
)

from src.runtime.procedure.models import (
    OperationKind,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
)

from src.runtime.procedure.workflow_state import (
    store_procedure_runtime_state,
)

from src.workflows.incident_resolution.models import (
    ProcedureExecutionContext,
)

from src.workflows.incident_resolution.parameter_resolution import (
    resolve_required_parameters,
)


class ProcedureRuntimeExecutor(Executor):
    """
    Construye ProcedureRuntimeState preservando la
    identidad generada antes de Procedure v5.
    """

    def __init__(self) -> None:
        super().__init__(
            id="procedure_runtime"
        )

    @staticmethod
    def _validate_execution_context(
        context: ProcedureExecutionContext,
    ) -> None:
        request = context.request
        result = context.result

        identity = (
            context.execution_identity
        )

        operational = (
            context.operational_context
        )

        if (
            request.alert_id
            != operational.alert_id
        ):
            raise ValueError(
                "OperationalContext no corresponde "
                "a la alerta de Procedure Execution."
            )

        if (
            identity.alert_id
            != request.alert_id
        ):
            raise ValueError(
                "ExecutionIdentity no corresponde "
                "a la alerta solicitada."
            )

        if (
            result.alert_id
            != request.alert_id
        ):
            raise ValueError(
                "ProcedureExecutionResult no corresponde "
                "a la alerta solicitada."
            )

        if (
            identity.correlation_id
            != operational.correlation_id
        ):
            raise ValueError(
                "La correlación operacional "
                "no coincide con ExecutionIdentity."
            )

        if not identity.workflow_id:
            raise ValueError(
                "ExecutionIdentity no contiene "
                "workflow_id."
            )

        if (
            result.procedure.id
            != request.procedure_id
        ):
            raise ValueError(
                "ProcedureExecutionResult no corresponde "
                "al procedimiento solicitado."
            )

        if (
            request.procedure_version is not None
            and (
                result.procedure.version
                != request.procedure_version
            )
        ):
            raise ValueError(
                "ProcedureExecutionResult no corresponde "
                "a la versión solicitada."
            )

    @staticmethod
    def _resolve_authoritative_target_resource(
        context: ProcedureExecutionContext,
    ) -> str | None:
        """
        Resuelve el target_resource que puede cruzar
        la frontera hacia ProcedureRuntimeState.

        Para Azure, el target_resource operativo no
        puede depender de texto libre generado por
        Procedure Execution.

        El tipo de recurso procede exclusivamente de
        OperationalContext, construido desde campos
        tipados de NormalizedAlert.

        El identificador concreto del recurso no se
        pierde: se conserva mediante los parámetros
        operacionales resueltos, por ejemplo:

            resource_type = "subscription"

            subscription_id =
                "557fdabc-..."

        Así se mantiene separada:

        - la clase/tipo de recurso autorizado;
        - la identidad concreta resuelta del recurso.
        """

        result = context.result
        operational = (
            context.operational_context
        )

        if result.step is None:
            raise ValueError(
                "ProcedureExecutionResult "
                "no contiene step."
            )

        if (
            result.step.operation_domain
            != "azure"
        ):
            return (
                result.step.target_resource
            )

        resource_type = (
            operational.resource_type
        )

        if (
            resource_type is None
            or not resource_type.strip()
        ):
            raise ValueError(
                "Una operación Azure requiere "
                "resource_type autoritativo en "
                "OperationalContext antes del HITL."
            )

        return resource_type

    @classmethod
    def _build_runtime_state(
        cls,
        context: ProcedureExecutionContext,
    ) -> ProcedureRuntimeState:
        cls._validate_execution_context(
            context
        )

        result = context.result

        identity = (
            context.execution_identity
        )

        if result.blocked_by_policy:
            raise ValueError(
                "El procedimiento está bloqueado "
                "por política."
            )

        if not result.execution_allowed:
            raise ValueError(
                "El procedimiento no está permitido "
                "para ejecución."
            )

        if (
            result.next_action
            != "execute_step"
        ):
            raise ValueError(
                "El workflow esperaba "
                "next_action=execute_step."
            )

        if result.step is None:
            raise ValueError(
                "ProcedureExecutionResult "
                "no contiene step."
            )

        parameter_resolution = (
            resolve_required_parameters(
                required_parameters=list(
                    result.step.required_parameters
                ),

                context=(
                    context.operational_context
                ),
            )
        )

        if not parameter_resolution.complete:
            raise ValueError(
                "No pueden resolverse todos los "
                "parámetros requeridos por el paso. "
                "Parámetros pendientes: "
                + ", ".join(
                    parameter_resolution
                    .missing_parameters
                )
            )

        target_resource = (
            cls
            ._resolve_authoritative_target_resource(
                context
            )
        )

        return ProcedureRuntimeState(
            workflow_id=(
                identity.workflow_id
            ),

            alert_id=(
                identity.alert_id
            ),

            correlation_id=(
                identity.correlation_id
            ),

            procedure=ProcedureReference(
                id=result.procedure.id,

                name=result.procedure.name,

                version=(
                    result.procedure.version
                ),
            ),

            total_steps=(
                result.total_steps
            ),

            current_step=(
                result.current_step
            ),

            step=ProcedureStep(
                id=result.step.id,

                description=(
                    result.step.description
                ),

                step_type=(
                    result.step.step_type
                ),

                operation_domain=(
                    result.step.operation_domain
                ),

                operation_kind=(
                    OperationKind(
                        result.step.operation_kind
                    )
                ),

                target_resource=(
                    target_resource
                ),

                required_parameters=list(
                    result.step.required_parameters
                ),

                preconditions=list(
                    result.step.preconditions
                ),

                expected_result=(
                    result.step.expected_result
                ),

                verification=(
                    result.step.verification
                ),
            ),

            resolved_parameters=list(
                parameter_resolution
                .resolved_parameters
            ),
        )

    @handler
    async def create_runtime_state(
        self,
        context: ProcedureExecutionContext,
        ctx: WorkflowContext[
            ProcedureRuntimeState
        ],
    ) -> None:
        state = (
            self._build_runtime_state(
                context
            )
        )

        store_procedure_runtime_state(
            ctx,
            state,
        )

        await ctx.send_message(
            state
        )