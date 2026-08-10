from importlib import (
    import_module,
)

import pytest

from src.runtime.procedure.identity import (
    create_operation_id,
)

from src.runtime.procedure.models import (
    ApprovalStatus,
    NextAction,
    OperationKind,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
    ResolvedParameter,
    StepEvidence,
    StepStatus,
    WorkflowStatus,
)

from src.workflows.incident_resolution.operation_evidence import (
    OperationEvidence,
)

from src.workflows.incident_resolution.operation_models import (
    OperationResult,
)


WORKFLOW_ID = (
    "wf-11111111-1111-4111-"
    "8111-111111111111"
)

APPROVAL_ID = (
    "apr-11111111-1111-4111-"
    "8111-111111111111"
)

ALERT_ID = (
    "ALT-AZ-RG-LIST-001"
)

CORRELATION_ID = (
    "corr-result-runtime-001"
)

CONVERSATION_ID = (
    "conv-result-runtime-001"
)

PROCEDURE_ID = (
    "NTTSY-SBX-AZ-001"
)

PROCEDURE_VERSION = "v1.0"

SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
)


def get_validator():
    module = import_module(
        "src.workflows."
        "incident_resolution."
        "operation_result_correlation"
    )

    return (
        module
        .validate_operation_result_against_runtime
    )


def resolved_parameters(
    *,
    value=SUBSCRIPTION_ID,
    source=(
        "normalized_alert."
        "subscription_id"
    ),
):
    return [
        ResolvedParameter(
            name="subscription_id",
            value=value,
            source=source,
        )
    ]


def create_runtime_state(
    *,
    approval_id=APPROVAL_ID,
    step_status=StepStatus.RUNNING,
    workflow_status=(
        WorkflowStatus.WAITING_OPERATION
    ),
    approval_status=(
        ApprovalStatus.APPROVED
    ),
    operation_result=None,
):
    return ProcedureRuntimeState(
        workflow_id=WORKFLOW_ID,

        approval_id=approval_id,

        alert_id=ALERT_ID,

        correlation_id=(
            CORRELATION_ID
        ),

        conversation_id=(
            CONVERSATION_ID
        ),

        procedure=ProcedureReference(
            id=PROCEDURE_ID,

            name=(
                "Consulta de Resource Groups"
            ),

            version=(
                PROCEDURE_VERSION
            ),
        ),

        total_steps=1,
        current_step=1,

        step=ProcedureStep(
            id="1",

            description=(
                "Consultar Resource Groups."
            ),

            step_type=(
                "technical_operation"
            ),

            operation_domain="azure",

            operation_kind=(
                OperationKind.READ
            ),

            target_resource=(
                "subscription"
            ),

            required_parameters=[
                "subscription_id",
            ],

            expected_result=(
                "Lista de Resource Groups."
            ),

            verification=(
                "Validar Resource Groups devueltos."
            ),
        ),

        resolved_parameters=(
            resolved_parameters()
        ),

        workflow_status=(
            workflow_status
        ),

        step_status=(
            step_status
        ),

        approval_status=(
            approval_status
        ),

        operation_result=(
            operation_result
        ),
    )


def create_result(
    *,
    updates=None,
    include_evidence=True,
    success=True,
):
    data = {
        "workflow_id": WORKFLOW_ID,
        "approval_id": APPROVAL_ID,
        "alert_id": ALERT_ID,

        "correlation_id": (
            CORRELATION_ID
        ),

        "conversation_id": (
            CONVERSATION_ID
        ),

        "procedure_id": (
            PROCEDURE_ID
        ),

        "procedure_version": (
            PROCEDURE_VERSION
        ),

        "current_step": 1,
        "step_id": "1",

        "operation_domain": "azure",

        "operation_kind": (
            OperationKind.READ
        ),

        "next_action": (
            NextAction.EXECUTE_STEP
        ),

        "target_resource": (
            "subscription"
        ),

        "required_parameters": [
            "subscription_id",
        ],

        "resolved_parameters": (
            resolved_parameters()
        ),
    }

    if updates:
        data.update(
            updates
        )

    operation_id = (
        data.get(
            "operation_id"
        )
    )

    if operation_id is None:
        operation_id = (
            create_operation_id(
                workflow_id=(
                    data["workflow_id"]
                ),

                approval_id=(
                    data["approval_id"]
                ),

                alert_id=(
                    data["alert_id"]
                ),

                procedure_id=(
                    data["procedure_id"]
                ),

                current_step=(
                    data["current_step"]
                ),

                step_id=(
                    data["step_id"]
                ),
            )
        )

    data["operation_id"] = (
        operation_id
    )

    evidence = None

    if include_evidence:
        evidence = OperationEvidence(
            **data
        )

    technical_success = (
        evidence.derive_technical_success()
        if evidence is not None
        else (
            None
            if success
            else False
        )
    )

    return OperationResult(
        **data,

        success=success,

        technical_success=(
            technical_success
        ),

        response_text=(
            "fake operation result"
            if success
            else None
        ),

        error=(
            None
            if success
            else "RuntimeError: fake failure"
        ),

        evidence=evidence,
    )


def test_matching_result_is_accepted_without_mutation():
    state = (
        create_runtime_state()
    )

    result = (
        create_result()
    )

    state_before = (
        state.model_dump(
            mode="python"
        )
    )

    result_before = (
        result.model_dump(
            mode="python"
        )
    )

    validator = (
        get_validator()
    )

    assert (
        validator(
            result,
            state,
        )
        is None
    )

    assert (
        state.model_dump(
            mode="python"
        )
        == state_before
    )

    assert (
        result.model_dump(
            mode="python"
        )
        == result_before
    )


@pytest.mark.parametrize(
    (
        "field_name",
        "wrong_value",
    ),
    [
        (
            "workflow_id",
            "wf-other",
        ),
        (
            "approval_id",
            "apr-other",
        ),
        (
            "alert_id",
            "ALT-OTHER",
        ),
        (
            "correlation_id",
            "corr-other",
        ),
        (
            "conversation_id",
            "conv-other",
        ),
        (
            "procedure_id",
            "OTHER-PROCEDURE",
        ),
        (
            "procedure_version",
            "v999",
        ),
        (
            "current_step",
            2,
        ),
        (
            "step_id",
            "999",
        ),
        (
            "operation_domain",
            "database",
        ),
        (
            "operation_kind",
            OperationKind.WRITE,
        ),
        (
            "next_action",
            NextAction.CONTINUE,
        ),
        (
            "target_resource",
            "other-resource",
        ),
        (
            "required_parameters",
            [
                "tenant_id",
            ],
        ),
        (
            "resolved_parameters",
            resolved_parameters(
                value="sub-attacker"
            ),
        ),
        (
            "operation_id",
            "op-attacker",
        ),
    ],
)
def test_result_for_different_operation_is_rejected(
    field_name,
    wrong_value,
):
    state = (
        create_runtime_state()
    )

    result = (
        create_result(
            updates={
                field_name:
                    wrong_value
            }
        )
    )

    validator = (
        get_validator()
    )

    with pytest.raises(
        ValueError,
    ):
        validator(
            result,
            state,
        )


@pytest.mark.parametrize(
    (
        "step_status",
        "workflow_status",
        "approval_status",
    ),
    [
        (
            StepStatus.APPROVED,
            WorkflowStatus.RUNNING,
            ApprovalStatus.APPROVED,
        ),
        (
            StepStatus.RUNNING,
            WorkflowStatus.RUNNING,
            ApprovalStatus.APPROVED,
        ),
        (
            StepStatus.RUNNING,
            WorkflowStatus.WAITING_OPERATION,
            ApprovalStatus.PENDING,
        ),
        (
            StepStatus.WAITING_VALIDATION,
            WorkflowStatus.WAITING_VALIDATION,
            ApprovalStatus.APPROVED,
        ),
    ],
)
def test_result_is_rejected_when_runtime_is_not_waiting_for_operation(
    step_status,
    workflow_status,
    approval_status,
):
    state = create_runtime_state(
        step_status=(
            step_status
        ),

        workflow_status=(
            workflow_status
        ),

        approval_status=(
            approval_status
        ),
    )

    result = (
        create_result()
    )

    with pytest.raises(
        ValueError,
    ):
        get_validator()(
            result,
            state,
        )


def test_result_is_rejected_when_runtime_has_no_approval_id():
    state = (
        create_runtime_state(
            approval_id=None
        )
    )

    result = (
        create_result()
    )

    with pytest.raises(
        ValueError,
    ):
        get_validator()(
            result,
            state,
        )


def test_duplicate_or_stale_result_is_rejected_after_result_already_registered():
    state = (
        create_runtime_state(
            step_status=(
                StepStatus.WAITING_VALIDATION
            ),

            workflow_status=(
                WorkflowStatus.WAITING_VALIDATION
            ),

            operation_result=(
                StepEvidence(
                    success=True,

                    result=(
                        "already registered"
                    ),
                )
            ),
        )
    )

    result = (
        create_result()
    )

    with pytest.raises(
        ValueError,
    ):
        get_validator()(
            result,
            state,
        )


def test_backend_failure_can_still_be_correctly_correlated():
    state = (
        create_runtime_state()
    )

    result = (
        create_result(
            include_evidence=False,
            success=False,
        )
    )

    assert result.success is False

    assert (
        result.technical_success
        is False
    )

    assert (
        get_validator()(
            result,
            state,
        )
        is None
    )


def test_indeterminate_technical_success_can_still_be_correlated():
    state = (
        create_runtime_state()
    )

    result = (
        create_result(
            include_evidence=True,
            success=True,
        )
    )

    assert (
        result.technical_success
        is None
    )

    assert (
        get_validator()(
            result,
            state,
        )
        is None
    )


def test_tampered_internal_evidence_is_revalidated_and_rejected():
    state = (
        create_runtime_state()
    )

    valid_result = (
        create_result()
    )

    assert (
        valid_result.evidence
        is not None
    )

    tampered_evidence_payload = (
        valid_result
        .evidence
        .model_dump(
            mode="python"
        )
    )

    tampered_evidence_payload[
        "target_resource"
    ] = "attacker-resource"

    tampered_evidence = (
        OperationEvidence(
            **tampered_evidence_payload
        )
    )

    # Conservamos los objetos tipados reales del
    # OperationResult y sustituimos únicamente
    # la evidencia para simular el bypass.
    payload = {
        field_name: getattr(
            valid_result,
            field_name,
        )
        for field_name
        in OperationResult.model_fields
    }

    payload[
        "evidence"
    ] = tampered_evidence

    # model_construct se usa deliberadamente
    # para simular un objeto que ha evitado
    # validación Pydantic normal.
    tampered_result = (
        OperationResult.model_construct(
            **payload
        )
    )

    with pytest.raises(
        ValueError,
    ):
        get_validator()(
            tampered_result,
            state,
        )
