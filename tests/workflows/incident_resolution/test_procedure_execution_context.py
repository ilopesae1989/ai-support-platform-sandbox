from dataclasses import replace

import pytest

from src.agents.contracts import (
    ProcedureExecutionResult,
)
from src.workflows.incident_resolution.executors.procedure import (
    ProcedureExecutionExecutor,
)
from src.workflows.incident_resolution.executors.runtime import (
    ProcedureRuntimeExecutor,
)
from src.workflows.incident_resolution.models import (
    ExecutionIdentity,
    ProcedureExecutionContext,
    ProcedureExecutionInput,
    ProcedureExecutionRequest,
)
from src.workflows.incident_resolution.operational_context import (
    OperationalContext,
)


SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-a9ae-e9e89b5ad172"
)

WORKFLOW_ID = (
    "wf-11111111-1111-4111-"
    "8111-111111111111"
)

CORRELATION_ID = (
    "corr-azure-rg-list-live-001"
)


def create_request() -> ProcedureExecutionRequest:
    return ProcedureExecutionRequest(
        alert_id="ALT-AZ-RG-LIST-001",
        procedure_found=True,
        procedure_match="exact",
        execution_eligible=True,
        procedure_id="NTTSY-SBX-AZ-001",
        procedure_name=(
            "Consulta de Resource Groups "
            "de una suscripción Azure"
        ),
        procedure_version="1.0",
        affected_resource=SUBSCRIPTION_ID,
        incident_description=(
            "Consultar Resource Groups."
        ),
    )


def create_identity() -> ExecutionIdentity:
    return ExecutionIdentity(
        workflow_id=WORKFLOW_ID,
        alert_id="ALT-AZ-RG-LIST-001",
        correlation_id=CORRELATION_ID,
    )


def create_operational_context():
    return OperationalContext(
        alert_id="ALT-AZ-RG-LIST-001",
        affected_resource=SUBSCRIPTION_ID,
        resource_type="subscription",
        service="Azure Resource Manager",
        environment="sandbox",
        subscription_id=SUBSCRIPTION_ID,
        tenant_id=(
            "0cb40b2b-6cfc-4c63-"
            "bf7b-da710ea390cb"
        ),
        correlation_id=(
            CORRELATION_ID
        ),
    )


def create_result():
    return ProcedureExecutionResult.model_validate(
        {
            "alert_id":
                "ALT-AZ-RG-LIST-001",
            "procedure": {
                "id":
                    "NTTSY-SBX-AZ-001",
                "name": (
                    "Consulta de Resource Groups "
                    "de una suscripción Azure"
                ),
                "version": "1.0",
            },
            "execution_allowed": True,
            "blocked_by_policy": False,
            "total_steps": 1,
            "current_step": 1,
            "step": {
                "id": "1",
                "description": (
                    "Consultar Resource Groups."
                ),
                "step_type": "validation",
                "operation_domain": "azure",
                "operation_kind": "read",
                "target_resource":
                    "subscription",
                "required_parameters": [
                    "subscription_id"
                ],
                "preconditions": [],
                "expected_result": (
                    "Listado de Resource Groups."
                ),
                "verification": (
                    "Validar el listado obtenido."
                ),
            },
            "resolution_criteria": None,
            "next_action": "execute_step",
            "escalation": {
                "required": False,
                "team": None,
                "level": None,
                "criteria": None,
            },
            "requires_clarification": False,
            "missing_information": [],
            "source_documents": [
                "NTTSY-SBX-AZ-001"
            ],
            "confidence": 0.95,
        }
    )


def create_execution_context():
    return ProcedureExecutionContext(
        request=create_request(),
        result=create_result(),
        execution_identity=(
            create_identity()
        ),
        operational_context=(
            create_operational_context()
        ),
    )


def test_exact_execution_input_is_valid():
    execution_input = ProcedureExecutionInput(
        request=create_request(),
        execution_identity=(
            create_identity()
        ),
        operational_context=(
            create_operational_context()
        ),
    )

    ProcedureExecutionExecutor._validate_input(
        execution_input
    )


def test_input_alert_mismatch_is_rejected():
    operational = (
        create_operational_context()
    )

    operational.alert_id = "ALT-OTHER"

    execution_input = ProcedureExecutionInput(
        request=create_request(),
        execution_identity=(
            create_identity()
        ),
        operational_context=operational,
    )

    with pytest.raises(
        ValueError,
        match="identidades de alerta",
    ):
        ProcedureExecutionExecutor._validate_input(
            execution_input
        )


def test_exact_procedure_result_identity_is_valid():
    ProcedureExecutionExecutor._validate_result_identity(
        create_request(),
        create_result(),
    )


def test_procedure_result_alert_swap_is_rejected():
    result = create_result()

    result.alert_id = "ALT-OTHER"

    with pytest.raises(
        ValueError,
        match="alert_id diferente",
    ):
        ProcedureExecutionExecutor._validate_result_identity(
            create_request(),
            result,
        )


def test_procedure_swap_is_rejected():
    result = create_result()

    result.procedure.id = (
        "NTTSY-SBX-AZ-999"
    )

    with pytest.raises(
        ValueError,
        match="procedimiento diferente",
    ):
        ProcedureExecutionExecutor._validate_result_identity(
            create_request(),
            result,
        )


def test_procedure_version_swap_is_rejected():
    result = create_result()

    result.procedure.version = "9.9"

    with pytest.raises(
        ValueError,
        match="versión diferente",
    ):
        ProcedureExecutionExecutor._validate_result_identity(
            create_request(),
            result,
        )


def test_operational_context_survives_exactly():
    execution_context = (
        create_execution_context()
    )

    assert (
        execution_context
        .operational_context
        .subscription_id
        == SUBSCRIPTION_ID
    )

    assert (
        execution_context
        .result
        .step
        .required_parameters
        == ["subscription_id"]
    )


def test_runtime_revalidates_execution_context():
    ProcedureRuntimeExecutor._validate_execution_context(
        create_execution_context()
    )


def test_runtime_blocks_operational_alert_swap():
    execution_context = (
        create_execution_context()
    )

    execution_context.operational_context.alert_id = (
        "ALT-OTHER"
    )

    with pytest.raises(
        ValueError,
        match="OperationalContext no corresponde",
    ):
        ProcedureRuntimeExecutor._validate_execution_context(
            execution_context
        )