from dataclasses import dataclass

from agent_framework import (
    Executor,
    FileCheckpointStorage,
    WorkflowBuilder,
    WorkflowContext,
    handler,
    response_handler,
)

from .models import ProcedureRuntimeState
from .runtime import ProcedureRuntime


@dataclass
class ApprovalRequest:
    workflow_id: str
    alert_id: str
    procedure_id: str
    current_step: int
    description: str
    operation_domain: str
    operation_kind: str
    target_resource: str | None


@dataclass
class ApprovalOutcome:
    workflow_id: str
    approved: bool
    status: str


class ProcedureApprovalExecutor(Executor):
    """
    Executor HITL determinista.

    Responsabilidades:
    - aplicar la política del ProcedureRuntime;
    - emitir una solicitud de aprobación;
    - recibir la decisión externa;
    - actualizar el estado mediante ProcedureRuntime.

    No interpreta procedimientos.
    No decide si una operación está permitida mediante LLM.
    No llama a MCP.
    No llama a Foundry.
    No ejecuta operaciones técnicas.
    """

    def __init__(self) -> None:
        super().__init__(id="procedure_approval")

        self._runtime = ProcedureRuntime()

        # Estado temporal de esta primera implementación.
        # Posteriormente se persiste y recupera mediante
        # checkpoints del workflow.
        self._pending_state: ProcedureRuntimeState | None = None

    @handler
    async def prepare_step(
        self,
        state: ProcedureRuntimeState,
        ctx: WorkflowContext[None, ApprovalOutcome],
    ) -> None:
        """
        Recibe el estado preparado a partir de la salida del
        Procedure Execution Agent y aplica exclusivamente
        la política determinista del runtime.
        """

        state = self._runtime.prepare_current_step(state)

        if state.step_status.value == "waiting_approval":
            self._pending_state = state

            request = ApprovalRequest(
                workflow_id=state.workflow_id,
                alert_id=state.alert_id,
                procedure_id=state.procedure.id,
                current_step=state.current_step,
                description=state.step.description,
                operation_domain=state.step.operation_domain,
                operation_kind=state.step.operation_kind.value,
                target_resource=state.step.target_resource,
            )

            await ctx.request_info(
                request_data=request,
                response_type=bool,
            )

            return

        # Si la política del runtime determina que el paso
        # no necesita aprobación, el workflow puede continuar.
        await ctx.yield_output(
            ApprovalOutcome(
                workflow_id=state.workflow_id,
                approved=True,
                status=state.workflow_status.value,
            )
        )

    @response_handler
    async def handle_approval_response(
        self,
        original_request: ApprovalRequest,
        response: bool,
        ctx: WorkflowContext[None, ApprovalOutcome],
    ) -> None:
        """
        Recibe exclusivamente una decisión ya resuelta
        por la capa externa: True o False.

        No interpreta lenguaje natural.
        No deduce una aprobación.
        """

        if self._pending_state is None:
            raise RuntimeError(
                "Se recibió una respuesta de aprobación "
                "sin estado pendiente."
            )

        if (
            self._pending_state.workflow_id
            != original_request.workflow_id
        ):
            raise RuntimeError(
                "La aprobación recibida no corresponde "
                "al workflow pendiente."
            )

        state = self._runtime.register_approval(
            self._pending_state,
            approved=response,
        )

        self._pending_state = None

        await ctx.yield_output(
            ApprovalOutcome(
                workflow_id=state.workflow_id,
                approved=response,
                status=state.workflow_status.value,
            )
        )

    async def on_checkpoint_save(self) -> dict:
        """
        Persiste únicamente el estado mínimo necesario
        para poder restaurar una aprobación pendiente.
        """

        if self._pending_state is None:
            return {
                "pending_state": None,
            }

        return {
            "pending_state": self._pending_state.model_dump(
                mode="json"
            ),
        }

    async def on_checkpoint_restore(
        self,
        state: dict,
    ) -> None:
        """
        Restaura el estado del runtime tras recuperar
        un checkpoint del workflow.
        """

        pending_state = state.get("pending_state")

        if pending_state is None:
            self._pending_state = None
            return

        self._pending_state = (
            ProcedureRuntimeState.model_validate(
                pending_state
            )
        )


def build_procedure_approval_workflow(
    checkpoint_path: str | None = None,
):
    executor = ProcedureApprovalExecutor()

    if checkpoint_path is None:
        return WorkflowBuilder(
            start_executor=executor,
            output_from=[executor],
            name="procedure-runtime",
        ).build()

    storage = FileCheckpointStorage(
        checkpoint_path,
        allowed_checkpoint_types={
             "src.runtime.procedure.workflow:ApprovalRequest",
             "src.runtime.procedure.workflow:ApprovalOutcome",
             },
    )

    return WorkflowBuilder(
        start_executor=executor,
        output_from=[executor],
        name="procedure-runtime",
        checkpoint_storage=storage,
    ).build()