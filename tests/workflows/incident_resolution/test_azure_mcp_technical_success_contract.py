import json

from src.runtime.procedure.models import (
    NextAction,
    OperationKind,
    ResolvedParameter,
)

from src.workflows.incident_resolution.mcp_evidence import (
    McpCallEvidence,
)

from src.workflows.incident_resolution.operation_evidence import (
    OperationEvidence,
)

from src.workflows.incident_resolution.technical_evidence import (
    McpResultEvidence,
)


SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
)


def create_mcp_call(
    *,
    call_id: str = "mcp-001",
) -> McpCallEvidence:
    return McpCallEvidence(
        mcp_call_id=call_id,

        server_name=(
            "azure-mcp-operations-sbx"
        ),

        tool_name="group_list",

        arguments={
            "subscription":
                SUBSCRIPTION_ID,
        },

        source_message_id=(
            "msg-assistant-001"
        ),

        source_message_role=(
            "assistant"
        ),
    )


def create_mcp_result(
    *,
    call_id: str = "mcp-001",
    status: int | None = 200,
    raw_text: str | None = None,
) -> McpResultEvidence:
    if raw_text is None:
        payload = {
            "status":
                status,

            "message": (
                "Success"
                if (
                    status is not None
                    and 200 <= status < 300
                )
                else "Failure"
            ),

            "results": {
                "groups": [
                    {
                        "name":
                            "rg-icenter-sandbox-foundry",

                        "id": (
                            "/subscriptions/"
                            + SUBSCRIPTION_ID
                            + "/resourceGroups/"
                            "rg-icenter-sandbox-foundry"
                        ),

                        "location":
                            "westeurope",
                    }
                ]
            },
        }

        raw_text = json.dumps(
            payload
        )

    #
    # Esta forma reproduce la estructura observada
    # en el LIVE real de Agent Framework:
    #
    # mcp_server_tool_result.output
    #   -> lista
    #   -> item type=text
    #   -> text contiene JSON Azure MCP
    #
    return McpResultEvidence(
        mcp_call_id=call_id,

        output=[
            {
                "type":
                    "text",

                "text":
                    raw_text,

                "additional_properties":
                    {},
            }
        ],

        source_message_id=(
            "msg-assistant-001"
        ),

        source_message_role=(
            "assistant"
        ),
    )


def create_evidence(
    *,
    mcp_calls=None,
    mcp_results=None,
) -> OperationEvidence:
    return OperationEvidence(
        operation_id=(
            "op-11111111-1111-5111-"
            "8111-111111111111"
        ),

        workflow_id=(
            "wf-11111111-1111-4111-"
            "8111-111111111111"
        ),

        approval_id=(
            "apr-11111111-1111-4111-"
            "8111-111111111111"
        ),

        alert_id=(
            "ALT-AZ-RG-LIST-001"
        ),

        correlation_id=(
            "corr-azure-rg-list-live-001"
        ),

        conversation_id=None,

        procedure_id=(
            "NTTSY-SBX-AZ-001"
        ),

        procedure_version="1.0",

        current_step=1,

        step_id="1",

        operation_domain="azure",

        operation_kind=(
            OperationKind.READ
        ),

        next_action=(
            NextAction.EXECUTE_STEP
        ),

        target_resource=(
            "subscription"
        ),

        required_parameters=[
            "subscription_id",
        ],

        resolved_parameters=[
            ResolvedParameter(
                name="subscription_id",

                value=(
                    SUBSCRIPTION_ID
                ),

                source=(
                    "normalized_alert."
                    "subscription_id"
                ),
            )
        ],

        tool_calls=[],

        mcp_calls=list(
            mcp_calls or []
        ),

        tool_results=[],

        mcp_results=list(
            mcp_results or []
        ),

        response_errors=[],
    )


def test_correlated_azure_mcp_2xx_result_derives_true():
    """
    Evidencia observada LIVE:

        MCP call group_list
            +
        mismo mcp_call_id
            +
        output JSON con status 2xx

    demuestra éxito técnico.
    """

    evidence = create_evidence(
        mcp_calls=[
            create_mcp_call(),
        ],

        mcp_results=[
            create_mcp_result(
                status=200,
            ),
        ],
    )

    assert (
        evidence
        .derive_technical_success()
        is True
    )


def test_correlated_azure_mcp_error_status_derives_false():
    """
    Un resultado MCP correlacionado que contiene
    un estado explícito de error demuestra fallo.
    """

    evidence = create_evidence(
        mcp_calls=[
            create_mcp_call(),
        ],

        mcp_results=[
            create_mcp_result(
                status=404,
            ),
        ],
    )

    assert (
        evidence
        .derive_technical_success()
        is False
    )


def test_azure_mcp_unparseable_result_remains_unknown():
    """
    Fail closed.

    Si el output MCP no contiene un contrato de
    estado interpretable, no inventamos éxito.
    """

    evidence = create_evidence(
        mcp_calls=[
            create_mcp_call(),
        ],

        mcp_results=[
            create_mcp_result(
                raw_text=(
                    "resultado MCP "
                    "sin estado estructurado"
                ),
            ),
        ],
    )

    assert (
        evidence
        .derive_technical_success()
        is None
    )


def test_azure_mcp_missing_result_remains_unknown():
    """
    Una llamada sin resultado correlacionado
    no demuestra éxito ni fallo.
    """

    evidence = create_evidence(
        mcp_calls=[
            create_mcp_call(),
        ],

        mcp_results=[],
    )

    assert (
        evidence
        .derive_technical_success()
        is None
    )


def test_azure_mcp_mismatched_call_result_remains_unknown():
    """
    El resultado de otra llamada MCP jamás puede
    utilizarse para demostrar el éxito de ésta.
    """

    evidence = create_evidence(
        mcp_calls=[
            create_mcp_call(
                call_id="mcp-001",
            ),
        ],

        mcp_results=[
            create_mcp_result(
                call_id="mcp-002",
                status=200,
            ),
        ],
    )

    assert (
        evidence
        .derive_technical_success()
        is None
    )