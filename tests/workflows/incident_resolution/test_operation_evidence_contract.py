import pytest

from pydantic import (
    ValidationError,
)

from src.runtime.procedure.models import (
    OperationKind,
    StepEvidence,
)

from src.workflows.incident_resolution.azure_operations_models import (
    AzureOperationResult,
)

from src.workflows.incident_resolution.operation_evidence import (
    OperationEvidence,
)

from src.workflows.incident_resolution.operation_models import (
    OperationResult,
)


def create_common_result(
    *,
    evidence: OperationEvidence | None = None,
) -> OperationResult:
    return OperationResult(
        workflow_id="wf-evidence-001",

        approval_id="apr-evidence-001",

        alert_id="ALT-EVIDENCE-001",

        correlation_id="corr-evidence-001",

        procedure_id="PROC-EVIDENCE-001",

        procedure_version="v1.0",

        current_step=1,

        step_id="1",

        operation_kind=(
            OperationKind.READ
        ),

        target_resource="resource-001",

        success=True,

        response_text="fake-result",

        error=None,

        evidence=evidence,
    )


def test_operation_evidence_starts_as_empty_contract():
    """
    FASE 15.4 crea exclusivamente el envelope.

    Ningún campo de fases posteriores debe aparecer
    todavía.
    """

    assert (
        tuple(
            OperationEvidence.model_fields
        )
        == ()
    )

    evidence = (
        OperationEvidence()
    )

    assert isinstance(
        evidence,
        OperationEvidence,
    )


def test_operation_evidence_rejects_unmodeled_fields():
    """
    No se permite usar OperationEvidence como un
    diccionario libre para adelantar tool/MCP data.
    """

    with pytest.raises(
        ValidationError,
    ):
        OperationEvidence(
            tool_name="invented-tool"
        )


def test_operation_result_exposes_optional_evidence():
    result = (
        create_common_result()
    )

    assert (
        "evidence"
        in OperationResult.model_fields
    )

    assert result.evidence is None


def test_operation_result_accepts_operation_evidence():
    evidence = (
        OperationEvidence()
    )

    result = (
        create_common_result(
            evidence=evidence
        )
    )

    assert (
        result.evidence
        == evidence
    )

    assert isinstance(
        result.evidence,
        OperationEvidence,
    )


def test_azure_operation_result_inherits_evidence_contract():
    result = AzureOperationResult(
        workflow_id="wf-azure-evidence-001",

        approval_id="apr-azure-evidence-001",

        alert_id="ALT-AZ-001",

        correlation_id="corr-azure-001",

        procedure_id="PROC-AZ-001",

        procedure_version="v1.0",

        current_step=1,

        step_id="1",

        operation_kind=(
            OperationKind.READ
        ),

        target_resource="resource-azure-001",

        success=True,

        response_text="fake-result",

        error=None,

        evidence=OperationEvidence(),
    )

    assert isinstance(
        result,
        OperationResult,
    )

    assert isinstance(
        result.evidence,
        OperationEvidence,
    )


def test_operation_evidence_is_distinct_from_step_evidence():
    """
    OperationEvidence pertenece a la capa técnica de
    operaciones.

    StepEvidence pertenece al runtime del
    procedimiento.

    No existe herencia entre ambos contratos.
    """

    assert (
        OperationEvidence
        is not StepEvidence
    )

    assert not issubclass(
        OperationEvidence,
        StepEvidence,
    )

    assert not issubclass(
        StepEvidence,
        OperationEvidence,
    )
