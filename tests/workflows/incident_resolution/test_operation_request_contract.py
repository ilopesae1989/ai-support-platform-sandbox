from typing import get_type_hints

from src.runtime.procedure.models import (
    ApprovedProcedureStep,
    NextAction,
    OperationKind,
    ResolvedParameter,
)

from src.workflows.incident_resolution.azure_operations import (
    build_azure_operation_request,
)

from src.workflows.incident_resolution.azure_operations_models import (
    AzureOperationRequest,
    VerifiedAzureOperationRequest,
)

from src.workflows.incident_resolution.executors.azure_operations import (
    AzureOperationsExecutor,
)

from src.workflows.incident_resolution.operation_models import (
    OperationRequest,
)

from src.workflows.incident_resolution.pre_call_security import (
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

CONVERSATION_ID = (
    "conv-azure-rg-list-001"
)

SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
)

APPROVED_DESCRIPTION = (
    "Consultar el listado de Resource Groups "
    "de la suscripción."
)


COMMON_OPERATION_FIELDS = (
    "operation_id",
    "workflow_id",
    "approval_id",
    "alert_id",
    "correlation_id",
    "conversation_id",
    "procedure_id",
    "procedure_version",
    "current_step",
    "step_id",
    "operation_domain",
    "operation_kind",
    "operation_action",
    "capability_id",
    "hitl_required",
    "next_action",
    "target_resource",
    "required_parameters",
    "resolved_parameters",
)


def create_approved_step() -> ApprovedProcedureStep:
    return ApprovedProcedureStep(
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
            "NTTSY-SBX-AZ-001"
        ),

        procedure_version=(
            "v1.0"
        ),

        current_step=1,

        step_id="1",

        description=(
            APPROVED_DESCRIPTION
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

        approved=True,
    )


def test_operation_request_contains_exact_common_contract():
    """
    FASE 15.2 / ampliado en FASE 17.1

    OperationRequest debe representar exactamente
    el contrato común actual.

    FASE 17.1 añade operation_action como identidad
    operacional vendor-neutral.

    No contiene marcadores de autorización ni
    campos específicos de Azure.
    """

    assert (
        tuple(
            OperationRequest.model_fields
        )
        == COMMON_OPERATION_FIELDS
    )

    assert (
        "security_verified"
        not in OperationRequest.model_fields
    )

    assert (
        "verification_source"
        not in OperationRequest.model_fields
    )

    assert (
        "approved"
        not in OperationRequest.model_fields
    )


def test_azure_operation_request_reuses_common_contract():
    """
    AzureOperationRequest reutiliza íntegramente
    OperationRequest y añade exclusivamente:

        description
    """

    common_fields = tuple(
        OperationRequest
        .model_fields
        .keys()
    )

    azure_fields = tuple(
        AzureOperationRequest
        .model_fields
        .keys()
    )

    assert (
        azure_fields.count(
            "description"
        )
        == 1
    )

    assert (
        len(azure_fields)
        == len(common_fields) + 1
    )

    assert tuple(
        field_name
        for field_name in azure_fields
        if field_name != "description"
    ) == common_fields


def test_verified_azure_request_keeps_security_layer():
    """
    La generalización de OperationRequest no debe
    absorber ni debilitar la frontera pre-call.

    Los marcadores de seguridad sólo aparecen
    en VerifiedAzureOperationRequest.
    """

    assert issubclass(
        VerifiedAzureOperationRequest,
        AzureOperationRequest,
    )

    assert issubclass(
        VerifiedAzureOperationRequest,
        OperationRequest,
    )

    assert (
        "security_verified"
        in VerifiedAzureOperationRequest.model_fields
    )

    assert (
        "verification_source"
        in VerifiedAzureOperationRequest.model_fields
    )

    assert (
        "security_verified"
        not in AzureOperationRequest.model_fields
    )

    assert (
        "verification_source"
        not in AzureOperationRequest.model_fields
    )


def test_azure_builder_still_creates_domain_candidate():
    """
    build_azure_operation_request() debe continuar
    produciendo la especialización Azure candidata.

    No debe degradarse a OperationRequest genérico
    ni producir directamente una operación verificada.
    """

    candidate = (
        build_azure_operation_request(
            create_approved_step()
        )
    )

    assert (
        candidate.description
        == APPROVED_DESCRIPTION
    )

    assert (
        type(candidate)
        is AzureOperationRequest
    )

    assert isinstance(
        candidate,
        OperationRequest,
    )

    assert not isinstance(
        candidate,
        VerifiedAzureOperationRequest,
    )

    assert (
        not hasattr(
            candidate,
            "security_verified",
        )
    )


def test_pre_call_verification_preserves_common_contract():
    """
    Todos los campos comunes deben sobrevivir
    literalmente:

        ApprovedProcedureStep
            ↓
        AzureOperationRequest
            ↓
        VerifiedAzureOperationRequest
    """

    approved_step = (
        create_approved_step()
    )

    candidate = (
        build_azure_operation_request(
            approved_step
        )
    )

    verified = (
        PreCallSecurityVerifier.verify(
            approved_step=(
                approved_step
            ),

            candidate=(
                candidate
            ),
        )
    )

    assert isinstance(
        verified,
        VerifiedAzureOperationRequest,
    )

    assert (
        verified.description
        == APPROVED_DESCRIPTION
    )

    for field_name in (
        COMMON_OPERATION_FIELDS
    ):
        if (
            field_name
            == "resolved_parameters"
        ):
            assert (
                [
                    parameter.model_dump(
                        mode="python"
                    )
                    for parameter
                    in verified.resolved_parameters
                ]
                == [
                    parameter.model_dump(
                        mode="python"
                    )
                    for parameter
                    in candidate.resolved_parameters
                ]
            )

            continue

        assert (
            getattr(
                verified,
                field_name,
            )
            == getattr(
                candidate,
                field_name,
            )
        )

    assert (
        verified.security_verified
        is True
    )

    assert (
        verified.verification_source
        == "pre_call_security_verifier"
    )


def test_azure_executor_still_requires_verified_domain_request():
    """
    La introducción de OperationRequest común
    no puede permitir que AzureOperationsExecutor
    acepte directamente:

        OperationRequest

    ni:

        AzureOperationRequest

    Debe continuar requiriendo exactamente:

        VerifiedAzureOperationRequest
    """

    hints = get_type_hints(
        AzureOperationsExecutor.handle
    )

    request_type = (
        hints["request"]
    )

    assert (
        request_type
        is VerifiedAzureOperationRequest
    )

    assert (
        request_type
        is not AzureOperationRequest
    )

    assert (
        request_type
        is not OperationRequest
    )
