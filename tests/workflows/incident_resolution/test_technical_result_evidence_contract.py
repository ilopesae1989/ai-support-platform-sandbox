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

from src.workflows.incident_resolution.executors.azure_operations import (
    AzureOperationsExecutor,
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

from src.workflows.incident_resolution.technical_evidence import (
    McpResultEvidence,
    ResponseErrorEvidence,
    ToolResultEvidence,
)

from src.workflows.incident_resolution.tool_evidence import (
    ToolCallEvidence,
)


def create_response(
    *contents,
):
    return SimpleNamespace(
        messages=[
            SimpleNamespace(
                role="assistant",

                message_id="msg-technical-001",

                contents=list(
                    contents
                ),
            )
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


def create_evidence(
    *,
    tool_calls=None,
    mcp_calls=None,
    tool_results=None,
    mcp_results=None,
    response_errors=None,
):
    return OperationEvidence(
        operation_id="op-technical-001",

        workflow_id="wf-technical-001",

        approval_id="apr-technical-001",

        alert_id="ALT-TECHNICAL-001",

        correlation_id="corr-technical-001",

        conversation_id="conv-technical-001",

        procedure_id="PROC-TECHNICAL-001",

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

        tool_calls=(
            list(tool_calls or [])
        ),

        mcp_calls=(
            list(mcp_calls or [])
        ),

        tool_results=(
            list(tool_results or [])
        ),

        mcp_results=(
            list(mcp_results or [])
        ),

        response_errors=(
            list(response_errors or [])
        ),
    )


def create_result(
    evidence: OperationEvidence,
    *,
    success: bool = True,
    technical_success=None,
):
    return OperationResult(
        operation_id=evidence.operation_id,

        workflow_id=evidence.workflow_id,

        approval_id=evidence.approval_id,

        alert_id=evidence.alert_id,

        correlation_id=(
            evidence.correlation_id
        ),

        conversation_id=(
            evidence.conversation_id
        ),

        procedure_id=(
            evidence.procedure_id
        ),

        procedure_version=(
            evidence.procedure_version
        ),

        current_step=(
            evidence.current_step
        ),

        step_id=evidence.step_id,

        operation_domain=(
            evidence.operation_domain
        ),

        operation_kind=(
            evidence.operation_kind
        ),

        next_action=(
            evidence.next_action
        ),

        target_resource=(
            evidence.target_resource
        ),

        required_parameters=list(
            evidence.required_parameters
        ),

        resolved_parameters=[
            item.model_copy(
                deep=True
            )
            for item
            in evidence.resolved_parameters
        ],

        success=success,

        technical_success=(
            technical_success
        ),

        response_text="response",

        error=None,

        evidence=evidence,
    )


def tool_call(
    call_id="call-001",
):
    return ToolCallEvidence(
        tool_call_id=call_id,
        tool_name="tool_one",
        arguments={},
    )


def tool_result(
    call_id="call-001",
    *,
    exception=None,
):
    return ToolResultEvidence(
        tool_call_id=call_id,
        result_text='{"value": 42}',
        exception=exception,
    )


def mcp_call(
    call_id="mcp-001",
):
    return McpCallEvidence(
        mcp_call_id=call_id,
        server_name="azure-mcp",
        tool_name="tool_one",
        arguments={},
    )


def mcp_result(
    call_id="mcp-001",
):
    return McpResultEvidence(
        mcp_call_id=call_id,
        output={
            "status":
                "success",
        },
    )


def test_technical_result_models_have_exact_contracts():
    assert (
        tuple(
            ToolResultEvidence.model_fields
        )
        == (
            "tool_call_id",
            "result_text",
            "exception",
            "source_message_id",
            "source_message_role",
        )
    )

    assert (
        tuple(
            McpResultEvidence.model_fields
        )
        == (
            "mcp_call_id",
            "output",
            "source_message_id",
            "source_message_role",
        )
    )

    assert (
        tuple(
            ResponseErrorEvidence.model_fields
        )
        == (
            "message",
            "error_code",
            "error_details",
            "source_message_id",
            "source_message_role",
        )
    )


def test_extracts_successful_function_result():
    response = create_response(
        Content.from_function_result(
            call_id="call-001",

            result={
                "value":
                    42,
            },
        )
    )

    results = (
        AzureOperationsExecutor
        ._extract_tool_results(
            response
        )
    )

    assert len(results) == 1

    assert (
        results[0].tool_call_id
        == "call-001"
    )

    assert (
        results[0].exception
        is None
    )

    assert (
        '"value": 42'
        in results[0].result_text
    )


def test_extracts_failed_function_result():
    response = create_response(
        Content.from_function_result(
            call_id="call-001",

            result=None,

            exception=(
                "RuntimeError: failure"
            ),
        )
    )

    results = (
        AzureOperationsExecutor
        ._extract_tool_results(
            response
        )
    )

    assert (
        results[0].exception
        == "RuntimeError: failure"
    )


def test_extracts_mcp_result_without_inventing_success():
    response = create_response(
        Content.from_mcp_server_tool_result(
            call_id="mcp-001",

            output={
                "status":
                    "success",
            },
        )
    )

    results = (
        AzureOperationsExecutor
        ._extract_mcp_results(
            response
        )
    )

    assert len(results) == 1

    assert (
        results[0].output
        == {
            "status":
                "success",
        }
    )

    assert (
        "technical_success"
        not in McpResultEvidence.model_fields
    )


def test_extracts_structured_response_error():
    response = create_response(
        Content.from_error(
            message="provider failure",

            error_code="provider_error",

            error_details="details",
        )
    )

    errors = (
        AzureOperationsExecutor
        ._extract_response_errors(
            response
        )
    )

    assert len(errors) == 1

    assert (
        errors[0].error_code
        == "provider_error"
    )


def test_complete_function_call_and_result_derives_true():
    evidence = create_evidence(
        tool_calls=[
            tool_call(),
        ],

        tool_results=[
            tool_result(),
        ],
    )

    assert (
        evidence
        .derive_technical_success()
        is True
    )


def test_function_exception_derives_false():
    evidence = create_evidence(
        tool_calls=[
            tool_call(),
        ],

        tool_results=[
            tool_result(
                exception="failure"
            ),
        ],
    )

    assert (
        evidence
        .derive_technical_success()
        is False
    )


def test_missing_function_result_derives_unknown():
    evidence = create_evidence(
        tool_calls=[
            tool_call(),
        ]
    )

    assert (
        evidence
        .derive_technical_success()
        is None
    )


def test_mcp_result_remains_unknown_without_explicit_status_contract():
    evidence = create_evidence(
        mcp_calls=[
            mcp_call(),
        ],

        mcp_results=[
            mcp_result(),
        ],
    )

    assert (
        evidence
        .derive_technical_success()
        is None
    )


def test_response_error_derives_false():
    evidence = create_evidence(
        response_errors=[
            ResponseErrorEvidence(
                message="failure"
            )
        ]
    )

    assert (
        evidence
        .derive_technical_success()
        is False
    )


def test_orphan_success_result_is_preserved_but_unknown():
    evidence = create_evidence(
        tool_results=[
            tool_result(),
        ]
    )

    assert len(
        evidence.tool_results
    ) == 1

    assert (
        evidence
        .derive_technical_success()
        is None
    )


@pytest.mark.parametrize(
    (
        "field_name",
        "values",
        "match",
    ),
    [
        (
            "tool_results",
            [
                tool_result(
                    "duplicate"
                ),
                tool_result(
                    "duplicate"
                ),
            ],
            "tool result call_id duplicados",
        ),
        (
            "mcp_results",
            [
                mcp_result(
                    "duplicate"
                ),
                mcp_result(
                    "duplicate"
                ),
            ],
            "MCP result call_id duplicados",
        ),
    ],
)
def test_duplicate_result_ids_are_rejected(
    field_name,
    values,
    match,
):
    with pytest.raises(
        ValidationError,
        match=match,
    ):
        create_evidence(
            **{
                field_name:
                    values
            }
        )


def test_operation_result_rejects_inconsistent_technical_success():
    evidence = create_evidence(
        tool_calls=[
            tool_call(),
        ],

        tool_results=[
            tool_result(),
        ],
    )

    with pytest.raises(
        ValidationError,
        match="technical_success",
    ):
        create_result(
            evidence,
            technical_success=False,
        )


def test_transport_success_can_coexist_with_technical_failure():
    evidence = create_evidence(
        tool_calls=[
            tool_call(),
        ],

        tool_results=[
            tool_result(
                exception=(
                    "RuntimeError: failure"
                )
            ),
        ],
    )

    result = create_result(
        evidence,
        success=True,
        technical_success=False,
    )

    assert result.success is True

    assert (
        result.technical_success
        is False
    )
