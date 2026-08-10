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

from src.workflows.incident_resolution.azure_operations import (
    build_azure_operation_request,
)

from src.workflows.incident_resolution.executors.azure_operations import (
    AzureOperationsExecutor,
)

from src.workflows.incident_resolution.operation_evidence import (
    OperationEvidence,
)

from src.workflows.incident_resolution.pre_call_security import (
    PreCallSecurityVerifier,
)

from src.workflows.incident_resolution.tool_evidence import (
    ToolCallEvidence,
)

from tests.workflows.incident_resolution.test_operation_request_contract import (
    create_approved_step,
)


def create_function_response(
    *contents,
    message_id: str = "msg-tool-001",
):
    """
    Fake mínimo del contrato estructural consumido
    por AzureOperationsExecutor._extract_tool_calls().

    No acoplamos este test a una clase concreta de
    respuesta del Agent Framework.

    FunctionCallContent sí permanece real porque es
    precisamente el contrato que estamos probando.
    """

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


def create_operation_evidence(
    *,
    tool_calls=None,
) -> OperationEvidence:
    return OperationEvidence(
        operation_id="op-tool-001",

        workflow_id="wf-tool-001",

        approval_id="apr-tool-001",

        alert_id="ALT-TOOL-001",

        correlation_id="corr-tool-001",

        conversation_id="conv-tool-001",

        procedure_id="PROC-TOOL-001",

        procedure_version="v1.0",

        current_step=1,

        step_id="1",

        operation_domain="azure",

        operation_kind="read",

        next_action="execute_step",

        target_resource="subscription",

        required_parameters=[
            "subscription_id",
        ],

        resolved_parameters=[
            {
                "name":
                    "subscription_id",

                "value":
                    "sub-001",

                "source":
                    (
                        "normalized_alert."
                        "subscription_id"
                    ),
            }
        ],

        tool_calls=(
            list(tool_calls)
            if tool_calls
            is not None
            else []
        ),
    )


def test_tool_call_evidence_contains_exact_phase_15_9_contract():
    assert (
        tuple(
            ToolCallEvidence.model_fields
        )
        == (
            "tool_call_id",
            "tool_name",
            "arguments",
            "source_message_id",
            "source_message_role",
        )
    )


def test_tool_call_evidence_rejects_later_phase_fields():
    with pytest.raises(
        ValidationError,
    ):
        ToolCallEvidence(
            tool_call_id="call-001",

            tool_name="azure_test",

            arguments={},

            mcp_call_id="mcp-001",
        )


def test_extracts_function_call_identity_arguments_and_metadata():
    response = (
        create_function_response(
            Content.from_function_call(
                call_id="call-001",

                name=(
                    "azure_list_"
                    "resource_groups"
                ),

                arguments={
                    "subscription_id":
                        "sub-001",
                },
            ),

            message_id="msg-001",
        )
    )

    calls = (
        AzureOperationsExecutor
        ._extract_tool_calls(
            response
        )
    )

    assert len(calls) == 1

    call = calls[0]

    assert (
        call.tool_call_id
        == "call-001"
    )

    assert (
        call.tool_name
        == (
            "azure_list_"
            "resource_groups"
        )
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
        == "msg-001"
    )

    assert (
        call.source_message_role
        == "assistant"
    )


def test_extracts_json_string_arguments():
    response = (
        create_function_response(
            Content.from_function_call(
                call_id="call-002",

                name="azure_test",

                arguments=(
                    '{"subscription_id":'
                    '"sub-001"}'
                ),
            )
        )
    )

    calls = (
        AzureOperationsExecutor
        ._extract_tool_calls(
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


def test_multiple_tool_calls_are_preserved_in_order():
    response = (
        create_function_response(
            Content.from_function_call(
                call_id="call-001",
                name="tool_one",
                arguments={
                    "value": 1,
                },
            ),

            Content.from_function_call(
                call_id="call-002",
                name="tool_two",
                arguments={
                    "value": 2,
                },
            ),
        )
    )

    calls = (
        AzureOperationsExecutor
        ._extract_tool_calls(
            response
        )
    )

    assert [
        call.tool_call_id
        for call
        in calls
    ] == [
        "call-001",
        "call-002",
    ]


def test_non_function_call_contents_are_not_captured_in_phase_15_9():
    """
    FASE 15.9 captura exclusivamente Content
    con type=function_call.

    function_result pertenece a FASE 15.11.
    """

    response = (
        create_function_response(
            Content.from_text(
                "operation completed"
            ),

            Content.from_function_result(
                call_id="call-001",

                result={
                    "status":
                        "success",
                },
            ),
        )
    )

    calls = (
        AzureOperationsExecutor
        ._extract_tool_calls(
            response
        )
    )

    assert calls == []


def test_operation_evidence_defaults_to_no_tool_calls():
    evidence = (
        create_operation_evidence()
    )

    assert (
        evidence.tool_calls
        == []
    )


def test_operation_evidence_rejects_duplicate_tool_call_ids():
    first = ToolCallEvidence(
        tool_call_id="call-duplicate",

        tool_name="tool_one",

        arguments={},
    )

    second = ToolCallEvidence(
        tool_call_id="call-duplicate",

        tool_name="tool_two",

        arguments={},
    )

    with pytest.raises(
        ValidationError,
        match="duplicados",
    ):
        create_operation_evidence(
            tool_calls=[
                first,
                second,
            ]
        )


def test_tool_evidence_is_bound_to_verified_operation_identity():
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
        create_function_response(
            Content.from_function_call(
                call_id="call-bound-001",

                name="azure_operation",

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

    assert len(
        evidence.tool_calls
    ) == 1

    assert (
        evidence.tool_calls[
            0
        ].tool_call_id
        == "call-bound-001"
    )
