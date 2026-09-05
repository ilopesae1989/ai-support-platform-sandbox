from __future__ import annotations

from collections.abc import (
    Mapping,
)

from uuid import (
    uuid4,
)

from pydantic import (
    Field,
)

from src.runtime.procedure.models import (
    ApprovalStatus,
    NextAction,
    OperationAction,
    OperationKind,
    ProcedureRuntimeState,
    StepStatus,
    WorkflowStatus,
)

from src.runtime.procedure.runtime import (
    ProcedureRuntime,
    validate_procedure_iteration_budget,
)

from src.workflows.incident_resolution.immutable_snapshot import (
    ImmutableSnapshotModel,
)

from src.workflows.incident_resolution.operation_models import (
    OperationResult,
)

from src.workflows.incident_resolution.procedure_validation_models import (
    ProcedureValidationRequest,
    ProcedureValidationStep,
)


class WaitRecheckRequest(
    ImmutableSnapshotModel
):
    """
    Solicitud de señal externa NO operacional.

    No constituye:
    - aprobación;
    - autorización;
    - dispatch;
    - resultado operacional.
    """

    recheck_id: str = Field(
        min_length=1
    )

    workflow_id: str = Field(
        min_length=1
    )

    alert_id: str = Field(
        min_length=1
    )

    correlation_id: str | None = None
    conversation_id: str | None = None

    procedure_id: str = Field(
        min_length=1
    )

    procedure_version: str | None = None

    current_step: int = Field(
        ge=1
    )

    step_id: str = Field(
        min_length=1
    )

    operation_id: str = Field(
        min_length=1
    )

    target_resource: str = Field(
        min_length=1
    )

    recheck_count: int = Field(
        ge=1
    )


class WaitRecheckSignal(
    ImmutableSnapshotModel
):
    """
    Señal externa que autoriza exclusivamente
    volver a observar y validar.

    No autoriza ninguna operación.
    """

    recheck_id: str = Field(
        min_length=1
    )


def create_wait_recheck_id() -> str:
    return (
        "rchk-"
        + str(
            uuid4()
        )
    )


def _revalidate_state(
    state: ProcedureRuntimeState,
) -> ProcedureRuntimeState:
    return (
        ProcedureRuntimeState
        .model_validate(
            state.model_dump(
                mode="python"
            )
        )
    )


def _load_registered_operation_result(
    state: ProcedureRuntimeState,
) -> OperationResult:
    evidence = state.operation_result

    if evidence is None:
        raise ValueError(
            "WAIT recheck requiere "
            "operation_result registrado."
        )

    if not isinstance(
        evidence.result,
        Mapping,
    ):
        raise ValueError(
            "operation_result registrado "
            "no contiene OperationResult."
        )

    try:
        result = (
            OperationResult
            .model_validate(
                evidence.result
            )
        )

    except Exception as exc:
        raise ValueError(
            "OperationResult registrado "
            "no supera revalidación."
        ) from exc

    if (
        evidence.success
        != result.success
    ):
        raise ValueError(
            "OperationResult registrado "
            "contiene success inconsistente."
        )

    if (
        evidence.error
        != result.error
    ):
        raise ValueError(
            "OperationResult registrado "
            "contiene error inconsistente."
        )

    return result


def _validate_wait_state(
    state: ProcedureRuntimeState,
) -> OperationResult:
    if (
        state.step_status
        != StepStatus.WAITING_VALIDATION
        or state.workflow_status
        != WorkflowStatus.WAITING_VALIDATION
    ):
        raise ValueError(
            "WAIT recheck requiere "
            "waiting_validation."
        )

    if (
        state.approval_status
        != ApprovalStatus.APPROVED
    ):
        raise ValueError(
            "WAIT VM recheck requiere que "
            "la operación original estuviera "
            "aprobada."
        )

    if not state.approval_id:
        raise ValueError(
            "WAIT VM recheck no dispone de "
            "identidad histórica de aprobación."
        )

    if (
        state.verification_result
        is None
    ):
        raise ValueError(
            "WAIT recheck requiere una "
            "validación WAIT previa."
        )

    result = (
        _load_registered_operation_result(
            state
        )
    )

    if (
        result.operation_domain
        != "azure"
        or result.operation_kind
        != OperationKind.WRITE
        or result.operation_action
        != OperationAction.VM_START
        or result.capability_id
        != "azure.vm.start"
        or result.hitl_required
        is not True
    ):
        raise ValueError(
            "WAIT recheck core sólo está "
            "autorizado para azure.vm.start."
        )

    if (
        result.success
        is not True
        or result.technical_success
        is not True
    ):
        raise ValueError(
            "WAIT recheck requiere un WRITE "
            "técnicamente exitoso antes de "
            "observar estado."
        )

    comparisons = {
        "workflow_id": (
            result.workflow_id,
            state.workflow_id,
        ),
        "approval_id": (
            result.approval_id,
            state.approval_id,
        ),
        "alert_id": (
            result.alert_id,
            state.alert_id,
        ),
        "correlation_id": (
            result.correlation_id,
            state.correlation_id,
        ),
        "conversation_id": (
            result.conversation_id,
            state.conversation_id,
        ),
        "procedure_id": (
            result.procedure_id,
            state.procedure.id,
        ),
        "procedure_version": (
            result.procedure_version,
            state.procedure.version,
        ),
        "current_step": (
            result.current_step,
            state.current_step,
        ),
        "step_id": (
            result.step_id,
            state.step.id,
        ),
        "operation_domain": (
            result.operation_domain,
            state.step.operation_domain,
        ),
        "operation_kind": (
            result.operation_kind,
            state.step.operation_kind,
        ),
        "operation_action": (
            result.operation_action,
            state.step.operation_action,
        ),
        "capability_id": (
            result.capability_id,
            state.step.capability_id,
        ),
        "hitl_required": (
            result.hitl_required,
            state.step.hitl_required,
        ),
        "target_resource": (
            result.target_resource,
            state.step.target_resource,
        ),
        "required_parameters": (
            list(
                result.required_parameters
            ),
            list(
                state.step
                .required_parameters
            ),
        ),
    }

    changed = [
        name
        for name, values
        in comparisons.items()
        if values[0] != values[1]
    ]

    runtime_resolved = [
        item.model_dump(
            mode="json"
        )
        for item
        in state.resolved_parameters
    ]

    result_resolved = [
        item.model_dump(
            mode="json"
        )
        for item
        in result.resolved_parameters
    ]

    if (
        runtime_resolved
        != result_resolved
    ):
        changed.append(
            "resolved_parameters"
        )

    if (
        result.next_action
        != NextAction.EXECUTE_STEP
    ):
        changed.append(
            "next_action"
        )

    if changed:
        raise ValueError(
            "WAIT recheck OperationResult "
            "no corresponde al runtime: "
            + ", ".join(
                changed
            )
        )

    return result


def _build_request(
    *,
    state: ProcedureRuntimeState,
    recheck_id: str,
) -> WaitRecheckRequest:
    result = (
        _validate_wait_state(
            state
        )
    )

    next_recheck_count = (
        state.recheck_count + 1
    )

    validate_procedure_iteration_budget(
        total_steps=state.total_steps,
        retry_count=state.retry_count,
        recheck_count=next_recheck_count,
    )

    if not result.target_resource:
        raise ValueError(
            "WAIT recheck requiere "
            "target_resource."
        )

    return WaitRecheckRequest(
        recheck_id=recheck_id,
        workflow_id=state.workflow_id,
        alert_id=state.alert_id,
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
        step_id=state.step.id,
        operation_id=(
            result.operation_id
        ),
        target_resource=(
            result.target_resource
        ),
        recheck_count=(
            next_recheck_count
        ),
    )


def build_wait_recheck_request(
    state: ProcedureRuntimeState,
) -> WaitRecheckRequest:
    trusted_state = (
        _revalidate_state(
            state
        )
    )

    return _build_request(
        state=trusted_state,
        recheck_id=(
            create_wait_recheck_id()
        ),
    )


def _build_validation_request(
    state: ProcedureRuntimeState,
) -> ProcedureValidationRequest:
    result = (
        _load_registered_operation_result(
            state
        )
    )

    return ProcedureValidationRequest(
        operation_result=result,
        step=ProcedureValidationStep(
            procedure_id=(
                state.procedure.id
            ),
            procedure_version=(
                state.procedure.version
            ),
            current_step=(
                state.current_step
            ),
            step_id=state.step.id,
            description=(
                state.step.description
            ),
            expected_result=(
                state.step.expected_result
            ),
            verification=(
                state.step.verification
            ),
        ),
    )


def consume_wait_recheck_signal(
    *,
    state: ProcedureRuntimeState,
    original_request: WaitRecheckRequest,
    signal: WaitRecheckSignal,
) -> tuple[
    ProcedureRuntimeState,
    ProcedureValidationRequest,
]:
    trusted_state = (
        _revalidate_state(
            state
        )
    )

    trusted_request = (
        WaitRecheckRequest
        .model_validate(
            original_request.model_dump(
                mode="python"
            )
        )
    )

    trusted_signal = (
        WaitRecheckSignal
        .model_validate(
            signal.model_dump(
                mode="python"
            )
        )
    )

    if (
        trusted_signal.recheck_id
        != trusted_request.recheck_id
    ):
        raise ValueError(
            "WaitRecheckSignal no corresponde "
            "a WaitRecheckRequest."
        )

    expected_request = (
        _build_request(
            state=trusted_state,
            recheck_id=(
                trusted_request
                .recheck_id
            ),
        )
    )

    if (
        trusted_request
        != expected_request
    ):
        raise ValueError(
            "WaitRecheckRequest no corresponde "
            "al runtime autoritativo."
        )

    runtime = ProcedureRuntime()

    trusted_state = (
        runtime.prepare_wait_recheck(
            trusted_state
        )
    )

    validation_request = (
        _build_validation_request(
            trusted_state
        )
    )

    return (
        trusted_state,
        validation_request,
    )
