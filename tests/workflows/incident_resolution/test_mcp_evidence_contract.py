from types import (
    SimpleNamespace,
)

import pytest

from agent_framework import (
    Content,
)

from pydantic import (
    ValidationError,
)

from src.runtime.procedure.models import (
    NextAction,
    OperationKind,
    ResolvedParameter,
)

from src.workflows.incident_resolution.azure_operations import (
    build_azure_operation_request,
)

from src.workflows.incident_resolution.executors.azure_operations import (
    AzureOperationsExecutor,
)

from src.workflows.incident_resolution.mcp_evidence import (
    McpCallEvidence,
)

from src.workflows.incident_resolution.operation_evidence import (
    OperationEvidence,
)

from src.workflows.incident_resolution.pre_call_security import (
    PreCallSecurityVerifier,
)

from tests.workflows.incident_resolution.test_operation_request_contract import (
    create_approved_step,
)


def create_response(
    *contents,
    message_id: str = "msg-mcp-001",
):
    message = SimpleNamespace(
        role="assistant",

        message_id=(
            message_id
        ),

        contents=list(
            contents
        ),
    )

    return SimpleNamespace(
        messages=[
            message,
        ]
    )


def resolved_parameters():
    return [
        ResolvedParameter(
            name="subscription_id",

            value="sub-001",

            source=(
                "normalized_alert."
                "subscription_id"
            ),
        )
    ]


def create_operation_evidence(
    *,
    mcp_calls=None,
) -> OperationEvidence:
    return OperationEvidence(
        operation_id="op-mcp-001",

        workflow_id="wf-mcp-001",

        approval_id="apr-mcp-001",

        alert_id="ALT-MCP-001",

        correlation_id="corr-mcp-001",

        conversation_id="conv-mcp-001",

        procedure_id="PROC-MCP-001",

        procedure_version="v1.0",

        current_step=1,

        step_id="1",

        operation_domain="azure",

        operation_kind=(
            OperationKind.READ
        ),

        next_action=(
            NextAction.EXECUTE_STEP
        ),

        target_resource="subscription",

        required_parameters=[
            "subscription_id",
        ],

        resolved_parameters=(
            resolved_parameters()
        ),

        mcp_calls=(
            list(mcp_calls)
            if mcp_calls
            is not None
            else []
        ),
    )


def test_mcp_call_evidence_contains_exact_phase_15_10_contract():
    assert (
        tuple(
            McpCallEvidence.model_fields
        )
        == (
            "mcp_call_id",
            "server_name",
            "tool_name",
            "arguments",
            "source_message_id",
            "source_message_role",
        )
    )


def test_mcp_call_evidence_rejects_phase_15_11_fields():
    with pytest.raises(
        ValidationError,
    ):
        McpCallEvidence(
            mcp_call_id="mcp-call-001",

            server_name="azure-mcp",

            tool_name="list_resource_groups",

            arguments={},

            output={
                "value": [],
            },
        )


def test_extracts_mcp_call_identity_server_tool_arguments_and_metadata():
    content = (
        Content.from_mcp_server_tool_call(
            call_id="mcp-call-001",

            tool_name="list_resource_groups",

            server_name="azure-mcp",

            arguments={
                "subscription_id":
                    "sub-001",
            },
        )
    )

    assert (
        content.type
        == "mcp_server_tool_call"
    )

    assert (
        content.informational_only
        is True
    )

    response = (
        create_response(
            content,

            message_id="msg-mcp-001",
        )
    )

    calls = (
        AzureOperationsExecutor
        ._extract_mcp_calls(
            response
        )
    )

    assert len(calls) == 1

    call = calls[0]

    assert (
        call.mcp_call_id
        == "mcp-call-001"
    )

    assert (
        call.server_name
        == "azure-mcp"
    )

    assert (
        call.tool_name
        == "list_resource_groups"
    )

    assert (
        call.arguments
        == {
            "subscription_id":
                "sub-001",
        }
    )

    assert (
        call.source_message_id
        == "msg-mcp-001"
    )

    assert (
        call.source_message_role
        == "assistant"
    )


def test_extracts_mcp_json_string_arguments():
    response = (
        create_response(
            Content.from_mcp_server_tool_call(
                call_id="mcp-call-002",

                tool_name="mcp_test",

                server_name="azure-mcp",

                arguments=(
                    '{"subscription_id":'
                    '"sub-001"}'
                ),
            )
        )
    )

    calls = (
        AzureOperationsExecutor
        ._extract_mcp_calls(
            response
        )
    )

    assert (
        calls[0].arguments
        == {
            "subscription_id":
                "sub-001",
        }
    )


def test_multiple_mcp_calls_are_preserved_in_order():
    response = (
        create_response(
            Content.from_mcp_server_tool_call(
                call_id="mcp-call-001",

                tool_name="tool_one",

                server_name="azure-mcp",

                arguments={
                    "value": 1,
                },
            ),

            Content.from_mcp_server_tool_call(
                call_id="mcp-call-002",

                tool_name="tool_two",

                server_name="azure-mcp",

                arguments={
                    "value": 2,
                },
            ),
        )
    )

    calls = (
        AzureOperationsExecutor
        ._extract_mcp_calls(
            response
        )
    )

    assert [
        call.mcp_call_id
        for call
        in calls
    ] == [
        "mcp-call-001",
        "mcp-call-002",
    ]


def test_mcp_results_are_not_captured_in_phase_15_10():
    response = (
        create_response(
            Content.from_mcp_server_tool_result(
                call_id="mcp-call-001",

                output={
                    "status":
                        "success",
                },
            )
        )
    )

    calls = (
        AzureOperationsExecutor
        ._extract_mcp_calls(
            response
        )
    )

    assert calls == []


def test_mcp_call_is_not_misclassified_as_function_tool_call():
    response = (
        create_response(
            Content.from_mcp_server_tool_call(
                call_id="mcp-call-001",

                tool_name="tool_one",

                server_name="azure-mcp",

                arguments={},
            )
        )
    )

    assert (
        AzureOperationsExecutor
        ._extract_tool_calls(
            response
        )
        == []
    )


def test_operation_evidence_defaults_to_no_mcp_calls():
    evidence = (
        create_operation_evidence()
    )

    assert (
        evidence.mcp_calls
        == []
    )


def test_operation_evidence_rejects_duplicate_mcp_call_ids():
    first = McpCallEvidence(
        mcp_call_id="mcp-duplicate",

        server_name="azure-mcp",

        tool_name="tool_one",

        arguments={},
    )

    second = McpCallEvidence(
        mcp_call_id="mcp-duplicate",

        server_name="azure-mcp",

        tool_name="tool_two",

        arguments={},
    )

    with pytest.raises(
        ValidationError,
        match="mcp_call_id duplicados",
    ):
        create_operation_evidence(
            mcp_calls=[
                first,
                second,
            ]
        )


def test_mcp_evidence_is_bound_to_verified_operation_identity():
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

    response = (
        create_response(
            Content.from_mcp_server_tool_call(
                call_id="mcp-bound-001",

                tool_name="azure_operation",

                server_name="azure-mcp",

                arguments={
                    "subscription_id":
                        (
                            verified
                            .resolved_parameters[
                                0
                            ]
                            .value
                        ),
                },
            )
        )
    )

    evidence = (
        AzureOperationsExecutor
        ._build_operation_evidence(
            verified,
            response,
        )
    )

    assert evidence is not None

    assert (
        evidence.operation_id
        == verified.operation_id
    )

    assert (
        evidence.workflow_id
        == verified.workflow_id
    )

    assert (
        evidence.approval_id
        == verified.approval_id
    )

    assert (
        evidence.alert_id
        == verified.alert_id
    )

    assert (
        evidence.procedure_id
        == verified.procedure_id
    )

    assert (
        evidence.step_id
        == verified.step_id
    )

    assert (
        evidence.tool_calls
        == []
    )

    assert len(
        evidence.mcp_calls
    ) == 1

    assert (
        evidence.mcp_calls[
            0
        ].mcp_call_id
        == "mcp-bound-001"
    )


def test_mcp_server_name_can_be_absent_when_framework_does_not_supply_it():
    response = (
        create_response(
            Content.from_mcp_server_tool_call(
                call_id="mcp-call-no-server",

                tool_name="tool_one",

                arguments={},
            )
        )
    )

    calls = (
        AzureOperationsExecutor
        ._extract_mcp_calls(
            response
        )
    )

    assert len(calls) == 1

    assert (
        calls[0].server_name
        is None
    )
