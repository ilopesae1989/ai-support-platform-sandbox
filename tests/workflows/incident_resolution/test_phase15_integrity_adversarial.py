import pickle

import pytest

from pydantic import (
    ValidationError,
)

from src.workflows.incident_resolution.azure_operations import (
    build_azure_operation_request,
)

from src.workflows.incident_resolution.azure_operations_models import (
    VerifiedAzureOperationRequest,
)

from src.workflows.incident_resolution.executors.azure_operations import (
    AzureOperationsExecutor,
)

from src.workflows.incident_resolution.operation_models import (
    OperationResult,
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

from tests.workflows.incident_resolution.test_technical_result_evidence_contract import (
    create_evidence,
    create_result,
    mcp_call,
    mcp_result,
    tool_call,
    tool_result,
)


def create_verified_request():
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

    return (
        approved_step,
        candidate,
        verified,
    )


def create_valid_result() -> OperationResult:
    evidence = (
        create_evidence(
            tool_calls=[
                tool_call(),
            ],

            tool_results=[
                tool_result(),
            ],
        )
    )

    return create_result(
        evidence,
        success=True,
        technical_success=True,
    )


# ============================================================
# Verified request
# ============================================================


def test_verified_request_requires_explicit_verification_fields():
    _approved, candidate, _verified = (
        create_verified_request()
    )

    with pytest.raises(
        ValidationError,
    ):
        VerifiedAzureOperationRequest(
            **candidate.model_dump(
                mode="python"
            )
        )


def test_verified_request_blocks_top_level_mutation():
    _approved, _candidate, verified = (
        create_verified_request()
    )

    with pytest.raises(
        ValidationError,
    ):
        verified.target_resource = (
            "tampered-resource"
        )


def test_verified_required_parameters_are_immutable():
    _approved, _candidate, verified = (
        create_verified_request()
    )

    with pytest.raises(
        TypeError,
        match="snapshot inmutable",
    ):
        verified.required_parameters.append(
            "tampered_parameter"
        )


def test_verified_resolved_parameter_is_immutable():
    _approved, _candidate, verified = (
        create_verified_request()
    )

    assert len(
        verified.resolved_parameters
    ) == 1

    with pytest.raises(
        ValidationError,
    ):
        verified.resolved_parameters[
            0
        ].value = "tampered-value"


def test_verified_request_blocks_model_copy_update():
    _approved, _candidate, verified = (
        create_verified_request()
    )

    with pytest.raises(
        TypeError,
        match="PreCallSecurityVerifier",
    ):
        verified.model_copy(
            update={
                "target_resource":
                    "tampered-resource"
            }
        )


def test_verified_request_allows_deep_copy_without_changes():
    _approved, _candidate, verified = (
        create_verified_request()
    )

    copied = verified.model_copy(
        deep=True
    )

    assert (
        copied
        == verified
    )

    assert (
        copied
        is not verified
    )

    assert (
        copied.required_parameters
        is not verified.required_parameters
    )

    assert (
        copied.resolved_parameters
        is not verified.resolved_parameters
    )

    assert (
        copied.required_parameters
        == verified.required_parameters
    )

    assert (
        copied.resolved_parameters
        == verified.resolved_parameters
    )

    with pytest.raises(
        TypeError,
        match="snapshot inmutable",
    ):
        copied.required_parameters.append(
            "tampered_parameter"
        )

    with pytest.raises(
        ValidationError,
    ):
        copied.operation_domain = (
            "database"
        )


def test_executor_rejects_model_construct_with_invalid_verification_source():
    _approved, candidate, _verified = (
        create_verified_request()
    )

    forged = (
        VerifiedAzureOperationRequest
        .model_construct(
            **candidate.model_dump(
                mode="python"
            ),

            security_verified=True,

            verification_source=(
                "forged_source"
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match="integridad estructural",
    ):
        (
            AzureOperationsExecutor
            ._revalidate_verified_request(
                forged
            )
        )


# ============================================================
# OperationResult
# ============================================================


def test_operation_result_blocks_top_level_mutation():
    result = (
        create_valid_result()
    )

    with pytest.raises(
        ValidationError,
    ):
        result.technical_success = False


def test_operation_result_model_copy_revalidates_inconsistent_update():
    result = (
        create_valid_result()
    )

    with pytest.raises(
        ValidationError,
        match="technical_success",
    ):
        result.model_copy(
            update={
                "technical_success":
                    False
            }
        )


def test_operation_result_model_copy_allows_consistent_update():
    result = (
        create_valid_result()
    )

    copied = result.model_copy(
        update={
            "response_text":
                "updated response"
        }
    )

    assert (
        copied.response_text
        == "updated response"
    )

    assert (
        copied.technical_success
        is True
    )

    assert (
        copied.evidence
        .derive_technical_success()
        is True
    )


# ============================================================
# Deep immutability
# ============================================================


def test_operation_result_required_parameters_are_deeply_immutable():
    result = (
        create_valid_result()
    )

    with pytest.raises(
        TypeError,
        match="snapshot inmutable",
    ):
        result.required_parameters.append(
            "tampered_parameter"
        )


def test_operation_result_resolved_parameter_is_deeply_immutable():
    result = (
        create_valid_result()
    )

    with pytest.raises(
        ValidationError,
    ):
        result.resolved_parameters[
            0
        ].value = "tampered-value"


def test_operation_evidence_is_frozen():
    result = (
        create_valid_result()
    )

    with pytest.raises(
        ValidationError,
    ):
        result.evidence.operation_id = (
            "op-tampered"
        )


def test_operation_evidence_collections_are_immutable():
    result = (
        create_valid_result()
    )

    with pytest.raises(
        TypeError,
        match="snapshot inmutable",
    ):
        result.evidence.tool_calls.append(
            tool_call(
                "call-extra"
            )
        )


def test_nested_tool_result_is_frozen():
    result = (
        create_valid_result()
    )

    with pytest.raises(
        ValidationError,
    ):
        result.evidence.tool_results[
            0
        ].exception = (
            "RuntimeError: tampered"
        )

    assert (
        result.technical_success
        is True
    )

    assert (
        result.evidence
        .derive_technical_success()
        is True
    )


def test_evidence_resolved_parameter_source_is_frozen():
    result = (
        create_valid_result()
    )

    with pytest.raises(
        ValidationError,
    ):
        result.evidence.resolved_parameters[
            0
        ].source = "untrusted_source"


def test_tool_and_mcp_arguments_are_deeply_immutable():
    evidence = (
        create_evidence(
            tool_calls=[
                tool_call(),
            ],

            mcp_calls=[
                mcp_call(),
            ],
        )
    )

    with pytest.raises(
        TypeError,
        match="snapshot inmutable",
    ):
        evidence.tool_calls[
            0
        ].arguments[
            "tampered"
        ] = True

    with pytest.raises(
        TypeError,
        match="snapshot inmutable",
    ):
        evidence.mcp_calls[
            0
        ].arguments[
            "tampered"
        ] = True


def test_mcp_output_is_deeply_immutable():
    evidence = (
        create_evidence(
            mcp_results=[
                mcp_result(),
            ]
        )
    )

    with pytest.raises(
        TypeError,
        match="snapshot inmutable",
    ):
        evidence.mcp_results[
            0
        ].output[
            "status"
        ] = "tampered"

    assert (
        evidence.mcp_results[
            0
        ].output[
            "status"
        ]
        == "success"
    )


def test_operation_evidence_blocks_model_copy_update():
    result = (
        create_valid_result()
    )

    with pytest.raises(
        TypeError,
        match="snapshot inmutable",
    ):
        result.evidence.model_copy(
            update={
                "operation_id":
                    "op-tampered"
            }
        )



# ============================================================
# Final review 15.13:
# serialization / checkpoint compatibility
# ============================================================


@pytest.mark.parametrize(
    "technical_success",
    [
        True,
        False,
    ],
)
def test_successful_result_rejects_technical_status_without_evidence(
    technical_success,
):
    evidence = (
        create_evidence()
    )

    with pytest.raises(
        ValidationError,
        match="technical_success",
    ):
        OperationResult(
            operation_id=(
                evidence.operation_id
            ),

            workflow_id=(
                evidence.workflow_id
            ),

            approval_id=(
                evidence.approval_id
            ),

            alert_id=(
                evidence.alert_id
            ),

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

            step_id=(
                evidence.step_id
            ),

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
                parameter.model_dump(
                    mode="python"
                )
                for parameter
                in evidence.resolved_parameters
            ],

            success=True,

            technical_success=(
                technical_success
            ),

            response_text="response",

            error=None,

            evidence=None,
        )


def test_verified_request_supports_pickle_round_trip():
    _approved, _candidate, verified = (
        create_verified_request()
    )

    restored = pickle.loads(
        pickle.dumps(
            verified
        )
    )

    assert (
        restored
        == verified
    )

    assert (
        restored
        is not verified
    )

    with pytest.raises(
        TypeError,
        match="snapshot inmutable",
    ):
        restored.required_parameters.append(
            "tampered_parameter"
        )

    with pytest.raises(
        ValidationError,
    ):
        restored.resolved_parameters[
            0
        ].value = "tampered-value"


def test_operation_result_supports_deep_pickle_round_trip():
    call = ToolCallEvidence(
        tool_call_id="call-pickle-001",

        tool_name="tool_pickle",

        arguments={
            "subscription_id":
                "sub-001",

            "nested": {
                "values": [
                    1,
                    2,
                ]
            },
        },
    )

    evidence = (
        create_evidence(
            tool_calls=[
                call,
            ],

            tool_results=[
                tool_result(
                    "call-pickle-001"
                ),
            ],
        )
    )

    result = create_result(
        evidence,
        success=True,
        technical_success=True,
    )

    restored = pickle.loads(
        pickle.dumps(
            result
        )
    )

    assert (
        restored
        == result
    )

    assert (
        restored.technical_success
        is True
    )

    assert (
        restored.evidence
        .derive_technical_success()
        is True
    )

    with pytest.raises(
        TypeError,
        match="snapshot inmutable",
    ):
        restored.evidence.tool_calls[
            0
        ].arguments[
            "nested"
        ][
            "values"
        ].append(
            3
        )


def test_operation_result_supports_json_model_round_trip():
    result = (
        create_valid_result()
    )

    payload = result.model_dump(
        mode="json"
    )

    restored = (
        OperationResult
        .model_validate(
            payload
        )
    )

    assert (
        restored
        == result
    )

    assert (
        restored.technical_success
        is True
    )

    assert (
        restored.evidence
        .derive_technical_success()
        is True
    )

    with pytest.raises(
        TypeError,
        match="snapshot inmutable",
    ):
        restored.evidence.tool_calls.append(
            tool_call(
                "call-extra"
            )
        )
