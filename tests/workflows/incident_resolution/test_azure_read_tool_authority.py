from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, fields, is_dataclass
from types import SimpleNamespace

import pytest
from agent_framework import WorkflowBuilder

from src.runtime.procedure.models import (
    OperationAction,
    OperationKind,
)
from src.workflows.incident_resolution.azure_operations_models import (
    VerifiedAzureOperationRequest,
    VerifiedResolvedParameter,
)
from src.workflows.incident_resolution.capability_registry import (
    build_default_capability_registry,
)
from src.workflows.incident_resolution.executors.azure_operations import (
    AzureOperationsExecutor,
)
from src.workflows.incident_resolution.operation_dispatch_ledger import (
    InMemoryOperationDispatchLedger,
)

MISSING = "F27_1_EXPECTED_RED_EXACT_AZURE_READ_TOOL_AUTHORITY_ABSENT"

SERVER_LABEL = "azure-mcp-operations-sbx"
CAPABILITY_ID = "azure.resource_group.list"
TOOL_NAME = "group_list"
SUBSCRIPTION_ID = "sub-f27-001"
APPROVAL_REQUEST_ID = "mcpr-f27-read-001"
RESPONSE_ID = "resp-f27-read-001"


def contract():
    try:
        from src.workflows.incident_resolution.azure_read_tool_authority import (
            AzureReadToolAuthority,
            AzureReadToolAuthorityError,
            AzureReadToolAuthorityRegistry,
            AzureReadToolAuthorityRegistryError,
            build_default_azure_read_tool_authority_registry,
        )
    except ModuleNotFoundError as exc:
        if exc.name == (
            "src.workflows.incident_resolution."
            "azure_read_tool_authority"
        ):
            raise AssertionError(MISSING) from None
        raise

    return (
        AzureReadToolAuthority,
        AzureReadToolAuthorityError,
        AzureReadToolAuthorityRegistry,
        AzureReadToolAuthorityRegistryError,
        build_default_azure_read_tool_authority_registry,
    )


def authority_kwargs(**overrides):
    values = {
        "capability_id": CAPABILITY_ID,
        "operation_domain": "azure",
        "resource_type": "subscription",
        "operation_action": (
            OperationAction.RESOURCE_GROUP_LIST
        ),
        "target_resource": "subscription",
        "server_label": SERVER_LABEL,
        "tool_name": TOOL_NAME,
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
    values.update(overrides)
    return values


def verified_read_request(
    *,
    capability_id=CAPABILITY_ID,
    operation_domain="azure",
    operation_kind=OperationKind.READ,
    operation_action=None,
    target_resource="subscription",
    required_parameters=None,
    resolved_parameters=None,
    security_verified=True,
    verification_source="pre_call_security_verifier",
):
    if operation_action is None:
        operation_action = (
            OperationAction.RESOURCE_GROUP_LIST
        )

    if required_parameters is None:
        required_parameters = [
            "subscription_id",
        ]

    if resolved_parameters is None:
        resolved_parameters = [
            VerifiedResolvedParameter(
                name="subscription_id",
                value=SUBSCRIPTION_ID,
                source=(
                    "normalized_alert."
                    "subscription_id"
                ),
            )
        ]

    return VerifiedAzureOperationRequest(
        operation_id="op-f27-read-001",
        workflow_id="wf-f27-read-001",
        approval_id=(
            "apr-27111111-1111-4111-"
            "8111-111111111111"
        ),
        alert_id="ALT-F27-READ-001",
        correlation_id="corr-f27-read-001",
        conversation_id="conv-f27-read-001",
        procedure_id="TEST-F27-READ",
        procedure_version="1.0",
        current_step=1,
        step_id="1",
        description=(
            "Listar exclusivamente los Resource Groups "
            "de la suscripción autorizada."
        ),
        operation_domain=operation_domain,
        operation_kind=operation_kind,
        operation_action=operation_action,
        capability_id=capability_id,
        hitl_required=False,
        next_action="execute_step",
        target_resource=target_resource,
        required_parameters=list(
            required_parameters
        ),
        resolved_parameters=list(
            resolved_parameters
        ),
        security_verified=security_verified,
        verification_source=verification_source,
    )


def approval(
    *,
    server_label=SERVER_LABEL,
    tool_name=TOOL_NAME,
    arguments=None,
):
    if arguments is None:
        arguments = {
            "subscription":
                SUBSCRIPTION_ID,
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


def first_approval_response(
    *,
    raw_server_label=SERVER_LABEL,
    raw_tool_name=TOOL_NAME,
    raw_arguments=None,
    native_server_label=SERVER_LABEL,
    native_tool_name=TOOL_NAME,
    native_arguments=None,
    include_approval=True,
):
    if raw_arguments is None:
        raw_arguments = {
            "subscription":
                SUBSCRIPTION_ID,
        }

    if native_arguments is None:
        native_arguments = dict(
            raw_arguments
        )

    raw_output = []

    if include_approval:
        raw_output.append(
            SimpleNamespace(
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
        )

    raw_response = SimpleNamespace(
        id=RESPONSE_ID,
        output=raw_output,
    )

    native_requests = []

    if include_approval:
        function_call = SimpleNamespace(
            type="function_call",
            id=None,
            call_id=(
                APPROVAL_REQUEST_ID
            ),
            name=native_tool_name,
            arguments=json.dumps(
                native_arguments
            ),
            additional_properties={
                "server_label":
                    native_server_label
            },
        )

        native_request = SimpleNamespace(
            type="function_approval_request",
            id=APPROVAL_REQUEST_ID,
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

        native_requests.append(
            native_request
        )

    response = SimpleNamespace(
        raw_response=raw_response,
        user_input_requests=(
            native_requests
        ),
        text=None,
        messages=[],
    )

    return response


def final_response():
    return SimpleNamespace(
        text="Resource groups listed.",
        messages=[],
        user_input_requests=[],
        raw_response=SimpleNamespace(
            id="resp-f27-read-final",
            output=[],
        ),
    )


class FakeGovernedReadAgents:
    def __init__(
        self,
        first_response,
    ) -> None:
        self.first_response = first_response
        self.final_response = final_response()
        self.begin_calls = []
        self.continue_calls = []
        self.legacy_calls = []
        self.invocation = SimpleNamespace(
            response=first_response
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
        return self.final_response


def build_executor_workflow(
    *,
    agents,
    ledger=None,
):
    if ledger is None:
        ledger = (
            InMemoryOperationDispatchLedger()
        )

    executor = AzureOperationsExecutor(
        agents=agents,
        operation_dispatch_ledger=ledger,
    )

    workflow = (
        WorkflowBuilder(
            start_executor=executor,
            output_from=[
                executor,
            ],
            name=(
                "f27-read-tool-authority"
            ),
        )
        .build()
    )

    return (
        workflow,
        ledger,
    )


async def run_once(
    *,
    agents,
    request=None,
):
    if request is None:
        request = (
            verified_read_request()
        )

    workflow, ledger = (
        build_executor_workflow(
            agents=agents,
        )
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
        outputs,
        ledger,
    )


def test_authority_is_small_frozen_value_not_executor_or_workflow():
    Authority, _, _, _, _ = contract()

    authority = Authority(
        **authority_kwargs()
    )

    assert is_dataclass(authority)
    assert authority.__dataclass_params__.frozen is True
    assert [
        item.name
        for item in fields(authority)
    ] == [
        "capability_id",
        "operation_domain",
        "resource_type",
        "operation_action",
        "target_resource",
        "server_label",
        "tool_name",
        "required_parameters",
        "argument_bindings",
    ]

    with pytest.raises(
        FrozenInstanceError
    ):
        authority.tool_name = (
            "subscription_list"
        )

    assert not hasattr(
        authority,
        "execute",
    )
    assert not hasattr(
        authority,
        "dispatch",
    )
    assert not hasattr(
        authority,
        "run",
    )


@pytest.mark.parametrize(
    (
        "field_name",
        "bad_value",
    ),
    [
        ("capability_id", None),
        ("capability_id", ""),
        ("capability_id", " azure.resource_group.list"),
        ("operation_domain", ""),
        ("operation_domain", "Azure"),
        ("resource_type", ""),
        ("target_resource", " subscription"),
        ("server_label", ""),
        ("tool_name", "group_list "),
    ],
)
def test_authority_rejects_invalid_or_nonexact_identity_fields(
    field_name,
    bad_value,
):
    Authority, Error, _, _, _ = contract()

    kwargs = authority_kwargs(
        **{
            field_name:
                bad_value,
        }
    )

    with pytest.raises(
        Error
    ):
        Authority(
            **kwargs
        )


@pytest.mark.parametrize(
    "bad_parameters",
    [
        ["subscription_id"],
        (),
        ("subscription_id", "subscription_id"),
        (" subscription_id",),
    ],
)
def test_authority_requires_exact_immutable_required_parameters(
    bad_parameters,
):
    Authority, Error, _, _, _ = contract()

    with pytest.raises(
        Error
    ):
        Authority(
            **authority_kwargs(
                required_parameters=(
                    bad_parameters
                )
            )
        )


@pytest.mark.parametrize(
    "bad_bindings",
    [
        [
            (
                "subscription",
                "subscription_id",
            )
        ],
        (),
        (
            (
                "subscription",
                "subscription_id",
            ),
            (
                "subscription",
                "subscription_id",
            ),
        ),
        (
            (
                " subscription",
                "subscription_id",
            ),
        ),
        (
            (
                "subscription",
                " subscription_id",
            ),
        ),
    ],
)
def test_authority_requires_exact_immutable_argument_bindings(
    bad_bindings,
):
    Authority, Error, _, _, _ = contract()

    with pytest.raises(
        Error
    ):
        Authority(
            **authority_kwargs(
                argument_bindings=(
                    bad_bindings
                )
            )
        )


def test_default_registry_contains_only_resource_group_list_read_authority():
    _, _, _, _, build_default = contract()

    registry = build_default()

    assert registry.count() == 1

    authority = registry.get(
        CAPABILITY_ID
    )

    assert (
        authority.capability_id
        == CAPABILITY_ID
    )
    assert (
        authority.operation_domain
        == "azure"
    )
    assert (
        authority.resource_type
        == "subscription"
    )
    assert (
        authority.operation_action
        == OperationAction.RESOURCE_GROUP_LIST
    )
    assert (
        authority.target_resource
        == "subscription"
    )
    assert (
        authority.server_label
        == SERVER_LABEL
    )
    assert (
        authority.tool_name
        == TOOL_NAME
    )
    assert (
        authority.required_parameters
        == (
            "subscription_id",
        )
    )
    assert (
        authority.argument_bindings
        == (
            (
                "subscription",
                "subscription_id",
            ),
        )
    )


@pytest.mark.parametrize(
    "capability_id",
    [
        "Azure.Resource_Group.List",
        "azure.resource_group.list ",
        " azure.resource_group.list",
        "azure.resource_group",
        "unknown",
    ],
)
def test_registry_lookup_is_exact_and_fails_closed(
    capability_id,
):
    _, _, _, RegistryError, build_default = (
        contract()
    )

    registry = build_default()

    with pytest.raises(
        RegistryError
    ):
        registry.get(
            capability_id
        )


def test_registry_rejects_duplicate_capability_authority():
    Authority, _, Registry, RegistryError, _ = (
        contract()
    )

    first = Authority(
        **authority_kwargs()
    )
    second = Authority(
        **authority_kwargs()
    )

    with pytest.raises(
        RegistryError
    ):
        Registry(
            authorities=(
                first,
                second,
            )
        )


def test_valid_pending_group_list_approval_is_accepted():
    _, _, _, _, build_default = contract()

    authority = (
        build_default()
        .get(
            CAPABILITY_ID
        )
    )

    authority.validate_pending_approval(
        request=(
            verified_read_request()
        ),
        approval=(
            approval()
        ),
    )


@pytest.mark.parametrize(
    (
        "request_overrides",
        "approval_overrides",
    ),
    [
        (
            {
                "capability_id":
                    "azure.subscription.list",
            },
            {},
        ),
        (
            {
                "operation_domain":
                    "Azure",
            },
            {},
        ),
        (
            {
                "operation_kind":
                    OperationKind.WRITE,
            },
            {},
        ),
        (
            {
                "target_resource":
                    "subscription ",
            },
            {},
        ),
        (
            {
                "required_parameters":
                    [],
            },
            {},
        ),
        (
            {
                "resolved_parameters":
                    [],
            },
            {},
        ),
        (
            {
                "security_verified":
                    False,
            },
            {},
        ),
        (
            {
                "verification_source":
                    "other",
            },
            {},
        ),
        (
            {},
            {
                "server_label":
                    "attacker-mcp",
            },
        ),
        (
            {},
            {
                "tool_name":
                    "subscription_list",
            },
        ),
        (
            {},
            {
                "arguments":
                    {},
            },
        ),
        (
            {},
            {
                "arguments": {
                    "subscription":
                        "sub-attacker",
                },
            },
        ),
        (
            {},
            {
                "arguments": {
                    "subscription":
                        SUBSCRIPTION_ID,
                    "extra":
                        "scope-expansion",
                },
            },
        ),
    ],
)
def test_pending_approval_validation_rejects_any_authority_mismatch(
    request_overrides,
    approval_overrides,
):
    _, Error, _, _, build_default = contract()

    authority = (
        build_default()
        .get(
            CAPABILITY_ID
        )
    )

    if (
        set(request_overrides)
        & {
            "security_verified",
            "verification_source",
        }
    ):
        valid_request = (
            verified_read_request()
        )

        payload = {
            field_name: getattr(
                valid_request,
                field_name,
            )
            for field_name
            in type(
                valid_request
            ).model_fields
        }

        payload.update(
            request_overrides
        )

        request = (
            type(
                valid_request
            ).model_construct(
                **payload
            )
        )

    else:
        request = (
            verified_read_request(
                **request_overrides
            )
        )

    with pytest.raises(
        Error
    ):
        authority.validate_pending_approval(
            request=request,
            approval=(
                approval(
                    **approval_overrides
                )
            ),
        )


def test_read_authority_registry_is_aligned_with_installed_capability_and_action():
    (
        _,
        _,
        _,
        _,
        build_authority_registry,
    ) = contract()

    capability_registry = (
        build_default_capability_registry()
    )

    assert capability_registry.count() == 2

    vm_start = (
        capability_registry
        .get(
            "azure.vm.start"
        )
    )

    resource_group_list = (
        capability_registry
        .get(
            CAPABILITY_ID
        )
    )

    assert (
        vm_start.capability_id
        == "azure.vm.start"
    )

    assert (
        resource_group_list.operation_action
        == OperationAction.RESOURCE_GROUP_LIST
    )

    authority = (
        build_authority_registry()
        .get(
            CAPABILITY_ID
        )
    )

    assert (
        authority.operation_action
        == resource_group_list.operation_action
    )

    assert {
        action.value
        for action
        in OperationAction
    } == {
        "vm_start",
        "resource_group_list",
    }


@pytest.mark.asyncio
async def test_governed_read_uses_begin_and_continue_not_legacy():
    contract()

    agents = (
        FakeGovernedReadAgents(
            first_approval_response()
        )
    )

    outputs, ledger = await run_once(
        agents=agents
    )

    assert len(
        agents.begin_calls
    ) == 1
    assert agents.legacy_calls == []
    assert len(
        agents.continue_calls
    ) == 1
    assert (
        agents.continue_calls[0][
            "approved"
        ]
        is True
    )
    assert ledger.count() == 1
    assert len(outputs) == 1
    assert outputs[0].success is True


@pytest.mark.asyncio
async def test_governed_read_rejects_wrong_tool_before_continue():
    contract()

    agents = (
        FakeGovernedReadAgents(
            first_approval_response(
                raw_tool_name=(
                    "subscription_list"
                ),
                native_tool_name=(
                    "subscription_list"
                ),
            )
        )
    )

    outputs, ledger = await run_once(
        agents=agents
    )

    assert len(
        agents.begin_calls
    ) == 1
    assert agents.legacy_calls == []
    assert (
        agents.continue_calls
        == []
    )
    assert ledger.count() == 1
    assert len(outputs) == 1
    assert outputs[0].success is False


@pytest.mark.asyncio
async def test_governed_read_rejects_wrong_arguments_before_continue():
    contract()

    agents = (
        FakeGovernedReadAgents(
            first_approval_response(
                raw_arguments={
                    "subscription":
                        "sub-attacker",
                },
                native_arguments={
                    "subscription":
                        "sub-attacker",
                },
            )
        )
    )

    outputs, ledger = await run_once(
        agents=agents
    )

    assert len(
        agents.begin_calls
    ) == 1
    assert agents.legacy_calls == []
    assert (
        agents.continue_calls
        == []
    )
    assert ledger.count() == 1
    assert len(outputs) == 1
    assert outputs[0].success is False


@pytest.mark.asyncio
async def test_governed_read_rejects_raw_native_tool_mismatch():
    contract()

    agents = (
        FakeGovernedReadAgents(
            first_approval_response(
                raw_tool_name=TOOL_NAME,
                native_tool_name=(
                    "subscription_list"
                ),
            )
        )
    )

    outputs, ledger = await run_once(
        agents=agents
    )

    assert len(
        agents.begin_calls
    ) == 1
    assert agents.legacy_calls == []
    assert (
        agents.continue_calls
        == []
    )
    assert ledger.count() == 1
    assert len(outputs) == 1
    assert outputs[0].success is False


@pytest.mark.asyncio
async def test_governed_read_requires_pending_approval_and_never_falls_back_legacy():
    contract()

    agents = (
        FakeGovernedReadAgents(
            first_approval_response(
                include_approval=False
            )
        )
    )

    outputs, ledger = await run_once(
        agents=agents
    )

    assert len(
        agents.begin_calls
    ) == 1
    assert agents.legacy_calls == []
    assert (
        agents.continue_calls
        == []
    )
    assert ledger.count() == 1
    assert len(outputs) == 1
    assert outputs[0].success is False


@pytest.mark.asyncio
async def test_unknown_governed_read_authority_fails_before_dispatch_or_foundry():
    _, _, _, RegistryError, _ = contract()

    agents = (
        FakeGovernedReadAgents(
            first_approval_response()
        )
    )

    workflow, ledger = (
        build_executor_workflow(
            agents=agents
        )
    )

    request = (
        verified_read_request(
            capability_id=(
                "azure.unknown.read"
            )
        )
    )

    with pytest.raises(
        RegistryError
    ):
        async for _ in workflow.run(
            request,
            stream=True,
        ):
            pass

    assert ledger.count() == 0
    assert agents.begin_calls == []
    assert agents.continue_calls == []
    assert agents.legacy_calls == []


@pytest.mark.asyncio
async def test_legacy_read_without_capability_preserves_existing_single_run_path():
    contract()

    agents = (
        FakeGovernedReadAgents(
            first_approval_response()
        )
    )

    outputs, ledger = await run_once(
        agents=agents,
        request=(
            verified_read_request(
                capability_id=None,
            )
        ),
    )

    assert agents.begin_calls == []
    assert agents.continue_calls == []
    assert len(
        agents.legacy_calls
    ) == 1
    assert ledger.count() == 1
    assert len(outputs) == 1
    assert outputs[0].success is True
