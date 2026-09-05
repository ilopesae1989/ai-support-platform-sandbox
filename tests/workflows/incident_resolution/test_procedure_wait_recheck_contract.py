import ast
import importlib
from pathlib import Path

import pytest

from src.agents.contracts import (
    ProcedureValidationEscalation,
    ProcedureValidationResult,
)

from src.runtime.procedure.models import (
    ApprovalStatus,
    NextAction,
    OperationAction,
    OperationKind,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
    ResolvedParameter,
    StepEvidence,
    StepStatus,
    WorkflowStatus,
)

from src.runtime.procedure.workflow_state import (
    PROCEDURE_RUNTIME_STATE_KEY,
)

from src.workflows.incident_resolution.executors.procedure_transition import (
    ProcedureTransitionExecutor,
)

from src.workflows.incident_resolution.operation_evidence import (
    OperationEvidence,
)

from src.workflows.incident_resolution.operation_models import (
    OperationResult,
)

from src.workflows.incident_resolution.procedure_validation_models import (
    ProcedureValidationContext,
    ProcedureValidationRequest,
    ProcedureValidationStep,
)

from src.workflows.incident_resolution.technical_evidence import (
    ToolResultEvidence,
)

from src.workflows.incident_resolution.tool_evidence import (
    ToolCallEvidence,
)


WORKFLOW_ID = "wf-wait-vm-001"
APPROVAL_ID = "apr-wait-vm-001"
ALERT_ID = "ALT-WAIT-VM-001"
CORRELATION_ID = "corr-wait-vm-001"
CONVERSATION_ID = "conv-wait-vm-001"

PROCEDURE_ID = "NTTSY-WAIT-VM-001"
PROCEDURE_VERSION = "1.0"

SUBSCRIPTION_ID = "557fdabc-f3b6-4c24-a9ae-e9e89b5ad172"
RESOURCE_GROUP = "rg-wait-recheck"
VM_NAME = "vm-wait-recheck"

TARGET_RESOURCE = (
    "/subscriptions/"
    + SUBSCRIPTION_ID
    + "/resourceGroups/"
    + RESOURCE_GROUP
    + "/providers/Microsoft.Compute/"
    + "virtualMachines/"
    + VM_NAME
)

REQUIRED_PARAMETERS = [
    "subscription_id",
    "resource_group",
    "vm_name",
]


def _resolved_parameters():
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


def _operation_evidence():
    evidence = OperationEvidence(
        operation_id="op-wait-vm-001",
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
        required_parameters=REQUIRED_PARAMETERS,
        resolved_parameters=_resolved_parameters(),
        tool_calls=[
            ToolCallEvidence(
                tool_call_id="tool-wait-vm-001",
                tool_name="azure.vm.start",
                arguments={
                    "subscription_id": SUBSCRIPTION_ID,
                    "resource_group": RESOURCE_GROUP,
                    "vm_name": VM_NAME,
                },
            )
        ],
        tool_results=[
            ToolResultEvidence(
                tool_call_id="tool-wait-vm-001",
                result_text="Backend invocation completed.",
                exception=None,
            )
        ],
    )

    assert (
        evidence.derive_technical_success()
        is True
    )

    return evidence


def _operation_result():
    evidence = _operation_evidence()

    return OperationResult(
        operation_id=evidence.operation_id,
        workflow_id=evidence.workflow_id,
        approval_id=evidence.approval_id,
        alert_id=evidence.alert_id,
        correlation_id=evidence.correlation_id,
        conversation_id=evidence.conversation_id,
        procedure_id=evidence.procedure_id,
        procedure_version=evidence.procedure_version,
        current_step=evidence.current_step,
        step_id=evidence.step_id,
        operation_domain=evidence.operation_domain,
        operation_kind=evidence.operation_kind,
        operation_action=evidence.operation_action,
        capability_id=evidence.capability_id,
        hitl_required=evidence.hitl_required,
        next_action=evidence.next_action,
        target_resource=evidence.target_resource,
        required_parameters=list(
            evidence.required_parameters
        ),
        resolved_parameters=list(
            evidence.resolved_parameters
        ),
        success=True,
        technical_success=True,
        response_text="Backend invocation completed.",
        error=None,
        evidence=evidence,
    )


def _state(
    *,
    total_steps=2,
    retry_count=0,
):
    result = _operation_result()

    return ProcedureRuntimeState(
        workflow_id=WORKFLOW_ID,
        approval_id=APPROVAL_ID,
        alert_id=ALERT_ID,
        correlation_id=CORRELATION_ID,
        conversation_id=CONVERSATION_ID,
        procedure=ProcedureReference(
            id=PROCEDURE_ID,
            name="Governed VM Start WAIT recheck",
            version=PROCEDURE_VERSION,
        ),
        total_steps=total_steps,
        current_step=1,
        step=ProcedureStep(
            id="1",
            description="Start governed Azure VM.",
            step_type="remediation",
            operation_domain="azure",
            operation_kind=OperationKind.WRITE,
            operation_action=OperationAction.VM_START,
            capability_id="azure.vm.start",
            hitl_required=True,
            target_resource=TARGET_RESOURCE,
            required_parameters=REQUIRED_PARAMETERS,
            preconditions=[],
            expected_result=(
                "VM reaches PowerState/running."
            ),
            verification=(
                "Observe Azure Compute Instance View."
            ),
        ),
        resolved_parameters=_resolved_parameters(),
        workflow_status=WorkflowStatus.WAITING_VALIDATION,
        step_status=StepStatus.WAITING_VALIDATION,
        approval_status=ApprovalStatus.APPROVED,
        operation_result=StepEvidence(
            success=True,
            result=result.model_dump(
                mode="json"
            ),
            error=None,
        ),
    )


def _context(
    *,
    validation_status="indeterminate",
    proposed_next_action="wait",
):
    result = _operation_result()

    request = ProcedureValidationRequest(
        operation_result=result,
        step=ProcedureValidationStep(
            procedure_id=PROCEDURE_ID,
            procedure_version=PROCEDURE_VERSION,
            current_step=1,
            step_id="1",
            description="Start governed Azure VM.",
            expected_result=(
                "VM reaches PowerState/running."
            ),
            verification=(
                "Observe Azure Compute Instance View."
            ),
        ),
    )

    cognitive = ProcedureValidationResult(
        operation_id=result.operation_id,
        validation_status=validation_status,
        proposed_next_action=proposed_next_action,
        validation_summary=(
            "VM state is not yet proven running."
        ),
        escalation=ProcedureValidationEscalation(
            required=False
        ),
    )

    return ProcedureValidationContext(
        request=request,
        result=cognitive,
    )


class WaitWorkflowContext:
    def __init__(
        self,
        snapshot,
    ):
        self.states = {
            PROCEDURE_RUNTIME_STATE_KEY:
                snapshot
        }

        self.requests = []
        self.messages = []
        self.outputs = []

    def get_state(
        self,
        key,
        default=None,
    ):
        return self.states.get(
            key,
            default,
        )

    def set_state(
        self,
        key,
        value,
    ):
        self.states[key] = value

    async def request_info(
        self,
        request_data,
        response_type,
        *,
        request_id=None,
    ):
        self.requests.append(
            (
                request_data,
                response_type,
                request_id,
            )
        )

    async def send_message(
        self,
        message,
        target_id=None,
    ):
        self.messages.append(
            (
                message,
                target_id,
            )
        )

    async def yield_output(
        self,
        value,
    ):
        self.outputs.append(
            value
        )


def _runtime_snapshot(
    *,
    total_steps=2,
    retry_count=0,
    recheck_count=None,
):
    state = _state(
        total_steps=total_steps,
        retry_count=retry_count,
    )

    snapshot = state.model_dump(
        mode="json"
    )

    if recheck_count is not None:
        snapshot[
            "recheck_count"
        ] = recheck_count

    return snapshot


def test_runtime_state_declares_python_owned_recheck_count():
    field = (
        ProcedureRuntimeState
        .model_fields
        .get(
            "recheck_count"
        )
    )

    assert field is not None
    assert field.default == 0


def test_wait_recheck_contract_is_separate_from_approval_request():
    module = importlib.import_module(
        "src.workflows."
        "incident_resolution."
        "wait_recheck"
    )

    wait_request = getattr(
        module,
        "WaitRecheckRequest",
    )

    wait_signal = getattr(
        module,
        "WaitRecheckSignal",
    )

    from src.runtime.procedure.workflow import (
        ApprovalRequest,
    )

    assert (
        wait_request
        is not ApprovalRequest
    )

    request_fields = set(
        getattr(
            wait_request,
            "model_fields",
            {},
        )
    )

    signal_fields = set(
        getattr(
            wait_signal,
            "model_fields",
            {},
        )
    )

    assert (
        "approval_id"
        not in signal_fields
    )

    assert (
        "approved"
        not in signal_fields
    )

    assert (
        "recheck_id"
        in request_fields
    )

    assert (
        "recheck_id"
        in signal_fields
    )


@pytest.mark.asyncio
async def test_wait_transition_requests_external_recheck_instead_of_terminal_output():
    ctx = WaitWorkflowContext(
        _runtime_snapshot()
    )

    executor = (
        ProcedureTransitionExecutor()
    )

    await executor.handle(
        _context(),
        ctx,
    )

    assert ctx.outputs == []
    assert ctx.messages == []

    assert len(
        ctx.requests
    ) == 1

    request_data, response_type, request_id = (
        ctx.requests[0]
    )

    module = importlib.import_module(
        "src.workflows."
        "incident_resolution."
        "wait_recheck"
    )

    WaitRecheckRequest = getattr(
        module,
        "WaitRecheckRequest",
    )

    WaitRecheckSignal = getattr(
        module,
        "WaitRecheckSignal",
    )

    assert isinstance(
        request_data,
        WaitRecheckRequest,
    )

    assert (
        response_type
        is WaitRecheckSignal
    )

    assert request_id

    assert (
        request_data.recheck_id
        == request_id
    )

    stored = (
        ProcedureRuntimeState
        .model_validate(
            ctx.states[
                PROCEDURE_RUNTIME_STATE_KEY
            ]
        )
    )

    assert (
        stored.step_status
        == StepStatus.WAITING_VALIDATION
    )

    assert (
        stored.workflow_status
        == WorkflowStatus.WAITING_VALIDATION
    )

    assert (
        stored.approval_status
        == ApprovalStatus.APPROVED
    )

    assert (
        stored.operation_result
        is not None
    )

    assert (
        stored.verification_result
        is not None
    )

    assert (
        stored.recheck_count
        == 0
    )


@pytest.mark.asyncio
async def test_wait_rejects_request_when_next_recheck_would_exhaust_framework_budget():
    ctx = WaitWorkflowContext(
        _runtime_snapshot(
            total_steps=8,
            retry_count=0,
            recheck_count=1,
        )
    )

    executor = (
        ProcedureTransitionExecutor()
    )

    with pytest.raises(
        ValueError,
        match="iteration budget",
    ):
        await executor.handle(
            _context(),
            ctx,
        )

    assert ctx.requests == []
    assert ctx.messages == []
    assert ctx.outputs == []


def test_wait_response_route_targets_fresh_post_operation_observation():
    transition_path = Path(
        "src/workflows/"
        "incident_resolution/"
        "executors/"
        "procedure_transition.py"
    )

    workflow_path = Path(
        "src/workflows/"
        "incident_resolution/"
        "workflow.py"
    )

    transition_source = (
        transition_path
        .read_text(
            encoding="utf-8"
        )
        .replace(
            "\r\n",
            "\n",
        )
    )

    workflow_source = (
        workflow_path
        .read_text(
            encoding="utf-8"
        )
        .replace(
            "\r\n",
            "\n",
        )
    )

    transition_tree = ast.parse(
        transition_source,
        filename=str(
            transition_path
        ),
    )

    workflow_tree = ast.parse(
        workflow_source,
        filename=str(
            workflow_path
        ),
    )

    transition_class = None

    for node in transition_tree.body:
        if (
            isinstance(
                node,
                ast.ClassDef,
            )
            and node.name
            == "ProcedureTransitionExecutor"
        ):
            transition_class = node
            break

    assert transition_class is not None

    response_handlers = []

    for node in transition_class.body:
        if not isinstance(
            node,
            ast.AsyncFunctionDef,
        ):
            continue

        decorator_names = []

        for decorator in node.decorator_list:
            if isinstance(
                decorator,
                ast.Name,
            ):
                decorator_names.append(
                    decorator.id
                )

            elif isinstance(
                decorator,
                ast.Attribute,
            ):
                decorator_names.append(
                    decorator.attr
                )

        if (
            "response_handler"
            in decorator_names
        ):
            response_handlers.append(
                node
            )

    assert len(
        response_handlers
    ) == 1

    response_handler = (
        response_handlers[0]
    )

    target_values = []

    for node in ast.walk(
        response_handler
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if not isinstance(
            node.func,
            ast.Attribute,
        ):
            continue

        if (
            node.func.attr
            != "send_message"
        ):
            continue

        for keyword in node.keywords:
            if (
                keyword.arg
                == "target_id"
                and isinstance(
                    keyword.value,
                    ast.Constant,
                )
            ):
                target_values.append(
                    keyword.value.value
                )

    assert target_values == [
        "azure_vm_post_operation_observation"
    ]

    edges = []

    for node in ast.walk(
        workflow_tree
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if not isinstance(
            node.func,
            ast.Attribute,
        ):
            continue

        if node.func.attr != "add_edge":
            continue

        if len(node.args) < 2:
            continue

        source = node.args[0]
        target = node.args[1]

        if (
            isinstance(
                source,
                ast.Name,
            )
            and isinstance(
                target,
                ast.Name,
            )
        ):
            edges.append(
                (
                    source.id,
                    target.id,
                )
            )

    assert (
        "procedure_transition",
        "azure_vm_post_operation_observation",
    ) in edges

    assert (
        "only emits"
        not in workflow_source
    )