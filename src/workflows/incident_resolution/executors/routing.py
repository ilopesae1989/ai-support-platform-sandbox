from typing import Never

from agent_framework import (
    Executor,
    WorkflowContext,
    handler,
)

from src.runtime.procedure.identity import (
    create_workflow_id,
)

from src.workflows.incident_resolution.models import (
    ExecutionIdentity,
    KnowledgeReviewRequest,
    ManualAnalysisRequest,
    ProcedureExecutionInput,
    ProcedureExecutionRequest,
    TriagedAlertContext,
)

from src.workflows.incident_resolution.operational_context import (
    build_operational_context,
)

from src.workflows.incident_resolution.continuation_context import (
    ProcedureContinuationContext,
    store_procedure_continuation_context,
)


class ProcedureRequestExecutor(Executor):
    """
    Convierte un Triage exacto y elegible
    en ProcedureExecutionInput.

    Aquí nace workflow_id.

    Se genera mediante Python antes de Procedure v6.
    """

    def __init__(self) -> None:
        super().__init__(
            id="procedure_request"
        )

    @handler
    async def prepare_procedure_request(
        self,
        context: TriagedAlertContext,
        ctx: WorkflowContext[
            ProcedureExecutionInput
        ],
    ) -> None:
        triage = context.triage

        if (
            not triage.procedure_found
            or triage.procedure_match != "exact"
            or not triage.execution_eligible
            or triage.procedure is None
            or (
                triage.recommended_next_step
                != "procedure_execution"
            )
        ):
            raise ValueError(
                "El contexto no cumple los requisitos "
                "para Procedure Execution."
            )

        procedure = triage.procedure

        operational_context = (
            build_operational_context(
                context.alert
            )
        )

        execution_identity = ExecutionIdentity(
            workflow_id=(
                create_workflow_id()
            ),

            alert_id=(
                context.alert.alert_id
            ),

            correlation_id=(
                operational_context
                .correlation_id
            ),
        )

        request = ProcedureExecutionRequest(
            alert_id=(
                context.alert.alert_id
            ),

            procedure_found=(
                triage.procedure_found
            ),

            procedure_match=(
                triage.procedure_match
            ),

            execution_eligible=(
                triage.execution_eligible
            ),

            procedure_id=(
                procedure.id
            ),

            procedure_name=(
                procedure.name
            ),

            procedure_version=(
                procedure.version
            ),

            # El primer cursor del procedimiento
            # nace en Python.
            requested_step=1,

            affected_resource=(
                context.alert.affected_resource
                or triage.affected_resource
            ),

            incident_description=(
                context.alert.description
            ),
        )

        continuation_context = (
            ProcedureContinuationContext(
                request_affected_resource=(
                    request.affected_resource
                ),

                incident_description=(
                    request.incident_description
                ),

                procedure_found=(
                    request.procedure_found
                ),

                procedure_match=(
                    request.procedure_match
                ),

                execution_eligible=(
                    request.execution_eligible
                ),

                operational_affected_resource=(
                    operational_context
                    .affected_resource
                ),

                resource_type=(
                    operational_context
                    .resource_type
                ),

                service=(
                    operational_context
                    .service
                ),

                environment=(
                    operational_context
                    .environment
                ),

                incident_origin=(
                    operational_context
                    .incident_origin
                ),

                subscription_id=(
                    operational_context
                    .subscription_id
                ),

                resource_group=(
                    operational_context
                    .resource_group
                ),

                vm_name=(
                    operational_context
                    .vm_name
                ),

                tenant_id=(
                    operational_context
                    .tenant_id
                ),
            )
        )

        # El contexto necesario para un futuro N+1
        # debe quedar durable antes de emitir el
        # primer ProcedureExecutionInput.
        #
        # Si shared state falla, el workflow no
        # puede continuar de forma no durable.
        store_procedure_continuation_context(
            ctx,
            continuation_context,
        )

        await ctx.send_message(
            ProcedureExecutionInput(
                request=request,

                execution_identity=(
                    execution_identity
                ),

                operational_context=(
                    operational_context
                ),
            )
        )


class KnowledgeReviewExecutor(Executor):
    def __init__(self) -> None:
        super().__init__(
            id="knowledge_review"
        )

    @handler
    async def prepare_review(
        self,
        context: TriagedAlertContext,
        ctx: WorkflowContext[
            Never,
            KnowledgeReviewRequest,
        ],
    ) -> None:
        triage = context.triage

        if (
            triage.recommended_next_step
            != "knowledge_review"
        ):
            raise ValueError(
                "Knowledge Review requiere "
                "recommended_next_step="
                "knowledge_review."
            )

        if (
            triage.procedure_match
            not in {
                "exact",
                "partial",
            }
        ):
            raise ValueError(
                "Knowledge Review requiere "
                "procedure_match=partial o exact."
            )

        if triage.execution_eligible:
            raise ValueError(
                "Knowledge Review no acepta "
                "contextos elegibles para ejecución."
            )

        if (
            not triage.procedure_found
            or triage.procedure is None
        ):
            raise ValueError(
                "Knowledge Review requiere "
                "un procedimiento identificado."
            )

        procedure = triage.procedure

        if (
            triage.procedure_match
            == "partial"
        ):
            reason = (
                "partial_procedure_match"
            )

        else:
            reason = (
                "insufficient_knowledge"
            )

        request = KnowledgeReviewRequest(
            alert_id=(
                context.alert.alert_id
            ),

            reason=reason,

            procedure_id=(
                procedure.id
            ),

            procedure_name=(
                procedure.name
            ),

            procedure_version=(
                procedure.version
            ),

            affected_resource=(
                context.alert.affected_resource
                or triage.affected_resource
            ),

            missing_context=list(
                triage.missing_context
            ),
        )

        await ctx.yield_output(
            request
        )


class ManualAnalysisExecutor(Executor):
    def __init__(self) -> None:
        super().__init__(
            id="manual_analysis"
        )

    @handler
    async def prepare_manual_analysis(
        self,
        context: TriagedAlertContext,
        ctx: WorkflowContext[
            Never,
            ManualAnalysisRequest,
        ],
    ) -> None:
        triage = context.triage

        if (
            triage.procedure_match == "exact"
            and triage.execution_eligible
        ):
            raise ValueError(
                "El contexto no corresponde a "
                "Manual Analysis."
            )

        if (
            triage.recommended_next_step
            not in {
                "manual_analysis",
                "human_escalation",
            }
        ):
            raise ValueError(
                "El contexto no corresponde a "
                "Manual Analysis."
            )

        if (
            triage.recommended_next_step
            == "human_escalation"
        ):
            reason = (
                "human_escalation_required"
            )
        else:
            reason = (
                "no_procedure"
            )

        request = ManualAnalysisRequest(
            alert_id=(
                context.alert.alert_id
            ),

            reason=reason,

            technical_domain=(
                triage.technical_domain
            ),

            affected_resource=(
                context.alert.affected_resource
                or triage.affected_resource
            ),

            missing_context=list(
                triage.missing_context
            ),
        )

        await ctx.yield_output(
            request
        )
