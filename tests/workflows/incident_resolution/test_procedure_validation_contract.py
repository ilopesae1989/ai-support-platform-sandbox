from importlib import (
    import_module,
)

import pytest

from pydantic import (
    ValidationError,
)

from src.runtime.procedure.models import (
    NextAction,
    OperationKind,
    ResolvedParameter,
)

from src.workflows.incident_resolution.operation_evidence import (
    OperationEvidence,
)

from src.workflows.incident_resolution.operation_models import (
    OperationResult,
)


OPERATION_ID = (
    "op-procedure-validation-001"
)

WORKFLOW_ID = (
    "wf-procedure-validation-001"
)

APPROVAL_ID = (
    "apr-procedure-validation-001"
)

ALERT_ID = (
    "ALT-PROCEDURE-VALIDATION-001"
)

CORRELATION_ID = (
    "corr-procedure-validation-001"
)

CONVERSATION_ID = (
    "conv-procedure-validation-001"
)

PROCEDURE_ID = (
    "NTTSY-SBX-AZ-001"
)

PROCEDURE_VERSION = (
    "v1.0"
)

CURRENT_STEP = 1
STEP_ID = "1"

SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
)


def get_validation_models():
    return import_module(
        "src.workflows."
        "incident_resolution."
        "procedure_validation_models"
    )


def get_validation_contracts():
    contracts = import_module(
        "src.agents.contracts"
    )

    return (
        getattr(
            contracts,
            "ProcedureValidationEscalation",
        ),
        getattr(
            contracts,
            "ProcedureValidationResult",
        ),
    )


def create_resolved_parameters():
    return [
        ResolvedParameter(
            name="subscription_id",

            value=(
                SUBSCRIPTION_ID
            ),

            source=(
                "normalized_alert."
                "subscription_id"
            ),
        )
    ]


def create_operation_evidence():
    return OperationEvidence(
        operation_id=(
            OPERATION_ID
        ),

        workflow_id=(
            WORKFLOW_ID
        ),

        approval_id=(
            APPROVAL_ID
        ),

        alert_id=(
            ALERT_ID
        ),

        correlation_id=(
            CORRELATION_ID
        ),

        conversation_id=(
            CONVERSATION_ID
        ),

        procedure_id=(
            PROCEDURE_ID
        ),

        procedure_version=(
            PROCEDURE_VERSION
        ),

        current_step=(
            CURRENT_STEP
        ),

        step_id=(
            STEP_ID
        ),

        operation_domain="azure",

        operation_kind=(
            OperationKind.READ
        ),

        next_action=(
            NextAction.EXECUTE_STEP
        ),

        target_resource=(
            "subscription"
        ),

        required_parameters=[
            "subscription_id",
        ],

        resolved_parameters=(
            create_resolved_parameters()
        ),
    )


def create_operation_result(
    *,
    success=True,
    include_evidence=True,
):
    evidence = (
        create_operation_evidence()
        if include_evidence
        else None
    )

    return OperationResult(
        operation_id=(
            OPERATION_ID
        ),

        workflow_id=(
            WORKFLOW_ID
        ),

        approval_id=(
            APPROVAL_ID
        ),

        alert_id=(
            ALERT_ID
        ),

        correlation_id=(
            CORRELATION_ID
        ),

        conversation_id=(
            CONVERSATION_ID
        ),

        procedure_id=(
            PROCEDURE_ID
        ),

        procedure_version=(
            PROCEDURE_VERSION
        ),

        current_step=(
            CURRENT_STEP
        ),

        step_id=(
            STEP_ID
        ),

        operation_domain="azure",

        operation_kind=(
            OperationKind.READ
        ),

        next_action=(
            NextAction.EXECUTE_STEP
        ),

        target_resource=(
            "subscription"
        ),

        required_parameters=[
            "subscription_id",
        ],

        resolved_parameters=(
            create_resolved_parameters()
        ),

        success=success,

        technical_success=(
            evidence.derive_technical_success()
            if evidence is not None
            else (
                None
                if success
                else False
            )
        ),

        response_text=(
            "Azure operation fake result."
            if success
            else None
        ),

        error=(
            None
            if success
            else "RuntimeError: fake backend failure"
        ),

        evidence=evidence,
    )


def create_validation_step(
    **updates,
):
    module = (
        get_validation_models()
    )

    payload = {
        "procedure_id": (
            PROCEDURE_ID
        ),

        "procedure_version": (
            PROCEDURE_VERSION
        ),

        "current_step": (
            CURRENT_STEP
        ),

        "step_id": (
            STEP_ID
        ),

        "description": (
            "Consultar Resource Groups "
            "de la suscripción."
        ),

        "expected_result": (
            "Lista de Resource Groups."
        ),

        "verification": (
            "Validar que el resultado "
            "corresponde a la suscripción."
        ),
    }

    payload.update(
        updates
    )

    return (
        module.ProcedureValidationStep(
            **payload
        )
    )


def create_validation_request(
    *,
    operation_result=None,
    step=None,
):
    module = (
        get_validation_models()
    )

    return (
        module.ProcedureValidationRequest(
            operation_result=(
                operation_result
                or create_operation_result()
            ),

            step=(
                step
                or create_validation_step()
            ),
        )
    )


def create_validation_result(
    *,
    operation_id=OPERATION_ID,
    validation_status="satisfied",
    proposed_next_action="continue",
    validation_summary=(
        "El resultado satisface "
        "la verificación del paso."
    ),
    escalation_required=False,
    escalation_team=None,
    escalation_level=None,
    escalation_criteria=None,
):
    (
        escalation_type,
        result_type,
    ) = get_validation_contracts()

    return result_type(
        operation_id=(
            operation_id
        ),

        validation_status=(
            validation_status
        ),

        proposed_next_action=(
            proposed_next_action
        ),

        validation_summary=(
            validation_summary
        ),

        escalation=(
            escalation_type(
                required=(
                    escalation_required
                ),

                team=(
                    escalation_team
                ),

                level=(
                    escalation_level
                ),

                criteria=(
                    escalation_criteria
                ),
            )
        ),
    )


def test_validation_step_contract_is_minimal():
    module = (
        get_validation_models()
    )

    assert tuple(
        module
        .ProcedureValidationStep
        .model_fields
    ) == (
        "procedure_id",
        "procedure_version",
        "current_step",
        "step_id",
        "description",
        "expected_result",
        "verification",
    )


def test_validation_request_uses_common_operation_result_without_duplicate_evidence():
    module = (
        get_validation_models()
    )

    request_type = (
        module
        .ProcedureValidationRequest
    )

    assert tuple(
        request_type.model_fields
    ) == (
        "operation_result",
        "step",
        "post_operation_observation",
    )

    assert (
        request_type
        .model_fields[
            "operation_result"
        ]
        .annotation
        is OperationResult
    )

    assert (
        "evidence"
        not in request_type.model_fields
    )

    request = (
        create_validation_request()
    )

    assert (
        request
        .operation_result
        .evidence
        is not None
    )

    assert (
        request
        .post_operation_observation
        is None
    )


@pytest.mark.parametrize(
    (
        "field_name",
        "wrong_value",
    ),
    [
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
    ],
)
def test_validation_request_rejects_step_identity_mismatch(
    field_name,
    wrong_value,
):
    step = (
        create_validation_step(
            **{
                field_name:
                    wrong_value
            }
        )
    )

    with pytest.raises(
        ValidationError,
    ):
        create_validation_request(
            step=step
        )


def test_validation_request_preserves_indeterminate_technical_success():
    operation_result = (
        create_operation_result(
            success=True,
            include_evidence=True,
        )
    )

    assert (
        operation_result
        .technical_success
        is None
    )

    request = (
        create_validation_request(
            operation_result=(
                operation_result
            )
        )
    )

    assert (
        request
        .operation_result
        .technical_success
        is None
    )

    assert (
        request
        .operation_result
        .success
        is True
    )


def test_validation_request_accepts_backend_failure_without_evidence():
    operation_result = (
        create_operation_result(
            success=False,
            include_evidence=False,
        )
    )

    request = (
        create_validation_request(
            operation_result=(
                operation_result
            )
        )
    )

    assert (
        request
        .operation_result
        .success
        is False
    )

    assert (
        request
        .operation_result
        .technical_success
        is False
    )

    assert (
        request
        .operation_result
        .evidence
        is None
    )


def test_validation_result_has_no_state_or_operational_authority():
    (
        _,
        result_type,
    ) = get_validation_contracts()

    assert tuple(
        result_type.model_fields
    ) == (
        "operation_id",
        "validation_status",
        "proposed_next_action",
        "validation_summary",
        "escalation",
    )

    forbidden = {
        "workflow_status",
        "step_status",
        "approval_status",
        "target_resource",
        "resolved_parameters",
        "success",
        "technical_success",
    }

    assert forbidden.isdisjoint(
        result_type.model_fields
    )


def test_validation_result_cannot_propose_execute_step():
    with pytest.raises(
        ValidationError,
    ):
        create_validation_result(
            proposed_next_action=(
                "execute_step"
            )
        )


def test_validation_result_escalate_requires_escalation():
    with pytest.raises(
        ValidationError,
    ):
        create_validation_result(
            validation_status=(
                "not_satisfied"
            ),

            proposed_next_action=(
                "escalate"
            ),

            escalation_required=False,
        )


def test_validation_result_non_escalate_cannot_claim_escalation():
    with pytest.raises(
        ValidationError,
    ):
        create_validation_result(
            proposed_next_action=(
                "continue"
            ),

            escalation_required=True,

            escalation_team=(
                "cloud"
            ),
        )


def test_validation_context_correlates_operation_id():
    module = (
        get_validation_models()
    )

    request = (
        create_validation_request()
    )

    result = (
        create_validation_result()
    )

    context = (
        module.ProcedureValidationContext(
            request=request,
            result=result,
        )
    )

    assert (
        context
        .result
        .operation_id
        ==
        context
        .request
        .operation_result
        .operation_id
    )


def test_validation_context_rejects_result_for_other_operation():
    module = (
        get_validation_models()
    )

    request = (
        create_validation_request()
    )

    result = (
        create_validation_result(
            operation_id=(
                "op-other-operation"
            )
        )
    )

    with pytest.raises(
        ValidationError,
    ):
        module.ProcedureValidationContext(
            request=request,
            result=result,
        )


def test_validation_contracts_are_immutable_after_creation():
    request = (
        create_validation_request()
    )

    result = (
        create_validation_result()
    )

    with pytest.raises(
        ValidationError,
    ):
        request.step = (
            create_validation_step()
        )

    with pytest.raises(
        ValidationError,
    ):
        result.validation_summary = (
            "tampered"
        )

    with pytest.raises(
        ValidationError,
    ):
        result.escalation.team = (
            "attacker"
        )


def test_validation_request_disallows_model_copy_update():
    request = (
        create_validation_request()
    )

    with pytest.raises(
        TypeError,
    ):
        request.model_copy(
            update={
                "step": (
                    create_validation_step(
                        step_id="attacker"
                    )
                )
            }
        )
