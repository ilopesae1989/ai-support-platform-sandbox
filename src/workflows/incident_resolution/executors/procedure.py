from agent_framework import (
    Executor,
    WorkflowContext,
    handler,
)

from src.agents.contracts import (
    ProcedureExecutionResult,
)

from src.agents.foundry_agents import (
    FoundryAgents,
)

from src.workflows.incident_resolution.models import (
    ProcedureExecutionContext,
    ProcedureExecutionInput,
    ProcedureExecutionRequest,
)


class ProcedureExecutionExecutor(Executor):
    """
    Procedure v5 recibe únicamente el request
    cognitivo.

    ExecutionIdentity y OperationalContext permanecen
    fuera del prompt.
    """

    def __init__(
        self,
        agents: FoundryAgents,
    ) -> None:
        super().__init__(
            id="procedure_execution"
        )

        self._agents = agents

    @staticmethod
    def _validate_input(
        execution_input: ProcedureExecutionInput,
    ) -> None:
        request = (
            execution_input.request
        )

        identity = (
            execution_input.execution_identity
        )

        operational = (
            execution_input.operational_context
        )

        if (
            request.alert_id
            != operational.alert_id
        ):
            raise ValueError(
                "ProcedureExecutionInput contiene "
                "identidades de alerta diferentes."
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
            identity.correlation_id
            != operational.correlation_id
        ):
            raise ValueError(
                "ExecutionIdentity contiene un "
                "correlation_id diferente al "
                "OperationalContext."
            )

        if not identity.workflow_id:
            raise ValueError(
                "ExecutionIdentity no contiene "
                "workflow_id."
            )

    @staticmethod
    def _validate_result_identity(
        request: ProcedureExecutionRequest,
        result: ProcedureExecutionResult,
    ) -> None:
        if (
            result.alert_id
            != request.alert_id
        ):
            raise ValueError(
                "Procedure Execution devolvió "
                "un alert_id diferente al solicitado."
            )

        if (
            result.procedure.id
            != request.procedure_id
        ):
            raise ValueError(
                "Procedure Execution devolvió "
                "un procedimiento diferente "
                "al solicitado."
            )

        if (
            request.procedure_version is not None
            and (
                result.procedure.version
                != request.procedure_version
            )
        ):
            raise ValueError(
                "Procedure Execution devolvió "
                "una versión diferente "
                "a la solicitada."
            )

    @handler
    async def process_request(
        self,
        execution_input: ProcedureExecutionInput,
        ctx: WorkflowContext[
            ProcedureExecutionContext
        ],
    ) -> None:
        self._validate_input(
            execution_input
        )

        request = (
            execution_input.request
        )

        prompt = (
            self._build_prompt(
                request
            )
        )

        result = (
            await self._agents
            .run_procedure_execution(
                prompt
            )
        )

        self._validate_result_identity(
            request,
            result,
        )

        await ctx.send_message(
            ProcedureExecutionContext(
                request=request,

                result=result,

                execution_identity=(
                    execution_input
                    .execution_identity
                    .model_copy(
                        deep=True
                    )
                ),

                operational_context=(
                    execution_input
                    .operational_context
                    .model_copy(
                        deep=True
                    )
                ),
            )
        )

    @staticmethod
    def _build_prompt(
        request: ProcedureExecutionRequest,
    ) -> str:
        version = (
            request.procedure_version
            or "no especificada"
        )

        return f"""
mode = "prepare_step"

Prepara la ejecución del procedimiento asociado a la siguiente alerta:

AlertId: {request.alert_id}

Resultado del Triage:
procedure_found: {str(request.procedure_found).lower()}
procedure_match: {request.procedure_match}
execution_eligible: {str(request.execution_eligible).lower()}

Procedimiento:
ID: {request.procedure_id}
Nombre: {request.procedure_name}
Versión: {version}

Recurso afectado:
{request.affected_resource}

Contrato obligatorio de target_resource:

- target_resource identifica el recurso al que aplica
    exactamente el paso recuperado.

- Para una operación Azure a nivel de suscripción cuyo
    parámetro requerido sea subscription_id, devuelve
    target_resource exclusivamente como uno de estos
    valores:

    1. el literal exacto "subscription"; o
    2. el valor exacto de Recurso afectado mostrado arriba.

- No uses descripciones como "Azure subscription",
    "suscripción Azure", "subscription_id" ni otros textos.

- No construyas rutas ARM ni transformes el identificador.

- No inventes ni sustituyas el identificador del recurso.

Incidencia:
{request.incident_description}

Recupera el procedimiento corporativo indicado y devuelve únicamente
el paso que corresponde procesar.
""".strip()