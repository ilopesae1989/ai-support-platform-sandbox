from __future__ import annotations

from agent_framework import (
    Executor,
    WorkflowContext,
    handler,
)

from src.runtime.procedure.models import (
    ApprovedProcedureStep,
)

from ..azure_operations import (
    build_azure_operation_request,
)

from ..azure_operations_models import (
    VerifiedAzureOperationRequest,
)

from ..pre_call_security import (
    PreCallSecurityVerifier,
)


class AzurePreCallSecurityExecutor(Executor):
    """
    Frontera explícita entre HITL y Azure Operations.

    Entrada:

        ApprovedProcedureStep

    Salida:

        VerifiedAzureOperationRequest

    Si cualquier comprobación falla:

        no existe mensaje hacia AzureOperationsExecutor

    por tanto:

        Foundry calls = 0
        MCP calls = 0
    """

    def __init__(self) -> None:
        super().__init__(
            id="azure_pre_call_security"
        )

        self._verifier = (
            PreCallSecurityVerifier()
        )

    @handler
    async def handle(
        self,
        step: ApprovedProcedureStep,
        ctx: WorkflowContext[
            VerifiedAzureOperationRequest
        ],
    ) -> None:
        """
        Construye candidato y verifica exactamente
        contra el snapshot post-HITL.
        """

        candidate = (
            build_azure_operation_request(
                step
            )
        )

        verified_request = (
            self._verifier.verify(
                approved_step=step,
                candidate=candidate,
            )
        )

        await ctx.send_message(
            verified_request
        )