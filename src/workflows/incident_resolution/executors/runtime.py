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
    identidad generada antes de Procedure.

    El Runtime constituye la frontera entre:

        salida cognitiva de Procedure
                ↓
        estado operacional autoritativo

    Ningún valor cognitivo adquiere autoridad
    operacional por el mero hecho de haber sido
    producido por el agente.
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
        Canonicaliza únicamente scopes Azure para los
        que existe una regla operacional determinista.

        Actualmente está definida la operación Azure
        a nivel de suscripción:

            operation_domain = azure
            required_parameters = ["subscription_id"]

        Para ese caso:

            target_resource = "subscription"

        El UUID concreto autorizado permanece en:

            resolved_parameters.subscription_id

        y procede exclusivamente de
        OperationalContext.

        Procedure puede haber expresado cognitivamente
        el target como:

            "subscription"

        o como:

            "<subscription_id>"

        Ambas representaciones sólo son aceptadas si
        coinciden con el contexto operacional
        autoritativo.

        Para otros scopes Azure todavía no existe una
        regla canónica general. En esos casos se
        conserva el target preparado por Procedure para
        que llegue exactamente al HITL y sea aprobado
        como parte de la operación concreta.

        No se intenta inferir, transformar ni
        generalizar esos scopes.
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

        required_parameters = list(
            result.step.required_parameters
        )

        #
        # Única regla canónica Azure definida
        # actualmente:
        #
        # operación sobre una suscripción concreta.
        #
        if (
            required_parameters
            != ["subscription_id"]
        ):
            return (
                result.step.target_resource
            )

        if (
            operational.resource_type
            != "subscription"
        ):
            raise ValueError(
                "Una operación Azure de suscripción "
                "requiere resource_type=subscription "
                "autoritativo en OperationalContext "
                "antes del HITL."
            )

        subscription_id = (
            operational.subscription_id
        )

        if (
            subscription_id is None
            or not subscription_id.strip()
        ):
            raise ValueError(
                "Una operación Azure de suscripción "
                "requiere subscription_id autoritativo "
                "antes del HITL."
            )

        allowed_cognitive_targets = {
            "subscription",
            subscription_id,
        }

        if (
            result.step.target_resource
            not in allowed_cognitive_targets
        ):
            raise ValueError(
                "Procedure Execution devolvió un "
                "target_resource incompatible con "
                "la suscripción autoritativa. "
                "target_resource="
                f"{result.step.target_resource!r}; "
                "valores admitidos="
                f"{sorted(allowed_cognitive_targets)!r}."
            )

        return "subscription"

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