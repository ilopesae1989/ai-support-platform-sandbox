import json

from types import SimpleNamespace

import pytest

from src.runtime.procedure.models import (
    NextAction,
    OperationAction,
    OperationKind,
)

from src.workflows.incident_resolution.azure_operations_models import (
    VerifiedAzureOperationRequest,
    VerifiedResolvedParameter,
)

from src.workflows.incident_resolution.executors.azure_operations import (
    AzureOperationsExecutor,
)


SERVER_LABEL = "azure-mcp-operations-sbx"

APPROVAL_REQUEST_ID = (
    "mcpr-test-001"
)

RESPONSE_ID = (
    "resp-test-001"
)


def _verified_vm_start_request(
) -> VerifiedAzureOperationRequest:
    return VerifiedAzureOperationRequest(
        operation_id="op-vm-start-001",

        workflow_id="wf-vm-start-001",

        approval_id=(
            "apr-11111111-1111-4111-"
            "8111-111111111111"
        ),

        alert_id="ALT-VM-START-001",

        correlation_id="corr-vm-start-001",

        conversation_id="conv-vm-start-001",

        procedure_id="TEST-PROC-VM-START",

        procedure_version="1.0",

        current_step=1,

        step_id="1",

        description=(
            "Encender la máquina virtual "
            "autorizada."
        ),

        operation_domain="azure",

        operation_kind=OperationKind.WRITE,

        operation_action=(
            OperationAction.VM_START
        ),

        capability_id="azure.vm.start",

        hitl_required=True,

        next_action=(
            NextAction.EXECUTE_STEP
        ),

        target_resource=(
            "/subscriptions/sub-001/"
            "resourceGroups/rg-demo/"
            "providers/Microsoft.Compute/"
            "virtualMachines/vm-demo"
        ),

        required_parameters=[
            "subscription_id",
            "resource_group",
            "vm_name",
        ],

        resolved_parameters=[
            VerifiedResolvedParameter(
                name="subscription_id",
                value="sub-001",
                source=(
                    "normalized_alert."
                    "subscription_id"
                ),
            ),

            VerifiedResolvedParameter(
                name="resource_group",
                value="rg-demo",
                source=(
                    "normalized_alert."
                    "resource_group"
                ),
            ),

            VerifiedResolvedParameter(
                name="vm_name",
                value="vm-demo",
                source=(
                    "normalized_alert."
                    "vm_name"
                ),
            ),
        ],

        security_verified=True,

        verification_source=(
            "pre_call_security_verifier"
        ),
    )


def _approval(
    *,
    server_label=SERVER_LABEL,
    tool_name="compute_vm-power-state",
    arguments=None,
):
    if arguments is None:
        arguments = {
            "subscription": "sub-001",
            "resource-group": "rg-demo",
            "vm-name": "vm-demo",
            "power-action": "start",
        }

    return SimpleNamespace(
        approval_request_id=(
            APPROVAL_REQUEST_ID
        ),

        response_id=RESPONSE_ID,

        server_label=server_label,

        tool_name=tool_name,

        arguments=dict(arguments),
    )


def _native_response(
    *,
    approvals=None,
):
    if approvals is None:
        approvals = [
            {
                "id": APPROVAL_REQUEST_ID,
                "response_id": RESPONSE_ID,
                "server_label": SERVER_LABEL,
                "name": (
                    "compute_vm-power-state"
                ),
                "arguments": json.dumps(
                    {
                        "subscription": "sub-001",
                        "resource-group": "rg-demo",
                        "vm-name": "vm-demo",
                        "power-action": "start",
                    }
                ),
            }
        ]

    output = [
        SimpleNamespace(
            type="mcp_approval_request",
            **item,
        )
        for item in approvals
    ]

    raw_response = SimpleNamespace(
        id=RESPONSE_ID,
        output=output,
    )

    return SimpleNamespace(
        raw_response=raw_response,
    )


def test_extract_mcp_approval_request_preserves_native_identity():
    response = _native_response()

    approvals = (
        AzureOperationsExecutor
        ._extract_mcp_approval_requests(
            response
        )
    )

    assert len(approvals) == 1

    approval = approvals[0]

    assert (
        approval.approval_request_id
        == APPROVAL_REQUEST_ID
    )

    assert (
        approval.response_id
        == RESPONSE_ID
    )

    assert (
        approval.server_label
        == SERVER_LABEL
    )

    assert (
        approval.tool_name
        == "compute_vm-power-state"
    )

    assert approval.arguments == {
        "subscription": "sub-001",
        "resource-group": "rg-demo",
        "vm-name": "vm-demo",
        "power-action": "start",
    }


def test_extract_rejects_invalid_approval_arguments_json():
    response = _native_response(
        approvals=[
            {
                "id": APPROVAL_REQUEST_ID,
                "response_id": RESPONSE_ID,
                "server_label": SERVER_LABEL,
                "name": (
                    "compute_vm-power-state"
                ),
                "arguments": "{not-json",
            }
        ]
    )

    with pytest.raises(
        ValueError
    ):
        (
            AzureOperationsExecutor
            ._extract_mcp_approval_requests(
                response
            )
        )


def test_write_requires_exactly_one_mcp_approval():
    response = _native_response(
        approvals=[]
    )

    with pytest.raises(
        ValueError
    ):
        (
            AzureOperationsExecutor
            ._extract_single_mcp_approval_request(
                response
            )
        )


def test_valid_vm_start_approval_is_accepted():
    request = (
        _verified_vm_start_request()
    )

    approval = _approval()

    (
        AzureOperationsExecutor
        ._validate_mcp_approval_request(
            request,
            approval,
        )
    )


def test_rejects_wrong_mcp_server():
    request = (
        _verified_vm_start_request()
    )

    approval = _approval(
        server_label="attacker-mcp"
    )

    with pytest.raises(
        ValueError
    ):
        (
            AzureOperationsExecutor
            ._validate_mcp_approval_request(
                request,
                approval,
            )
        )


def test_rejects_wrong_mcp_tool():
    request = (
        _verified_vm_start_request()
    )

    approval = _approval(
        tool_name="compute_vm_delete"
    )

    with pytest.raises(
        ValueError
    ):
        (
            AzureOperationsExecutor
            ._validate_mcp_approval_request(
                request,
                approval,
            )
        )


@pytest.mark.parametrize(
    "power_action",
    [
        "stop",
        "deallocate",
        "restart",
    ],
)
def test_rejects_non_start_power_action(
    power_action,
):
    request = (
        _verified_vm_start_request()
    )

    approval = _approval(
        arguments={
            "subscription": "sub-001",
            "resource-group": "rg-demo",
            "vm-name": "vm-demo",
            "power-action": power_action,
        }
    )

    with pytest.raises(
        ValueError
    ):
        (
            AzureOperationsExecutor
            ._validate_mcp_approval_request(
                request,
                approval,
            )
        )


def test_rejects_different_vm():
    request = (
        _verified_vm_start_request()
    )

    approval = _approval(
        arguments={
            "subscription": "sub-001",
            "resource-group": "rg-demo",
            "vm-name": "vm-attacker",
            "power-action": "start",
        }
    )

    with pytest.raises(
        ValueError
    ):
        (
            AzureOperationsExecutor
            ._validate_mcp_approval_request(
                request,
                approval,
            )
        )


def test_rejects_different_subscription():
    request = (
        _verified_vm_start_request()
    )

    approval = _approval(
        arguments={
            "subscription": "sub-attacker",
            "resource-group": "rg-demo",
            "vm-name": "vm-demo",
            "power-action": "start",
        }
    )

    with pytest.raises(
        ValueError
    ):
        (
            AzureOperationsExecutor
            ._validate_mcp_approval_request(
                request,
                approval,
            )
        )


def test_rejects_unapproved_extra_argument():
    request = (
        _verified_vm_start_request()
    )

    approval = _approval(
        arguments={
            "subscription": "sub-001",
            "resource-group": "rg-demo",
            "vm-name": "vm-demo",
            "power-action": "start",

            # Aunque Azure MCP lo soporta,
            # no fue aprobado en HITL.
            "no-wait": True,
        }
    )

    with pytest.raises(
        ValueError
    ):
        (
            AzureOperationsExecutor
            ._validate_mcp_approval_request(
                request,
                approval,
            )
        )


# ============================================================
# GREEN 2B - executor/session/approval integration
# ============================================================

from agent_framework import (
    WorkflowBuilder,
)

from src.workflows.incident_resolution.operation_dispatch_ledger import (
    InMemoryOperationDispatchLedger,
)


class _NativeApprovalRequest:
    """
    Representación mínima de
    AgentResponse.user_input_requests.

    Se mantiene separada del raw_response porque
    Agent Framework usa este Content nativo para
    generar posteriormente la approval response.
    """

    def __init__(
        self,
        *,
        server_label=SERVER_LABEL,
        tool_name="compute_vm-power-state",
        arguments=None,
    ) -> None:
        if arguments is None:
            arguments = {
                "subscription": "sub-001",
                "resource-group": "rg-demo",
                "vm-name": "vm-demo",
                "power-action": "start",
            }

        self.function_call = (
            SimpleNamespace(
                name=tool_name,
                arguments=json.dumps(
                    arguments
                ),
            )
        )

        self.additional_properties = {
            "server_label":
                server_label
        }


def _first_approval_response(
    *,
    raw_server_label=SERVER_LABEL,
    raw_tool_name="compute_vm-power-state",
    raw_arguments=None,
    native_server_label=None,
    native_tool_name=None,
    native_arguments=None,
):
    if raw_arguments is None:
        raw_arguments = {
            "subscription": "sub-001",
            "resource-group": "rg-demo",
            "vm-name": "vm-demo",
            "power-action": "start",
        }

    if native_server_label is None:
        native_server_label = (
            raw_server_label
        )

    if native_tool_name is None:
        native_tool_name = (
            raw_tool_name
        )

    if native_arguments is None:
        native_arguments = dict(
            raw_arguments
        )

    native_request = (
        _NativeApprovalRequest(
            server_label=(
                native_server_label
            ),
            tool_name=(
                native_tool_name
            ),
            arguments=(
                native_arguments
            ),
        )
    )

    raw_approval = SimpleNamespace(
        type="mcp_approval_request",

        id=APPROVAL_REQUEST_ID,

        response_id=RESPONSE_ID,

        server_label=(
            raw_server_label
        ),

        name=raw_tool_name,

        arguments=json.dumps(
            raw_arguments
        ),
    )

    raw_response = (
        SimpleNamespace(
            id=RESPONSE_ID,
            output=[
                raw_approval
            ],
        )
    )

    response = (
        SimpleNamespace(
            raw_response=raw_response,
            user_input_requests=[
                native_request
            ],
            text=None,
            messages=[],
        )
    )

    return (
        response,
        native_request,
    )


def _final_success_response():
    return SimpleNamespace(
        text="VM Start ejecutado.",
        messages=[],
        user_input_requests=[],
        raw_response=(
            SimpleNamespace(
                id="resp-final-001",
                output=[],
            )
        ),
    )


class _FakeAzureOperationsAgents:
    def __init__(
        self,
        first_response,
    ) -> None:
        self.first_response = (
            first_response
        )

        self.final_response = (
            _final_success_response()
        )

        self.begin_calls = []
        self.continue_calls = []
        self.legacy_calls = []

        self.invocation = (
            SimpleNamespace(
                response=(
                    self.first_response
                )
            )
        )

    async def begin_azure_operations(
        self,
        message: str,
    ):
        self.begin_calls.append(
            message
        )

        return self.invocation

    async def continue_azure_operations(
        self,
        *,
        invocation,
        approval_request,
        approved,
    ):
        self.continue_calls.append(
            {
                "invocation":
                    invocation,

                "approval_request":
                    approval_request,

                "approved":
                    approved,
            }
        )

        return SimpleNamespace(
            response=(
                self.final_response
            )
        )

    async def run_azure_operations(
        self,
        message: str,
    ):
        self.legacy_calls.append(
            message
        )

        raise AssertionError(
            "GREEN 2B no debe usar "
            "run_azure_operations() para "
            "WRITE gobernado."
        )


def _build_integration_workflow(
    *,
    agents,
    ledger,
):
    executor = (
        AzureOperationsExecutor(
            agents=agents,
            operation_dispatch_ledger=(
                ledger
            ),
        )
    )

    return (
        WorkflowBuilder(
            start_executor=executor,
            output_from=[
                executor
            ],
            name=(
                "azure-mcp-approval-"
                "integration-test"
            ),
        )
        .build()
    )


async def _run_integration(
    *,
    agents,
    ledger,
):
    workflow = (
        _build_integration_workflow(
            agents=agents,
            ledger=ledger,
        )
    )

    request = (
        _verified_vm_start_request()
    )

    outputs = []

    async for event in workflow.run(
        request,
        stream=True,
    ):
        if event.type == "output":
            outputs.append(
                event.data
            )

    return (
        request,
        outputs,
    )


@pytest.mark.asyncio
async def test_executor_uses_one_dispatch_claim_and_continues_valid_mcp_approval():
    (
        first_response,
        native_request,
    ) = (
        _first_approval_response()
    )

    agents = (
        _FakeAzureOperationsAgents(
            first_response
        )
    )

    ledger = (
        InMemoryOperationDispatchLedger()
    )

    request, outputs = (
        await _run_integration(
            agents=agents,
            ledger=ledger,
        )
    )

    assert (
        ledger.count()
        == 1
    )

    assert (
        ledger.contains(
            request.operation_id
        )
        is True
    )

    assert len(
        agents.begin_calls
    ) == 1

    assert (
        agents.legacy_calls
        == []
    )

    assert len(
        agents.continue_calls
    ) == 1

    continuation = (
        agents.continue_calls[0]
    )

    assert (
        continuation[
            "invocation"
        ]
        is agents.invocation
    )

    assert (
        continuation[
            "approval_request"
        ]
        is native_request
    )

    assert (
        continuation[
            "approved"
        ]
        is True
    )

    assert len(outputs) == 1

    result = outputs[0]

    assert (
        result.success
        is True
    )

    assert (
        result.response_text
        == "VM Start ejecutado."
    )


@pytest.mark.asyncio
async def test_executor_does_not_continue_when_mcp_power_action_is_tampered():
    (
        first_response,
        _
    ) = (
        _first_approval_response(
            raw_arguments={
                "subscription":
                    "sub-001",

                "resource-group":
                    "rg-demo",

                "vm-name":
                    "vm-demo",

                "power-action":
                    "stop",
            }
        )
    )

    agents = (
        _FakeAzureOperationsAgents(
            first_response
        )
    )

    ledger = (
        InMemoryOperationDispatchLedger()
    )

    request, outputs = (
        await _run_integration(
            agents=agents,
            ledger=ledger,
        )
    )

    # La operación ya cruzó la frontera
    # monotónica de dispatch.
    assert (
        ledger.count()
        == 1
    )

    assert (
        ledger.contains(
            request.operation_id
        )
        is True
    )

    assert len(
        agents.begin_calls
    ) == 1

    # FAIL CLOSED:
    # nunca se concede la aprobación.
    assert (
        agents.continue_calls
        == []
    )

    assert (
        agents.legacy_calls
        == []
    )

    assert len(outputs) == 1

    assert (
        outputs[0].success
        is False
    )


@pytest.mark.asyncio
async def test_executor_rejects_mismatch_between_raw_and_native_approval():
    (
        first_response,
        _
    ) = (
        _first_approval_response(
            raw_tool_name=(
                "compute_vm-power-state"
            ),

            native_tool_name=(
                "group_resource_list"
            ),
        )
    )

    agents = (
        _FakeAzureOperationsAgents(
            first_response
        )
    )

    ledger = (
        InMemoryOperationDispatchLedger()
    )

    _, outputs = (
        await _run_integration(
            agents=agents,
            ledger=ledger,
        )
    )

    assert (
        ledger.count()
        == 1
    )

    assert len(
        agents.begin_calls
    ) == 1

    assert (
        agents.continue_calls
        == []
    )

    assert (
        agents.legacy_calls
        == []
    )

    assert len(outputs) == 1

    assert (
        outputs[0].success
        is False
    )


@pytest.mark.asyncio
async def test_executor_rejects_missing_native_user_input_request():
    (
        first_response,
        _
    ) = (
        _first_approval_response()
    )

    first_response.user_input_requests = []

    agents = (
        _FakeAzureOperationsAgents(
            first_response
        )
    )

    ledger = (
        InMemoryOperationDispatchLedger()
    )

    _, outputs = (
        await _run_integration(
            agents=agents,
            ledger=ledger,
        )
    )

    assert (
        ledger.count()
        == 1
    )

    assert len(
        agents.begin_calls
    ) == 1

    assert (
        agents.continue_calls
        == []
    )

    assert (
        agents.legacy_calls
        == []
    )

    assert len(outputs) == 1

    assert (
        outputs[0].success
        is False
    )


def test_extract_mcp_approval_request_from_agent_framework_raw_representation():
    """
    Reproduce el shape observado LIVE con
    Agent Framework 1.13.0:

    AgentResponse
      -> raw_representation: ChatResponse
          -> raw_representation: OpenAI Response
              -> output
                  -> mcp_approval_request

    El extractor gobernado debe alcanzar el
    OpenAI Response real sin reconstruir ni
    inventar identidad MCP.
    """

    raw_approval = SimpleNamespace(
        type="mcp_approval_request",
        id=APPROVAL_REQUEST_ID,
        server_label=SERVER_LABEL,
        name="compute_vm-power-state",
        arguments=json.dumps(
            {
                "subscription": "sub-001",
                "resource-group": "rg-demo",
                "vm-name": "vm-demo",
                "power-action": "start",
            }
        ),
    )

    openai_response = SimpleNamespace(
        id=RESPONSE_ID,
        output=[
            raw_approval
        ],
    )

    chat_response = SimpleNamespace(
        raw_representation=(
            openai_response
        ),
    )

    agent_response = SimpleNamespace(
        response_id=RESPONSE_ID,
        raw_representation=(
            chat_response
        ),
    )

    approvals = (
        AzureOperationsExecutor
        ._extract_mcp_approval_requests(
            agent_response
        )
    )

    assert len(approvals) == 1

    approval = approvals[0]

    assert (
        approval.approval_request_id
        == APPROVAL_REQUEST_ID
    )

    assert (
        approval.response_id
        == RESPONSE_ID
    )

    assert (
        approval.server_label
        == SERVER_LABEL
    )

    assert (
        approval.tool_name
        == "compute_vm-power-state"
    )

    assert approval.arguments == {
        "subscription": "sub-001",
        "resource-group": "rg-demo",
        "vm-name": "vm-demo",
        "power-action": "start",
    }


def test_extract_mcp_approval_request_rejects_raw_representation_response_id_mismatch():
    """
    Agent Framework y OpenAI Response deben referirse
    exactamente a la misma response.

    Una discrepancia de identidad se rechaza
    fail-closed antes de aprobar MCP.
    """

    raw_approval = SimpleNamespace(
        type="mcp_approval_request",
        id=APPROVAL_REQUEST_ID,
        server_label=SERVER_LABEL,
        name="compute_vm-power-state",
        arguments=json.dumps(
            {
                "subscription": "sub-001",
                "resource-group": "rg-demo",
                "vm-name": "vm-demo",
                "power-action": "start",
            }
        ),
    )

    openai_response = SimpleNamespace(
        id="resp-raw-different",
        output=[
            raw_approval
        ],
    )

    chat_response = SimpleNamespace(
        raw_representation=(
            openai_response
        ),
    )

    agent_response = SimpleNamespace(
        response_id=RESPONSE_ID,
        raw_representation=(
            chat_response
        ),
    )

    with pytest.raises(
        ValueError,
        match="identidad de la response MCP",
    ):
        (
            AzureOperationsExecutor
            ._extract_mcp_approval_requests(
                agent_response
            )
        )
