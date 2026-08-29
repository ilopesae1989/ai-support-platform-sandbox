from types import SimpleNamespace

import pytest

import src.runtime.procedure.approval_resumer as approval_resumer

from src.runtime.procedure.approval_resolution import (
    ApprovalResumeInstruction,
)

from src.runtime.procedure.workflow import (
    ApprovalRequest,
)


REQUEST_ID = "req-phase18-restore-001"
CHECKPOINT_ID = "cp-phase18-restore-001"

WORKFLOW_ID = "wf-phase18-restore-001"
APPROVAL_ID = "apr-phase18-restore-001"

CONVERSATION_ID = "19:phase18-restore@thread.v2"


def create_request():
    return ApprovalRequest(
        workflow_id=WORKFLOW_ID,
        approval_id=APPROVAL_ID,
        alert_id="alert-phase18-001",
        correlation_id="corr-phase18-001",
        conversation_id=CONVERSATION_ID,
        procedure_id="NTTSY-SBX-AZ-VM-001",
        procedure_version="1.0",
        current_step=1,
        step_id="step-001",
        description="Start governed VM",
        operation_domain="azure",
        operation_kind="write",
        operation_action="vm_start",
        capability_id="azure.vm.start",
        hitl_required=True,
        next_action="execute_step",
        target_resource=(
            "/subscriptions/sub/resourceGroups/rg/"
            "providers/Microsoft.Compute/"
            "virtualMachines/vm-demo"
        ),
        required_parameters=[
            "subscription_id",
            "resource_group",
            "vm_name",
        ],
        resolved_parameters=[],
    )


def create_instruction():
    return ApprovalResumeInstruction(
        approval_id=APPROVAL_ID,
        workflow_id=WORKFLOW_ID,
        request_id=REQUEST_ID,
        checkpoint_id=CHECKPOINT_ID,
        approved=True,
    )


class FakeWorkflow:
    def __init__(self, request):
        self.request = request
        self.run_calls = []

    async def run(self, **kwargs):
        self.run_calls.append(kwargs)

        yield SimpleNamespace(
            type="request_info",
            request_id=REQUEST_ID,
            data=self.request,
        )


@pytest.mark.asyncio
async def test_public_restore_helper_uses_explicit_checkpoint_storage():
    request = create_request()
    workflow = FakeWorkflow(request)
    checkpoint_storage = object()

    restored = await (
        approval_resumer
        .restore_and_verify_pending_request(
            workflow=workflow,
            instruction=create_instruction(),
            expected_conversation_id=CONVERSATION_ID,
            checkpoint_storage=checkpoint_storage,
        )
    )

    assert restored is request

    assert workflow.run_calls == [
        {
            "checkpoint_id": CHECKPOINT_ID,
            "checkpoint_storage": checkpoint_storage,
            "stream": True,
        }
    ]
