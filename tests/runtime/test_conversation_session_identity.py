from __future__ import annotations

import dataclasses
import importlib
import inspect
import re
import textwrap

import pytest


TARGET_MODULE = (
    "src.runtime.conversation_session_identity"
)


def _module():
    return importlib.import_module(
        TARGET_MODULE
    )


def _identity(
    *,
    tenant_id="tenant-a",
    conversation_id="conversation-a",
    agent_key="azure_operations",
):
    module = _module()

    return module.ConversationSessionIdentity(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        agent_key=agent_key,
    )


def test_identity_has_exact_frozen_surface():
    module = _module()

    identity_type = getattr(
        module,
        "ConversationSessionIdentity",
        None,
    )

    assert identity_type is not None

    assert dataclasses.is_dataclass(
        identity_type
    )

    assert tuple(
        field.name
        for field in dataclasses.fields(
            identity_type
        )
    ) == (
        "tenant_id",
        "conversation_id",
        "agent_key",
    )

    identity = _identity()

    with pytest.raises(
        dataclasses.FrozenInstanceError
    ):
        identity.tenant_id = "other"


def test_identity_rejects_non_exact_components():
    module = _module()

    valid = {
        "tenant_id": "tenant-a",
        "conversation_id": "conversation-a",
        "agent_key": "azure_operations",
    }

    invalid_values = (
        None,
        object(),
        "",
        " ",
        " tenant-a",
        "tenant-a ",
        "\ttenant-a",
        "tenant-a\n",
    )

    for field_name in (
        "tenant_id",
        "conversation_id",
        "agent_key",
    ):
        for invalid in invalid_values:
            values = dict(
                valid
            )

            values[
                field_name
            ] = invalid

            with pytest.raises(
                (
                    TypeError,
                    ValueError,
                )
            ):
                module.ConversationSessionIdentity(
                    **values
                )


def test_identity_preserves_exact_values_without_normalization():
    tenant_id = "Tenant-A"
    conversation_id = "Conversation-ABC-123"
    agent_key = "Azure_Operations_V1"

    identity = _identity(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        agent_key=agent_key,
    )

    assert identity.tenant_id == tenant_id

    assert (
        identity.conversation_id
        == conversation_id
    )

    assert identity.agent_key == agent_key


def test_store_id_factory_has_exact_surface():
    module = _module()

    factory = getattr(
        module,
        "build_conversation_session_store_id",
        None,
    )

    assert callable(
        factory
    )

    signature = inspect.signature(
        factory
    )

    assert tuple(
        signature.parameters
    ) == (
        "identity",
    )

    with pytest.raises(
        TypeError
    ):
        factory(
            object()
        )


def test_store_id_is_deterministic_opaque_and_bounded():
    module = _module()

    identity = _identity()

    first = (
        module
        .build_conversation_session_store_id(
            identity
        )
    )

    second = (
        module
        .build_conversation_session_store_id(
            identity
        )
    )

    assert first == second

    assert isinstance(
        first,
        str,
    )

    assert re.fullmatch(
        r"cs1:[0-9a-f]{64}",
        first,
    )

    assert len(
        first
    ) == 68

    assert identity.tenant_id not in first

    assert identity.conversation_id not in first

    assert identity.agent_key not in first


def test_each_identity_component_changes_store_id():
    module = _module()

    baseline = (
        module
        .build_conversation_session_store_id(
            _identity()
        )
    )

    variants = (
        _identity(
            tenant_id="tenant-b"
        ),
        _identity(
            conversation_id="conversation-b"
        ),
        _identity(
            agent_key="knowledge"
        ),
    )

    variant_ids = {
        module
        .build_conversation_session_store_id(
            variant
        )
        for variant in variants
    }

    assert len(
        variant_ids
    ) == 3

    assert baseline not in variant_ids


def test_store_id_has_no_delimiter_ambiguity():
    module = _module()

    first = (
        module
        .build_conversation_session_store_id(
            _identity(
                tenant_id="a|b",
                conversation_id="c",
                agent_key="d",
            )
        )
    )

    second = (
        module
        .build_conversation_session_store_id(
            _identity(
                tenant_id="a",
                conversation_id="b|c",
                agent_key="d",
            )
        )
    )

    third = (
        module
        .build_conversation_session_store_id(
            _identity(
                tenant_id="a",
                conversation_id="b",
                agent_key="c|d",
            )
        )
    )

    assert len(
        {
            first,
            second,
            third,
        }
    ) == 3


def test_identity_contract_has_no_session_storage_or_runtime_authority():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.lower()

    required = (
        "hashlib",
        "sha256",
        "conversation-session",
    )

    for fragment in required:
        assert fragment in lowered

    forbidden = (
        "agentsession",
        "sessionstore",
        "filesessionstore",
        "service_session_id",
        "os.environ",
        "os.getenv",
        "uuid",
        "random",
        "time.",
        "datetime",
        "mssql",
        "sqlite",
        "cosmos",
        "redis",
        "azure",
        "teams",
        "foundry",
        "mcp",
        "get_token",
        "connect(",
        "asyncio",
    )

    for fragment in forbidden:
        assert fragment not in lowered
