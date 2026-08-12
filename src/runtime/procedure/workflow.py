from dataclasses import (
    dataclass,
    field,
    fields,
)

from agent_framework import (
    Executor,
    FileCheckpointStorage,
    WorkflowBuilder,
    WorkflowContext,
    handler,
    response_handler,
)

from .identity import (
    create_approval_id,
)

from .models import (
    ApprovalStatus,
    ApprovedProcedureStep,
    NextAction,
    OperationAction,
    ProcedureRuntimeState,
    ResolvedParameter,
    StepStatus,
)

from .runtime import (
    ProcedureRuntime,
)

from .workflow_state import (
    store_procedure_runtime_state,
)


@dataclass
class ApprovalRequest:
    workflow_id: str
    approval_id: str

    alert_id: str
    correlation_id: str | None

    conversation_id: str | None

    procedure_id: str
    procedure_version: str | None

    current_step: int
    step_id: str

    description: str

    operation_domain: str
    operation_kind: str

    operation_action: str | None

    next_action: str

    target_resource: str | None

    required_parameters: list[str] = field(
        default_factory=list
    )

    resolved_parameters: list[
        ResolvedParameter
    ] = field(
        default_factory=list
    )


@dataclass
class ApprovalOutcome:
    workflow_id: str
    approved: bool
    status: str


def _validate_parameter_binding(
    state: ProcedureRuntimeState,
) -> None:
    required = list(
        state.step.required_parameters
    )

    resolved_names = [
        parameter.name
        for parameter
        in state.resolved_parameters
    ]

    if required != resolved_names:
        raise ValueError(
            "Los parámetros resueltos no coinciden "
            "exactamente con required_parameters."
        )


def build_approved_procedure_step(
    state: ProcedureRuntimeState,
) -> ApprovedProcedureStep:
    if (
        state.approval_status
        != ApprovalStatus.APPROVED
    ):
        raise ValueError(
            "No puede construirse "
            "ApprovedProcedureStep sin "
            "aprobación humana válida."
        )

    if (
        state.step_status
        != StepStatus.APPROVED
    ):
        raise ValueError(
            "El paso no está en estado approved."
        )

    if not state.approval_id:
        raise ValueError(
            "El estado aprobado no contiene "
            "approval_id."
        )

    if (
        not state.step.description
        or not state.step.description.strip()
    ):
        raise ValueError(
            "El paso aprobado no contiene "
            "description válida."
        )

    _validate_parameter_binding(
        state
    )

    return ApprovedProcedureStep(
        workflow_id=(
            state.workflow_id
        ),

        approval_id=(
            state.approval_id
        ),

        alert_id=(
            state.alert_id
        ),

        correlation_id=(
            state.correlation_id
        ),

        conversation_id=(
            state.conversation_id
        ),

        procedure_id=(
            state.procedure.id
        ),

        procedure_version=(
            state.procedure.version
        ),

        current_step=(
            state.current_step
        ),

        step_id=(
            state.step.id
        ),

        description=(
            state.step.description
        ),

        operation_domain=(
            state.step.operation_domain
        ),

        operation_kind=(
            state.step.operation_kind
        ),

        operation_action=(
            state.step.operation_action
        ),

        next_action=(
            NextAction.EXECUTE_STEP
        ),

        target_resource=(
            state.step.target_resource
        ),

        required_parameters=list(
            state.step.required_parameters
        ),

        resolved_parameters=[
            parameter.model_copy(
                deep=True
            )
            for parameter
            in state.resolved_parameters
        ],

        approved=True,
    )


class ProcedureApprovalExecutor(Executor):
    def __init__(self) -> None:
        super().__init__(
            id="procedure_approval"
        )

        self._runtime = (
            ProcedureRuntime()
        )

        self._pending_state: (
            ProcedureRuntimeState | None
        ) = None

    @staticmethod
    def _build_approval_request(
        state: ProcedureRuntimeState,
    ) -> ApprovalRequest:
        _validate_parameter_binding(
            state
        )

        if not state.approval_id:
            raise ValueError(
                "No puede construirse ApprovalRequest "
                "sin approval_id."
            )

        if (
            not state.step.description
            or not state.step.description.strip()
        ):
            raise ValueError(
                "No puede construirse ApprovalRequest "
                "sin description válida."
            )

        return ApprovalRequest(
            workflow_id=(
                state.workflow_id
            ),

            approval_id=(
                state.approval_id
            ),

            alert_id=(
                state.alert_id
            ),

            correlation_id=(
                state.correlation_id
            ),

            conversation_id=(
                state.conversation_id
            ),

            procedure_id=(
                state.procedure.id
            ),

            procedure_version=(
                state.procedure.version
            ),

            current_step=(
                state.current_step
            ),

            step_id=(
                state.step.id
            ),

            description=(
                state.step.description
            ),

            operation_domain=(
                state.step.operation_domain
            ),

            operation_kind=(
                state.step.operation_kind.value
            ),

            operation_action=(
                (
                    state.step.operation_action.value
                    if state.step.operation_action
                    is not None
                    else None
                )
            ),

            next_action=(
                NextAction.EXECUTE_STEP.value
            ),

            target_resource=(
                state.step.target_resource
            ),

            required_parameters=list(
                state.step.required_parameters
            ),

            resolved_parameters=[
                parameter.model_copy(
                    deep=True
                )
                for parameter
                in state.resolved_parameters
            ],
        )

    def _validate_original_request(
        self,
        original_request: ApprovalRequest,
    ) -> None:
        if self._pending_state is None:
            raise RuntimeError(
                "Se recibió una respuesta de aprobación "
                "sin estado pendiente."
            )

        expected_request = (
            self._build_approval_request(
                self._pending_state
            )
        )

        if (
            original_request
            == expected_request
        ):
            return

        changed_fields = [
            item.name
            for item in fields(
                ApprovalRequest
            )
            if (
                getattr(
                    original_request,
                    item.name,
                )
                != getattr(
                    expected_request,
                    item.name,
                )
            )
        ]

        raise RuntimeError(
            "La solicitud de aprobación fue alterada "
            "o no corresponde al estado pendiente. "
            "Campos distintos: "
            + ", ".join(
                changed_fields
            )
        )

    @handler
    async def prepare_step(
        self,
        state: ProcedureRuntimeState,
        ctx: WorkflowContext[
            ApprovedProcedureStep,
            ApprovalOutcome,
        ],
    ) -> None:
        state = (
            self._runtime.prepare_current_step(
                state
            )
        )

        if (
            state.step_status
            == StepStatus.WAITING_APPROVAL
        ):
            #
            # Se genera una sola vez.
            #
            if state.approval_id is None:
                state.approval_id = (
                    create_approval_id()
                )

            store_procedure_runtime_state(
                ctx,
                state,
            )

            self._pending_state = (
                state
            )

            request = (
                self._build_approval_request(
                    state
                )
            )

            await ctx.request_info(
                request_data=request,
                response_type=bool,
            )

            return

        store_procedure_runtime_state(
            ctx,
            state,
        )

        await ctx.yield_output(
            ApprovalOutcome(
                workflow_id=(
                    state.workflow_id
                ),

                approved=True,

                status=(
                    state.workflow_status.value
                ),
            )
        )

    @response_handler
    async def handle_approval_response(
        self,
        original_request: ApprovalRequest,
        response: bool,
        ctx: WorkflowContext[
            ApprovedProcedureStep,
            ApprovalOutcome,
        ],
    ) -> None:
        self._validate_original_request(
            original_request
        )

        pending_state = (
            self._pending_state
        )

        if pending_state is None:
            raise RuntimeError(
                "No existe estado pendiente "
                "para registrar la aprobación."
            )

        state = (
            self._runtime.register_approval(
                pending_state,
                approved=response,
            )
        )

        store_procedure_runtime_state(
            ctx,
            state,
        )

        #
        # Consumo local.
        #
        self._pending_state = None

        if response is False:
            await ctx.yield_output(
                ApprovalOutcome(
                    workflow_id=(
                        state.workflow_id
                    ),

                    approved=False,

                    status=(
                        state.workflow_status.value
                    ),
                )
            )

            return

        await ctx.send_message(
            build_approved_procedure_step(
                state
            )
        )

    async def on_checkpoint_save(
        self,
    ) -> dict:
        if self._pending_state is None:
            return {
                "pending_state": None,
            }

        return {
            "pending_state":
                self._pending_state.model_dump(
                    mode="json"
                ),
        }

    async def on_checkpoint_restore(
        self,
        state: dict,
    ) -> None:
        pending_state = (
            state.get(
                "pending_state"
            )
        )

        if pending_state is None:
            self._pending_state = None
            return

        self._pending_state = (
            ProcedureRuntimeState.model_validate(
                pending_state
            )
        )


class ApprovedStepOutputExecutor(Executor):
    def __init__(self) -> None:
        super().__init__(
            id="approved_step_output"
        )

    @handler
    async def handle(
        self,
        step: ApprovedProcedureStep,
        ctx: WorkflowContext[
            None,
            ApprovedProcedureStep,
        ],
    ) -> None:
        await ctx.yield_output(
            step
        )


def _allowed_checkpoint_types() -> set[str]:
    return {
        "src.runtime.procedure.workflow:ApprovalRequest",
        "src.runtime.procedure.workflow:ApprovalOutcome",

        "src.runtime.procedure.models:StepStatus",
        "src.runtime.procedure.models:WorkflowStatus",
        "src.runtime.procedure.models:ApprovalStatus",
        "src.runtime.procedure.models:OperationKind",
        "src.runtime.procedure.models:NextAction",

        "src.runtime.procedure.models:ProcedureReference",
        "src.runtime.procedure.models:ProcedureStep",
        "src.runtime.procedure.models:StepEvidence",
        "src.runtime.procedure.models:ProcedureExecutionResult",
        "src.runtime.procedure.models:ResolvedParameter",
        "src.runtime.procedure.models:ProcedureRuntimeState",
        "src.runtime.procedure.models:ApprovedProcedureStep",
    }


def build_procedure_approval_workflow(
    checkpoint_path: str | None = None,
):
    executor = (
        ProcedureApprovalExecutor()
    )

    approved_output = (
        ApprovedStepOutputExecutor()
    )

    if checkpoint_path is None:
        return (
            WorkflowBuilder(
                start_executor=executor,

                output_from=[
                    executor,
                    approved_output,
                ],

                name="procedure-runtime",
            )
            .add_edge(
                executor,
                approved_output,
            )
            .build()
        )

    storage = (
        FileCheckpointStorage(
            checkpoint_path,

            allowed_checkpoint_types=(
                _allowed_checkpoint_types()
            ),
        )
    )

    return (
        WorkflowBuilder(
            start_executor=executor,

            output_from=[
                executor,
                approved_output,
            ],

            name="procedure-runtime",

            checkpoint_storage=storage,
        )
        .add_edge(
            executor,
            approved_output,
        )
        .build()
    )