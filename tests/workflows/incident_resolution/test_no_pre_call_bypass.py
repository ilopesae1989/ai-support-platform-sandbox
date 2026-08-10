import inspect

from typing import (
    get_args,
    get_type_hints,
)

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

from src.workflows.incident_resolution.executors.azure_pre_call import (
    AzurePreCallSecurityExecutor,
)

from src.workflows.incident_resolution.pre_call_security import (
    PreCallSecurityVerifier,
)

from src.workflows.incident_resolution.workflow import (
    build_incident_resolution_workflow,
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

SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
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
            "conv-azure-rg-list-001"
        ),

        procedure_id=(
            "NTTSY-SBX-AZ-001"
        ),

        procedure_version=(
            "v1.0"
        ),

        current_step=1,

        step_id="1",

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


def test_pre_call_executor_contract_is_exact():
    """
    AzurePreCallSecurityExecutor debe recibir:

        ApprovedProcedureStep

    y su WorkflowContext debe transportar:

        VerifiedAzureOperationRequest

    get_type_hints() resuelve correctamente
    anotaciones diferidas por:

        from __future__ import annotations
    """

    hints = (
        get_type_hints(
            AzurePreCallSecurityExecutor.handle
        )
    )

    assert (
        hints["step"]
        is ApprovedProcedureStep
    )

    ctx_annotation = (
        hints["ctx"]
    )

    ctx_args = (
        get_args(
            ctx_annotation
        )
    )

    assert (
        VerifiedAzureOperationRequest
        in ctx_args
    )


def test_azure_operations_executor_contract_requires_verified_request():
    """
    AzureOperationsExecutor sólo acepta como
    contrato de entrada:

        VerifiedAzureOperationRequest

    No ApprovedProcedureStep.
    No AzureOperationRequest sin verificar.
    """

    hints = (
        get_type_hints(
            AzureOperationsExecutor.handle
        )
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
        is not ApprovedProcedureStep
    )


def test_builder_only_creates_unverified_candidate():
    """
    build_azure_operation_request() únicamente
    construye un candidato.

    No debe otorgar autoridad por sí mismo.
    """

    approved_step = (
        create_approved_step()
    )

    candidate = (
        build_azure_operation_request(
            approved_step
        )
    )

    assert isinstance(
        candidate,
        AzureOperationRequest,
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


def test_only_verifier_creates_verified_request():
    """
    Sólo PreCallSecurityVerifier convierte el
    candidato en VerifiedAzureOperationRequest.
    """

    approved_step = (
        create_approved_step()
    )

    candidate = (
        build_azure_operation_request(
            approved_step
        )
    )

    verifier = (
        PreCallSecurityVerifier()
    )

    verified = (
        verifier.verify(
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
        verified.security_verified
        is True
    )

    assert (
        verified.verification_source
        == "pre_call_security_verifier"
    )


def test_verified_request_preserves_approval_identity():
    """
    ApprovedProcedureStep
        ↓
    AzureOperationRequest
        ↓
    VerifiedAzureOperationRequest

    debe conservar literalmente toda la identidad
    de seguridad.
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

    assert (
        verified.workflow_id
        == approved_step.workflow_id
    )

    assert (
        verified.approval_id
        == approved_step.approval_id
    )

    assert (
        verified.alert_id
        == approved_step.alert_id
    )

    assert (
        verified.correlation_id
        == approved_step.correlation_id
    )

    assert (
        verified.conversation_id
        == approved_step.conversation_id
    )

    assert (
        verified.procedure_id
        == approved_step.procedure_id
    )

    assert (
        verified.procedure_version
        == approved_step.procedure_version
    )

    assert (
        verified.current_step
        == approved_step.current_step
    )

    assert (
        verified.step_id
        == approved_step.step_id
    )

    assert (
        verified.operation_domain
        == approved_step.operation_domain
    )

    assert (
        verified.operation_kind
        == approved_step.operation_kind
    )

    assert (
        verified.next_action
        == approved_step.next_action
    )

    assert (
        verified.target_resource
        == approved_step.target_resource
    )

    assert (
        list(
            verified.required_parameters
        )
        == approved_step.required_parameters
    )

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
            in approved_step.resolved_parameters
        ]
    )


def test_workflow_source_contains_pre_call_edge_and_no_direct_azure_edge():
    """
    Defensa estructural adicional.

    El switch post-HITL debe enviar Azure a:

        azure_pre_call

    y únicamente después:

        azure_pre_call -> azure_route

    No debe existir:

        approval -> azure_route
    """

    source = (
        inspect.getsource(
            build_incident_resolution_workflow
        )
    )

    assert (
        "azure_pre_call"
        in source
    )

    assert (
        ".add_edge(\n"
        "            azure_pre_call,\n"
        "            azure_route,"
        in source
    )

    assert (
        ".add_edge(\n"
        "            approval,\n"
        "            azure_route,"
        not in source
    )


def test_approved_step_is_not_verified_request():
    """
    El snapshot HITL no es todavía una
    autorización pre-call.

    Requiere pasar por el verifier.
    """

    approved_step = (
        create_approved_step()
    )

    assert not isinstance(
        approved_step,
        VerifiedAzureOperationRequest,
    )