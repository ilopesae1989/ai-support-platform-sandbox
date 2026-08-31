from __future__ import annotations

import json

import pytest

from pydantic import (
    ValidationError,
)

from src.runtime.procedure.models import (
    NextAction,
    OperationAction,
    OperationKind,
    ResolvedParameter,
)

from src.workflows.incident_resolution.executors.azure_vm_post_operation_observation import (
    AzureVmPostOperationObservationExecutor,
)

from src.workflows.incident_resolution.executors.procedure_validation import (
    ProcedureValidationExecutor,
)

from src.workflows.incident_resolution.mcp_evidence import (
    McpCallEvidence,
)

from src.workflows.incident_resolution.operation_evidence import (
    OperationEvidence,
)

from src.workflows.incident_resolution.operation_models import (
    OperationResult,
)

from src.workflows.incident_resolution.post_operation_observation import (
    AzureVmPowerStateObservation,
)

from src.workflows.incident_resolution.procedure_validation_models import (
    ProcedureValidationRequest,
    ProcedureValidationStep,
)

from src.workflows.incident_resolution.technical_evidence import (
    McpResultEvidence,
)


OPERATION_ID = "op-vm-post-observation-001"
WORKFLOW_ID = "wf-vm-post-observation-001"
APPROVAL_ID = "apr-vm-post-observation-001"
ALERT_ID = "alert-vm-post-observation-001"
CORRELATION_ID = "corr-vm-post-observation-001"
CONVERSATION_ID = "conv-vm-post-observation-001"

PROCEDURE_ID = "NTTSY-SBX-AZ-VM-DEMO-001"
PROCEDURE_VERSION = "1.0"

SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
)

RESOURCE_GROUP = "rg-icenter-sandbox-vm-demo"
VM_NAME = "vm-icenter-sbx-demo-01"

TARGET_RESOURCE = (
    "/subscriptions/"
    + SUBSCRIPTION_ID
    + "/resourceGroups/"
    + RESOURCE_GROUP
    + "/providers/Microsoft.Compute/"
    + "virtualMachines/"
    + VM_NAME
)


def resolved_parameters():
    return [
        ResolvedParameter(
            name="subscription_id",
            value=SUBSCRIPTION_ID,
            source="normalized_alert.subscription_id",
        ),
        ResolvedParameter(
            name="resource_group",
            value=RESOURCE_GROUP,
            source="normalized_alert.resource_group",
        ),
        ResolvedParameter(
            name="vm_name",
            value=VM_NAME,
            source="normalized_alert.vm_name",
        ),
    ]


def build_operation_evidence():
    call_id = "mcp-vm-start-001"

    return OperationEvidence(
        operation_id=OPERATION_ID,
        workflow_id=WORKFLOW_ID,
        approval_id=APPROVAL_ID,
        alert_id=ALERT_ID,
        correlation_id=CORRELATION_ID,
        conversation_id=CONVERSATION_ID,
        procedure_id=PROCEDURE_ID,
        procedure_version=PROCEDURE_VERSION,
        current_step=1,
        step_id="1",
        operation_domain="azure",
        operation_kind=OperationKind.WRITE,
        operation_action=OperationAction.VM_START,
        capability_id="azure.vm.start",
        hitl_required=True,
        next_action=NextAction.EXECUTE_STEP,
        target_resource=TARGET_RESOURCE,
        required_parameters=[
            "subscription_id",
            "resource_group",
            "vm_name",
        ],
        resolved_parameters=resolved_parameters(),
        mcp_calls=[
            McpCallEvidence(
                mcp_call_id=call_id,
                server_name="azure-mcp-operations-sbx",
                tool_name="compute_vm_power-state",
                arguments={
                    "subscription": SUBSCRIPTION_ID,
                    "resource-group": RESOURCE_GROUP,
                    "vm-name": VM_NAME,
                    "power-action": "start",
                },
            )
        ],
        mcp_results=[
            McpResultEvidence(
                mcp_call_id=call_id,
                output={
                    "status": 200
                },
            )
        ],
    )


def create_vm_start_result(
    *,
    backend_success=True,
):
    if backend_success:
        evidence = build_operation_evidence()

        technical_success = (
            evidence.derive_technical_success()
        )

        assert technical_success is True
        error = None

    else:
        evidence = None
        technical_success = False
        error = "backend failure"

    return OperationResult(
        operation_id=OPERATION_ID,
        workflow_id=WORKFLOW_ID,
        approval_id=APPROVAL_ID,
        alert_id=ALERT_ID,
        correlation_id=CORRELATION_ID,
        conversation_id=CONVERSATION_ID,
        procedure_id=PROCEDURE_ID,
        procedure_version=PROCEDURE_VERSION,
        current_step=1,
        step_id="1",
        operation_domain="azure",
        operation_kind=OperationKind.WRITE,
        operation_action=OperationAction.VM_START,
        capability_id="azure.vm.start",
        hitl_required=True,
        next_action=NextAction.EXECUTE_STEP,
        target_resource=TARGET_RESOURCE,
        required_parameters=[
            "subscription_id",
            "resource_group",
            "vm_name",
        ],
        resolved_parameters=resolved_parameters(),
        success=backend_success,
        technical_success=technical_success,
        response_text=(
            "VM start completed."
            if backend_success
            else None
        ),
        error=error,
        evidence=evidence,
    )


def create_step():
    return ProcedureValidationStep(
        procedure_id=PROCEDURE_ID,
        procedure_version=PROCEDURE_VERSION,
        current_step=1,
        step_id="1",
        description=(
            "Arrancar exclusivamente la "
            "máquina virtual de sandbox."
        ),
        expected_result=(
            "La máquina virtual debe alcanzar "
            "PowerState/running."
        ),
        verification=(
            "Comprobar explícitamente que "
            "PowerState sea running."
        ),
    )


def create_request(
    *,
    backend_success=True,
):
    return ProcedureValidationRequest(
        operation_result=(
            create_vm_start_result(
                backend_success=backend_success
            )
        ),
        step=create_step(),
    )


class FakeReader:
    def __init__(
        self,
        *,
        power_state="PowerState/running",
        error=None,
    ):
        self.power_state = power_state
        self.error = error
        self.calls = []

    def read_power_state(
        self,
        *,
        subscription_id,
        resource_group,
        vm_name,
    ):
        self.calls.append(
            {
                "subscription_id": subscription_id,
                "resource_group": resource_group,
                "vm_name": vm_name,
            }
        )

        if self.error is not None:
            raise self.error

        return self.power_state


class FakeContext:
    def __init__(self):
        self.messages = []

    async def send_message(
        self,
        message,
    ):
        self.messages.append(
            message
        )


@pytest.mark.asyncio
async def test_successful_vm_start_gets_exact_running_observation():
    request = create_request()

    before = request.model_dump(
        mode="json"
    )

    reader = FakeReader()
    ctx = FakeContext()

    executor = (
        AzureVmPostOperationObservationExecutor(
            reader=reader
        )
    )

    await executor.handle(
        request,
        ctx,
    )

    assert len(reader.calls) == 1

    assert reader.calls[0] == {
        "subscription_id": SUBSCRIPTION_ID,
        "resource_group": RESOURCE_GROUP,
        "vm_name": VM_NAME,
    }

    assert len(ctx.messages) == 1

    enriched = ctx.messages[0]

    observation = (
        enriched.post_operation_observation
    )

    assert observation is not None
    assert observation.success is True
    assert observation.power_state == "PowerState/running"
    assert observation.error is None
    assert observation.operation_id == OPERATION_ID
    assert observation.workflow_id == WORKFLOW_ID
    assert observation.approval_id == APPROVAL_ID
    assert observation.target_resource == TARGET_RESOURCE

    assert (
        request.model_dump(
            mode="json"
        )
        == before
    )


@pytest.mark.asyncio
async def test_reader_failure_becomes_explicit_failed_observation():
    reader = FakeReader(
        error=RuntimeError(
            "instance view unavailable"
        )
    )

    ctx = FakeContext()

    await (
        AzureVmPostOperationObservationExecutor(
            reader=reader
        )
        .handle(
            create_request(),
            ctx,
        )
    )

    observation = (
        ctx.messages[0]
        .post_operation_observation
    )

    assert observation is not None
    assert observation.success is False
    assert observation.power_state is None
    assert "RuntimeError" in observation.error
    assert "instance view unavailable" in observation.error


@pytest.mark.asyncio
async def test_missing_reader_becomes_explicit_failed_observation():
    ctx = FakeContext()

    await (
        AzureVmPostOperationObservationExecutor()
        .handle(
            create_request(),
            ctx,
        )
    )

    observation = (
        ctx.messages[0]
        .post_operation_observation
    )

    assert observation is not None
    assert observation.success is False
    assert "no está configurado" in observation.error


@pytest.mark.asyncio
async def test_failed_write_does_not_call_reader():
    reader = FakeReader()
    ctx = FakeContext()

    await (
        AzureVmPostOperationObservationExecutor(
            reader=reader
        )
        .handle(
            create_request(
                backend_success=False
            ),
            ctx,
        )
    )

    assert reader.calls == []

    assert (
        ctx.messages[0]
        .post_operation_observation
        is None
    )


def test_observation_rejects_target_not_matching_vm_identity():
    with pytest.raises(
        ValidationError,
        match="target_resource",
    ):
        AzureVmPowerStateObservation(
            operation_id=OPERATION_ID,
            workflow_id=WORKFLOW_ID,
            approval_id=APPROVAL_ID,
            target_resource=TARGET_RESOURCE + "-attacker",
            subscription_id=SUBSCRIPTION_ID,
            resource_group=RESOURCE_GROUP,
            vm_name=VM_NAME,
            success=True,
            power_state="PowerState/running",
            error=None,
        )


def test_validation_request_rejects_observation_for_other_operation():
    wrong = AzureVmPowerStateObservation(
        operation_id="op-attacker",
        workflow_id=WORKFLOW_ID,
        approval_id=APPROVAL_ID,
        target_resource=TARGET_RESOURCE,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        vm_name=VM_NAME,
        success=True,
        power_state="PowerState/running",
        error=None,
    )

    with pytest.raises(
        ValidationError,
        match="post-operation observation",
    ):
        ProcedureValidationRequest(
            operation_result=create_vm_start_result(),
            step=create_step(),
            post_operation_observation=wrong,
        )


@pytest.mark.asyncio
async def test_validation_prompt_contains_trusted_running_observation():
    reader = FakeReader()
    ctx = FakeContext()

    await (
        AzureVmPostOperationObservationExecutor(
            reader=reader
        )
        .handle(
            create_request(),
            ctx,
        )
    )

    prompt = (
        ProcedureValidationExecutor
        ._build_prompt(
            ctx.messages[0]
        )
    )

    payload = json.loads(
        prompt
    )

    observation = payload[
        "post_operation_observation"
    ]

    assert observation[
        "source"
    ] == "azure_compute_instance_view"

    assert (
        observation["power_state"]
        == "PowerState/running"
    )

    assert observation["success"] is True


def test_success_observation_requires_explicit_power_state():
    with pytest.raises(
        ValidationError,
        match="PowerState",
    ):
        AzureVmPowerStateObservation(
            operation_id=OPERATION_ID,
            workflow_id=WORKFLOW_ID,
            approval_id=APPROVAL_ID,
            target_resource=TARGET_RESOURCE,
            subscription_id=SUBSCRIPTION_ID,
            resource_group=RESOURCE_GROUP,
            vm_name=VM_NAME,
            success=True,
            power_state=None,
            error=None,
        )


def test_failed_observation_requires_explicit_error():
    with pytest.raises(
        ValidationError,
        match="error",
    ):
        AzureVmPowerStateObservation(
            operation_id=OPERATION_ID,
            workflow_id=WORKFLOW_ID,
            approval_id=APPROVAL_ID,
            target_resource=TARGET_RESOURCE,
            subscription_id=SUBSCRIPTION_ID,
            resource_group=RESOURCE_GROUP,
            vm_name=VM_NAME,
            success=False,
            power_state=None,
            error=None,
        )
