from __future__ import annotations

from agent_framework import (
    Executor,
    WorkflowContext,
    handler,
)

from src.runtime.procedure.models import (
    ApprovalStatus,
    OperationKind,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
    StepStatus,
    WorkflowStatus,
)

from src.runtime.procedure.runtime import (
    CERTIFIED_MAX_PROCEDURE_OPERATION_ATTEMPTS,
    validate_procedure_iteration_budget,
)

from src.workflows.incident_resolution.operational_capability import (
    OperationalCapability,
)

from src.runtime.procedure.workflow_state import (
    PROCEDURE_RUNTIME_STATE_KEY,
    load_procedure_runtime_state,
    store_procedure_runtime_state,
)

from src.workflows.incident_resolution.models import (
    ProcedureExecutionContext,
)

from src.workflows.incident_resolution.resource_identity import (
    ResourceIdentityResolutionError,
)

from src.workflows.incident_resolution.resource_identity_registry import (
    ResourceIdentityRegistry,
    build_default_resource_identity_registry,
)

from src.workflows.incident_resolution.procedure_capability_registry import (
    ProcedureCapabilityRegistry,
    build_default_procedure_capability_registry,
)

from src.workflows.incident_resolution.parameter_resolution import (
    resolve_required_parameters,
)

from src.workflows.incident_resolution.workflow_input import (
    load_incident_conversation_id,
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

    def __init__(
        self,

        resource_identity_registry: (
            ResourceIdentityRegistry | None
        ) = None,

        procedure_capability_registry: (
            ProcedureCapabilityRegistry | None
        ) = None,
    ) -> None:
        super().__init__(
            id="procedure_runtime"
        )

        self._resource_identity_registry = (
            resource_identity_registry
            or build_default_resource_identity_registry()
        )

        self._procedure_capability_registry = (
            procedure_capability_registry
            or (
                build_default_procedure_capability_registry()
            )
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

        if (
            result.current_step
            != request.requested_step
        ):
            raise ValueError(
                "ProcedureExecutionResult contiene un "
                "current_step diferente al "
                "requested_step autorizado por Python."
            )

    def _resolve_authoritative_target_resource(
        self,
        context: ProcedureExecutionContext,
        *,
        require_registered_identity: bool = False,
        authoritative_required_parameters: (
            tuple[str, ...] | None
        ) = None,
    ) -> str | None:
        """
        Resuelve target_resource utilizando únicamente
        resolvers registrados de identidad operacional.

        Runtime no conoce tipos concretos de recursos.

        No conoce:

        - Azure VM;
        - Storage;
        - SQL;
        - Windows;
        - Linux;
        - nombres específicos de recursos.

        La especialización pertenece exclusivamente
        al ResourceIdentityRegistry y sus adapters.
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

        resource_type = (
            operational.resource_type
        )

        #
        # Compatibilidad transitoria.
        #
        # Los dominios cuya identidad todavía no ha sido
        # registrada conservan el target cognitivo.
        #
        # Esto NO concede permiso de ejecución.
        #
        # FASE 17.3 será quien exija Capability +
        # Identity Resolver para adquirir autoridad
        # operacional.
        #
        if resource_type is None:
            return (
                result.step.target_resource
            )

        if not (
            self
            ._resource_identity_registry
            .contains(
                operation_domain=(
                    result.step.operation_domain
                ),
                resource_type=(
                    resource_type
                ),
            )
        ):
            if require_registered_identity:
                raise (
                    ResourceIdentityResolutionError(
                        "Una capability gobernada "
                        "requiere un "
                        "ResourceIdentityResolver "
                        "registrado para "
                        "operation_domain="
                        f"{result.step.operation_domain!r}, "
                        "resource_type="
                        f"{resource_type!r}."
                    )
                )

            return (
                result.step.target_resource
            )

        resolver = (
            self
            ._resource_identity_registry
            .get_resolver(
                operation_domain=(
                    result.step.operation_domain
                ),
                resource_type=(
                    resource_type
                ),
            )
        )

        if (
            authoritative_required_parameters
            is None
        ):
            required_parameters = tuple(
                result.step.required_parameters
            )

        else:
            required_parameters = (
                authoritative_required_parameters
            )

        if (
            required_parameters
            != resolver.required_parameters
        ):
            raise (
                ResourceIdentityResolutionError(
                    "required_parameters no coincide "
                    "con el contrato exacto del "
                    "resolver de identidad. "
                    "recibidos="
                    f"{required_parameters!r}; "
                    "esperados="
                    f"{resolver.required_parameters!r}."
                )
            )

        identity = resolver.resolve(
            operational
        )

        identity.validate_cognitive_target(
            result.step.target_resource
        )

        return (
            identity.canonical_target_resource
        )

    def _resolve_governed_capability(
        self,
        context: ProcedureExecutionContext,
    ) -> OperationalCapability | None:
        """
        Resuelve la capability autorizada para el
        procedure/version/step exacto.

        Reglas:

        1. Un WRITE requiere binding exacto.
        2. Un READ todavía puede funcionar de forma
           transitoria sin binding.
        3. Si existe binding, la interpretación del
           Procedure Agent debe coincidir exactamente
           con la capability gobernada.
        4. operation_action nunca procede del agente.
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

        step = result.step

        procedure_version = (
            result.procedure.version
        )

        cognitive_operation_kind = (
            OperationKind(
                step.operation_kind
            )
        )

        #
        # No podemos hacer binding versionado
        # sin versión exacta.
        #
        if procedure_version is None:
            if (
                cognitive_operation_kind
                == OperationKind.WRITE
            ):
                raise ValueError(
                    "Una operación WRITE requiere "
                    "procedure_version exacta y "
                    "capability binding gobernado."
                )

            return None

        has_binding = (
            self
            ._procedure_capability_registry
            .contains_binding(
                procedure_id=(
                    result.procedure.id
                ),

                procedure_version=(
                    procedure_version
                ),

                step_id=(
                    step.id
                ),
            )
        )

        #
        # WRITE fail-closed.
        #
        if not has_binding:
            if (
                cognitive_operation_kind
                == OperationKind.WRITE
            ):
                raise ValueError(
                    "Una operación WRITE requiere "
                    "un capability binding exacto "
                    "antes del HITL."
                )

            #
            # Compatibilidad transitoria para READ.
            #
            return None

        capability = (
            self
            ._procedure_capability_registry
            .resolve_applicable_capability(
                procedure_id=(
                    result.procedure.id
                ),

                procedure_version=(
                    procedure_version
                ),

                step_id=(
                    step.id
                ),

                operational_context=(
                    operational
                ),
            )
        )

        #
        # El agente puede interpretar estos campos,
        # pero no convertirlos en autoridad.
        #
        if (
            step.operation_domain
            != capability.operation_domain
        ):
            raise ValueError(
                "operation_domain cognitivo "
                "no coincide con la capability "
                "gobernada."
            )

        if (
            cognitive_operation_kind
            != capability.operation_kind
        ):
            raise ValueError(
                "operation_kind cognitivo "
                "no coincide con la capability "
                "gobernada."
            )

        if (
            tuple(
                step.required_parameters
            )
            != capability.required_parameters
        ):
            raise ValueError(
                "required_parameters cognitivos "
                "no coinciden con la capability "
                "gobernada."
            )

        if (
            operational.resource_type
            != capability.resource_type
        ):
            raise ValueError(
                "resource_type autoritativo "
                "no coincide con la capability "
                "gobernada."
            )

        return capability

    @staticmethod
    def _load_prior_runtime_state(
        ctx: WorkflowContext,
    ) -> ProcedureRuntimeState | None:
        snapshot = ctx.get_state(
            PROCEDURE_RUNTIME_STATE_KEY,
            None,
        )

        if snapshot is None:
            return None

        return load_procedure_runtime_state(
            ctx
        )

    @staticmethod
    def _resolve_carried_retry_count(
        *,
        context: ProcedureExecutionContext,
        prior_state: ProcedureRuntimeState | None,
    ) -> int:
        """
        Conserva retry_count exclusivamente desde
        ProcedureRuntimeState autoritativo.

        Nunca procede:
        - del LLM;
        - del prompt;
        - de ProcedureExecutionResult.
        """

        if prior_state is None:
            return 0

        identity = (
            context.execution_identity
        )

        request = (
            context.request
        )

        result = (
            context.result
        )

        if prior_state.retry_count < 0:
            raise ValueError(
                "retry_count autoritativo inválido."
            )

        if (
            prior_state.workflow_id
            != identity.workflow_id
        ):
            raise ValueError(
                "ProcedureRuntimeState previo "
                "pertenece a otro workflow."
            )

        if (
            prior_state.alert_id
            != identity.alert_id
        ):
            raise ValueError(
                "ProcedureRuntimeState previo "
                "pertenece a otra alerta."
            )

        if (
            prior_state.procedure.id
            != result.procedure.id
        ):
            raise ValueError(
                "ProcedureRuntimeState previo "
                "pertenece a otro procedimiento."
            )

        if (
            prior_state.procedure.version
            != result.procedure.version
        ):
            raise ValueError(
                "ProcedureRuntimeState previo "
                "pertenece a otra versión."
            )

        if (
            prior_state.total_steps
            != result.total_steps
        ):
            raise ValueError(
                "total_steps cambió durante "
                "la continuación del procedimiento."
            )

        requested_step = (
            request.requested_step
        )

        #
        # REPEAT:
        # mismo cursor y fresh operation boundary.
        #
        if (
            requested_step
            == prior_state.current_step
        ):
            if (
                prior_state.step_status
                != StepStatus.PENDING
                or prior_state.workflow_status
                != WorkflowStatus.RUNNING
                or prior_state.approval_status
                != ApprovalStatus.PENDING
                or prior_state.approval_id
                is not None
                or prior_state.resolved_parameters
                != []
                or prior_state.operation_result
                is not None
                or prior_state.verification_result
                is not None
                or prior_state.retry_count
                <= 0
            ):
                raise ValueError(
                    "REPEAT continuation state "
                    "no representa un fresh "
                    "operation boundary."
                )

            return (
                prior_state.retry_count
            )

        #
        # CONTINUE:
        # N -> N+1 conserva el budget acumulado.
        #
        if (
            requested_step
            == prior_state.current_step + 1
        ):
            if (
                prior_state.step_status
                != StepStatus.SUCCEEDED
                or prior_state.workflow_status
                != WorkflowStatus.RUNNING
                or prior_state.verification_result
                is None
            ):
                raise ValueError(
                    "CONTINUE continuation state "
                    "no es autoritativo."
                )

            return (
                prior_state.retry_count
            )

        raise ValueError(
            "Procedure continuation cursor "
            "no corresponde al estado previo."
        )

    def _build_runtime_state(
        self,
        context: ProcedureExecutionContext,
        *,
        conversation_id: str | None = None,
        retry_count: int = 0,
    ) -> ProcedureRuntimeState:
        self._validate_execution_context(
            context
        )

        result = context.result

        if retry_count < 0:
            raise ValueError(
                "retry_count no puede ser negativo."
            )

        if (
            result.total_steps
            + retry_count
            > CERTIFIED_MAX_PROCEDURE_OPERATION_ATTEMPTS
        ):
            raise ValueError(
                "Procedure iteration budget exceeded."
            )

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

        capability = (
            self
            ._resolve_governed_capability(
                context
            )
        )

        if capability is None:
            authoritative_required_parameters = (
                tuple(
                    result.step.required_parameters
                )
            )

        else:
            authoritative_required_parameters = (
                capability.required_parameters
            )

        parameter_resolution = (
            resolve_required_parameters(
                required_parameters=list(
                    authoritative_required_parameters
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
            self
            ._resolve_authoritative_target_resource(
                context,

                require_registered_identity=(
                    capability is not None
                ),

                authoritative_required_parameters=(
                    authoritative_required_parameters
                ),
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

            conversation_id=(
                conversation_id
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
                    capability.operation_domain
                    if capability is not None
                    else result.step.operation_domain
                ),

                operation_kind=(
                    capability.operation_kind
                    if capability is not None
                    else OperationKind(
                        result.step.operation_kind
                    )
                ),

                operation_action=(
                    capability.operation_action
                    if capability is not None
                    else None
                ),

                capability_id=(
                    capability.capability_id
                    if capability is not None
                    else None
                ),

                hitl_required=(
                    capability.hitl_required
                    if capability is not None
                    else None
                ),

                target_resource=(
                    target_resource
                ),

                required_parameters=list(
                    authoritative_required_parameters
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

            retry_count=(
                retry_count
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
        conversation_id = (
            load_incident_conversation_id(
                ctx
            )
        )

        prior_state = (
            self._load_prior_runtime_state(
                ctx
            )
        )

        retry_count = (
            self._resolve_carried_retry_count(
                context=context,
                prior_state=prior_state,
            )
        )

        recheck_count = (
            prior_state.recheck_count
            if prior_state is not None
            else 0
        )

        validate_procedure_iteration_budget(
            total_steps=(
                context.result.total_steps
            ),
            retry_count=retry_count,
            recheck_count=recheck_count,
        )

        state = (
            self._build_runtime_state(
                context,
                conversation_id=(
                    conversation_id
                ),
                retry_count=(
                    retry_count
                ),
            )
        )

        state.recheck_count = (
            recheck_count
        )

        store_procedure_runtime_state(
            ctx,
            state,
        )

        await ctx.send_message(
            state
        )