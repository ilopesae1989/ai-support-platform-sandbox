from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest

from src.runtime.procedure.models import (
    ApprovedProcedureStep,
    NextAction,
    OperationAction,
    OperationKind,
    ResolvedParameter,
)
from src.workflows.incident_resolution.azure_operations import (
    build_azure_operation_request,
)
from src.workflows.incident_resolution.azure_operations_models import (
    VerifiedAzureOperationRequest,
    VerifiedResolvedParameter,
)
from src.workflows.incident_resolution.azure_read_tool_authority import (
    AzureReadToolAuthority,
    AzureReadToolAuthorityError,
    build_default_azure_read_tool_authority_registry,
)
from src.workflows.incident_resolution.capability_registry import (
    build_default_capability_registry,
)
from src.workflows.incident_resolution.pre_call_security import (
    PreCallSecurityError,
    PreCallSecurityVerifier,
)
from src.workflows.incident_resolution.procedure_capability_registry import (
    DEFAULT_PROCEDURE_CAPABILITY_BINDINGS_PATH,
)


CAPABILITY_ID = "azure.resource_group.list"
SERVER_LABEL = "azure-mcp-operations-sbx"
TOOL_NAME = "group_list"
SUBSCRIPTION_ID = "sub-f27-2-001"


def _fail(marker: str) -> None:
    pytest.fail(
        marker,
        pytrace=False,
    )


def _verified_read(
    *,
    operation_action,
) -> VerifiedAzureOperationRequest:
    return VerifiedAzureOperationRequest(
        operation_id="op-f27-2-read-001",
        workflow_id="wf-f27-2-read-001",
        approval_id=(
            "apr-27222222-2222-4222-"
            "8222-222222222222"
        ),
        alert_id="ALT-F27-2-READ-001",
        correlation_id="corr-f27-2-read-001",
        conversation_id="conv-f27-2-read-001",
        procedure_id="TEST-F27-2-READ",
        procedure_version="1.0",
        current_step=1,
        step_id="1",
        description=(
            "Listar exclusivamente los Resource Groups "
            "de la suscripción autorizada."
        ),
        operation_domain="azure",
        operation_kind=OperationKind.READ,
        operation_action=operation_action,
        capability_id=CAPABILITY_ID,
        hitl_required=False,
        next_action=NextAction.EXECUTE_STEP,
        target_resource="subscription",
        required_parameters=[
            "subscription_id",
        ],
        resolved_parameters=[
            VerifiedResolvedParameter(
                name="subscription_id",
                value=SUBSCRIPTION_ID,
                source=(
                    "normalized_alert."
                    "subscription_id"
                ),
            )
        ],
        security_verified=True,
        verification_source=(
            "pre_call_security_verifier"
        ),
    )


def _approved_governed_read(
    *,
    operation_action,
    hitl_required,
) -> ApprovedProcedureStep:
    return ApprovedProcedureStep(
        workflow_id="wf-f27-2-precall-001",
        approval_id=(
            "apr-27333333-3333-4333-"
            "8333-333333333333"
        ),
        alert_id="ALT-F27-2-PRECALL-001",
        correlation_id="corr-f27-2-precall-001",
        conversation_id="conv-f27-2-precall-001",
        procedure_id="TEST-F27-2-PRECALL",
        procedure_version="1.0",
        current_step=1,
        step_id="1",
        description=(
            "Listar exclusivamente los Resource Groups "
            "de la suscripción autorizada."
        ),
        operation_domain="azure",
        operation_kind=OperationKind.READ,
        operation_action=operation_action,
        capability_id=CAPABILITY_ID,
        hitl_required=hitl_required,
        next_action=NextAction.EXECUTE_STEP,
        target_resource="subscription",
        required_parameters=[
            "subscription_id",
        ],
        resolved_parameters=[
            ResolvedParameter(
                name="subscription_id",
                value=SUBSCRIPTION_ID,
                source=(
                    "normalized_alert."
                    "subscription_id"
                ),
            )
        ],
        approved=True,
    )


def test_resource_group_list_operation_action_is_canonical():
    action = getattr(
        OperationAction,
        "RESOURCE_GROUP_LIST",
        None,
    )

    if action is None:
        _fail(
            "F27_2_EXPECTED_RED_RESOURCE_GROUP_LIST_ACTION_ABSENT"
        )

    assert (
        action.value
        == "resource_group_list"
    )


def test_default_capability_registry_installs_exact_resource_group_list_capability():
    registry = (
        build_default_capability_registry()
    )

    if not registry.contains(
        CAPABILITY_ID
    ):
        _fail(
            "F27_2_EXPECTED_RED_RESOURCE_GROUP_LIST_CAPABILITY_ABSENT"
        )

    action = getattr(
        OperationAction,
        "RESOURCE_GROUP_LIST",
        None,
    )

    assert action is not None

    capability = registry.get(
        CAPABILITY_ID
    )

    assert registry.count() == 2
    assert capability.operation_domain == "azure"
    assert capability.resource_type == "subscription"
    assert capability.operation_kind == OperationKind.READ
    assert capability.operation_action == action
    assert capability.required_parameters == (
        "subscription_id",
    )
    assert capability.hitl_required is False
    assert capability.executor_id == "azure_operations"


def test_read_tool_authority_declares_canonical_operation_action_field():
    names = [
        item.name
        for item in fields(
            AzureReadToolAuthority
        )
    ]

    if "operation_action" not in names:
        _fail(
            "F27_2_EXPECTED_RED_READ_AUTHORITY_OPERATION_ACTION_FIELD_ABSENT"
        )

    action = getattr(
        OperationAction,
        "RESOURCE_GROUP_LIST",
        None,
    )

    assert action is not None

    authority = (
        build_default_azure_read_tool_authority_registry()
        .get(
            CAPABILITY_ID
        )
    )

    assert (
        authority.operation_action
        == action
    )


def test_read_tool_authority_requires_exact_operation_action_enum():
    kwargs = {
        "capability_id":
            CAPABILITY_ID,
        "operation_domain":
            "azure",
        "resource_type":
            "subscription",
        "operation_action":
            "resource_group_list",
        "target_resource":
            "subscription",
        "server_label":
            SERVER_LABEL,
        "tool_name":
            TOOL_NAME,
        "required_parameters": (
            "subscription_id",
        ),
        "argument_bindings": (
            (
                "subscription",
                "subscription_id",
            ),
        ),
    }

    try:
        AzureReadToolAuthority(
            **kwargs
        )
    except AzureReadToolAuthorityError as exc:
        assert (
            "operation_action"
            in str(exc)
        )
        return
    except TypeError:
        _fail(
            "F27_2_EXPECTED_RED_READ_AUTHORITY_OPERATION_ACTION_TYPE_NOT_ENFORCED"
        )

    _fail(
        "F27_2_EXPECTED_RED_READ_AUTHORITY_OPERATION_ACTION_TYPE_NOT_ENFORCED"
    )


def test_read_tool_authority_rejects_wrong_request_operation_action():
    authority = (
        build_default_azure_read_tool_authority_registry()
        .get(
            CAPABILITY_ID
        )
    )

    request = _verified_read(
        operation_action=(
            OperationAction.VM_START
        )
    )

    approval = type(
        "PendingApproval",
        (),
        {
            "server_label":
                SERVER_LABEL,
            "tool_name":
                TOOL_NAME,
            "arguments": {
                "subscription":
                    SUBSCRIPTION_ID,
            },
        },
    )()

    try:
        authority.validate_pending_approval(
            request=request,
            approval=approval,
        )
    except AzureReadToolAuthorityError:
        return

    _fail(
        "F27_2_EXPECTED_RED_READ_AUTHORITY_OPERATION_ACTION_NOT_ENFORCED"
    )


def test_precall_rejects_governed_read_without_operation_action():
    step = _approved_governed_read(
        operation_action=None,
        hitl_required=False,
    )

    candidate = (
        build_azure_operation_request(
            step
        )
    )

    try:
        PreCallSecurityVerifier.verify(
            approved_step=step,
            candidate=candidate,
        )
    except PreCallSecurityError:
        return

    _fail(
        "F27_2_EXPECTED_RED_PRECALL_GOVERNED_READ_OPERATION_ACTION_NOT_REQUIRED"
    )


def test_precall_rejects_governed_read_without_explicit_hitl_policy():
    step = _approved_governed_read(
        operation_action=(
            OperationAction.VM_START
        ),
        hitl_required=None,
    )

    candidate = (
        build_azure_operation_request(
            step
        )
    )

    try:
        PreCallSecurityVerifier.verify(
            approved_step=step,
            candidate=candidate,
        )
    except PreCallSecurityError:
        return

    _fail(
        "F27_2_EXPECTED_RED_PRECALL_GOVERNED_READ_HITL_POLICY_NOT_REQUIRED"
    )


def test_f27_2_installation_does_not_grant_default_procedure_or_live_mcp_authority():
    binding_payload = json.loads(
        Path(
            DEFAULT_PROCEDURE_CAPABILITY_BINDINGS_PATH
        ).read_text(
            encoding="utf-8"
        )
    )

    assert len(
        binding_payload[
            "bindings"
        ]
    ) == 3

    assert {
        item[
            "capability_id"
        ]
        for item
        in binding_payload[
            "bindings"
        ]
    } == {
        "azure.vm.start",
    }

    tools_path = (
        Path(__file__)
        .resolve()
        .parents[3]
        / "docs"
        / "foundry"
        / "agents"
        / "agent-azure-operations-sbx"
        / "v13"
        / "tools.sanitized.json"
    )

    tools_payload = json.loads(
        tools_path.read_text(
            encoding="utf-8"
        )
    )

    assert len(
        tools_payload
    ) == 1

    tool_config = tools_payload[0]

    assert (
        TOOL_NAME
        in tool_config[
            "allowed_tools"
        ][
            "tool_names"
        ]
    )

    assert (
        TOOL_NAME
        in tool_config[
            "require_approval"
        ][
            "never"
        ][
            "tool_names"
        ]
    )
