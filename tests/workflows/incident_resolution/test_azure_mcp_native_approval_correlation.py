import json

from types import SimpleNamespace

import pytest

from src.workflows.incident_resolution.executors.azure_operations import (
    AzureOperationsExecutor,
    McpApprovalRequest,
)


APPROVAL_REQUEST_ID = (
    "mcpr-live-shape-001"
)

RESPONSE_ID = (
    "resp-live-shape-001"
)

SERVER_LABEL = (
    "azure-mcp-operations-sbx"
)

TOOL_NAME = (
    "compute_vm_power-state"
)

ARGUMENTS = {
    "subscription":
        "557fdabc-f3b6-4c24-a9ae-e9e89b5ad172",

    "resource-group":
        "rg-icenter-sandbox-vm-demo",

    "vm-name":
        "vm-icenter-sbx-demo-01",

    "power-action":
        "start",
}


def _approval():
    return McpApprovalRequest(
        approval_request_id=(
            APPROVAL_REQUEST_ID
        ),

        response_id=(
            RESPONSE_ID
        ),

        server_label=(
            SERVER_LABEL
        ),

        tool_name=(
            TOOL_NAME
        ),

        arguments=dict(
            ARGUMENTS
        ),
    )


def _native_response(
    *,
    native_id=APPROVAL_REQUEST_ID,
    call_id=APPROVAL_REQUEST_ID,
    server_label=SERVER_LABEL,
):
    function_call = SimpleNamespace(
        type="function_call",

        id=None,

        call_id=call_id,

        name=TOOL_NAME,

        arguments=json.dumps(
            ARGUMENTS
        ),

        additional_properties={
            "server_label":
                server_label
        },
    )

    native_request = SimpleNamespace(
        type="function_approval_request",

        id=native_id,

        call_id=None,

        function_call=function_call,

        additional_properties={},

        to_function_approval_response=(
            lambda approved:
                SimpleNamespace(
                    approved=approved
                )
        ),
    )

    response = SimpleNamespace(
        user_input_requests=[
            native_request
        ]
    )

    return (
        response,
        native_request,
    )


def test_correlates_live_agent_framework_native_mcp_approval_shape():
    """
    Reproduce exactamente el shape observado LIVE
    con Agent Framework 1.13.0.

    server_label NO vive en:

        native_request.additional_properties

    sino en:

        native_request
            .function_call
            .additional_properties
            ["server_label"]

    La identidad MCP se correlaciona además:

        RAW approval_request_id
            ==
        native_request.id
            ==
        function_call.call_id
    """

    (
        response,
        native_request,
    ) = _native_response()

    correlated = (
        AzureOperationsExecutor
        ._extract_correlated_native_mcp_approval_request(
            response,
            _approval(),
        )
    )

    assert (
        correlated
        is native_request
    )


def test_rejects_native_request_id_mismatch():
    (
        response,
        _
    ) = _native_response(
        native_id=(
            "mcpr-attacker-native-id"
        )
    )

    with pytest.raises(
        ValueError,
        match="native id",
    ):
        (
            AzureOperationsExecutor
            ._extract_correlated_native_mcp_approval_request(
                response,
                _approval(),
            )
        )


def test_rejects_function_call_id_mismatch():
    (
        response,
        _
    ) = _native_response(
        call_id=(
            "mcpr-attacker-call-id"
        )
    )

    with pytest.raises(
        ValueError,
        match="call_id",
    ):
        (
            AzureOperationsExecutor
            ._extract_correlated_native_mcp_approval_request(
                response,
                _approval(),
            )
        )


def test_rejects_function_call_server_label_mismatch():
    (
        response,
        _
    ) = _native_response(
        server_label=(
            "attacker-mcp"
        )
    )

    with pytest.raises(
        ValueError,
        match="server_label",
    ):
        (
            AzureOperationsExecutor
            ._extract_correlated_native_mcp_approval_request(
                response,
                _approval(),
            )
        )