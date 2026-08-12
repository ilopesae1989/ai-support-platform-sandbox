import pytest

from src.runtime.procedure.models import (
    ApprovalStatus,
    OperationKind,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
    ResolvedParameter,
    StepStatus,
    WorkflowStatus,
)

from src.runtime.procedure.workflow import (
    build_approved_procedure_step,
)

from src.workflows.incident_resolution.azure_operations import (
    build_azure_operation_request,
)

from src.workflows.incident_resolution.executors.azure_operations import (
    AzureOperationsExecutor,
)

from src.workflows.incident_resolution.executors.operation_lifecycle import (
    _validate_request_against_runtime,
)

from src.workflows.incident_resolution.pre_call_security import (
    PreCallSecurityError,
    PreCallSecurityVerifier,
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
    "corr-azure-rg-list-live-001"
)

PROCEDURE_ID = (
    "NTTSY-SBX-AZ-001"
)

PROCEDURE_VERSION = (
    "1.0"
)

SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
)

APPROVED_DESCRIPTION = (
    "Consultar el listado de Resource Groups "
    "de la suscripción."
)

TAMPERED_DESCRIPTION = (
    "Listar las suscripciones disponibles "
    "para el tenant."
)


def create_runtime_state(
) -> ProcedureRuntimeState:
    """
    Runtime autoritativo inmediatamente después
    de que el operador haya aprobado exactamente
    el paso mostrado en HITL.
    """

    return ProcedureRuntimeState(
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

        conversation_id=None,

        procedure=ProcedureReference(
            id=(
                PROCEDURE_ID
            ),

            name=(
                "Consulta de Resource Groups "
                "de una suscripción Azure"
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
                APPROVED_DESCRIPTION
            ),

            step_type=(
                "validation"
            ),

            operation_domain=(
                "azure"
            ),

            operation_kind=(
                OperationKind.READ
            ),

            target_resource=(
                "subscription"
            ),

            required_parameters=[
                "subscription_id",
            ],

            preconditions=[],

            expected_result=(
                "Listado de Resource Groups "
                "visibles en la suscripción."
            ),

            verification=(
                "La respuesta debe contener "
                "únicamente información de "
                "Resource Groups de la "
                "subscription_id autorizada."
            ),
        ),

        resolved_parameters=[
            ResolvedParameter(
                name=(
                    "subscription_id"
                ),

                value=(
                    SUBSCRIPTION_ID
                ),

                source=(
                    "normalized_alert."
                    "subscription_id"
                ),
            )
        ],

        workflow_status=(
            WorkflowStatus.RUNNING
        ),

        step_status=(
            StepStatus.APPROVED
        ),

        approval_status=(
            ApprovalStatus.APPROVED
        ),
    )


def create_approved_step():
    return (
        build_approved_procedure_step(
            create_runtime_state()
        )
    )


def create_verified_request():
    approved_step = (
        create_approved_step()
    )

    candidate = (
        build_azure_operation_request(
            approved_step
        )
    )

    return (
        PreCallSecurityVerifier.verify(
            approved_step=(
                approved_step
            ),

            candidate=(
                candidate
            ),
        )
    )


def test_approved_step_preserves_exact_human_approved_description():
    """
    La semántica que el técnico vio y aprobó
    en HITL no puede desaparecer al construir
    ApprovedProcedureStep.

    Este es el primer punto donde actualmente
    perdemos la operación exacta autorizada.
    """

    approved_step = (
        create_approved_step()
    )

    assert (
        approved_step.description
        == APPROVED_DESCRIPTION
    )


def test_azure_candidate_preserves_exact_approved_description():
    """
    AzureOperationRequest debe transportar la
    descripción exacta aprobada.

    No debe reconstruirse posteriormente mediante
    un LLM ni inferirse desde target_resource.
    """

    approved_step = (
        create_approved_step()
    )

    candidate = (
        build_azure_operation_request(
            approved_step
        )
    )

    assert (
        candidate.description
        == APPROVED_DESCRIPTION
    )


def test_verified_request_preserves_exact_approved_description():
    """
    PreCallSecurity debe conservar exactamente
    la descripción aprobada dentro del request
    verificado que podrá alcanzar Azure Operations.
    """

    verified = (
        create_verified_request()
    )

    assert (
        verified.description
        == APPROVED_DESCRIPTION
    )


def test_pre_call_rejects_description_substitution():
    """
    Un atacante no puede transformar:

        listar Resource Groups

    en:

        listar suscripciones

    aunque:

    - operation_domain siga siendo azure;
    - operation_kind siga siendo read;
    - target_resource siga siendo subscription;
    - subscription_id siga siendo el mismo.
    """

    approved_step = (
        create_approved_step()
    )

    candidate = (
        build_azure_operation_request(
            approved_step
        )
    )

    tampered = (
        candidate.model_copy(
            update={
                "description":
                    TAMPERED_DESCRIPTION,
            }
        )
    )

    with pytest.raises(
        PreCallSecurityError,
        match=(
            "description"
        ),
    ):
        (
            PreCallSecurityVerifier
            .verify(
                approved_step=(
                    approved_step
                ),

                candidate=(
                    tampered
                ),
            )
        )


def test_operation_start_rejects_description_different_from_runtime():
    """
    Incluso después de PreCall, OperationStart
    vuelve a correlacionar el request contra el
    ProcedureRuntimeState autoritativo.

    La descripción forma parte de esa identidad
    operacional y no puede cambiar.
    """

    verified = (
        create_verified_request()
    )

    runtime_state = (
        create_runtime_state()
    )

    runtime_state.step.description = (
        TAMPERED_DESCRIPTION
    )

    with pytest.raises(
        ValueError,
        match=(
            "description"
        ),
    ):
        (
            _validate_request_against_runtime(
                verified,
                runtime_state,
            )
        )


def test_azure_operations_prompt_contains_exact_approved_description():
    """
    Azure Operations debe conocer qué operación
    exacta fue aprobada.

    Para este caso no basta con transmitir:

        azure
        read
        subscription
        subscription_id

    porque ese conjunto permite múltiples consultas
    Azure diferentes.

    Debe llegar también:

        Consultar el listado de Resource Groups...
    """

    verified = (
        create_verified_request()
    )

    prompt = (
        AzureOperationsExecutor
        ._build_prompt(
            verified
        )
    )

    assert (
        APPROVED_DESCRIPTION
        in prompt
    )

    assert (
        SUBSCRIPTION_ID
        in prompt
    )

    assert (
        "subscription_id"
        in prompt
    )

    assert (
        TAMPERED_DESCRIPTION
        not in prompt
    )