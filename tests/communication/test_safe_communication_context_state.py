from __future__ import annotations

from importlib import import_module
import inspect
import json

import pytest
from pydantic import ValidationError

from src.communication.context import (
    SafeCommunicationContext,
    build_safe_communication_context,
)

from tests.communication.test_communication_projection import (
    _context,
)


class FakeWorkflowContext:
    def __init__(
        self,
        initial=None,
    ) -> None:
        self.state = dict(
            initial or {}
        )
        self.writes = []

    def set_state(
        self,
        key,
        value,
    ) -> None:
        self.writes.append(
            (
                key,
                value,
            )
        )
        self.state[key] = value

    def get_state(
        self,
        key,
        default=None,
    ):
        return self.state.get(
            key,
            default,
        )


def _module():
    try:
        return import_module(
            "src.communication.context_state"
        )
    except ModuleNotFoundError as exc:
        if exc.name != "src.communication.context_state":
            raise

        pytest.fail(
            "Safe Communication workflow state "
            "is not implemented.",
            pytrace=False,
        )


def _snapshot() -> SafeCommunicationContext:
    return build_safe_communication_context(
        _context()
    )


def test_state_key_is_exact_and_dedicated():
    module = _module()

    assert (
        module.SAFE_COMMUNICATION_CONTEXT_STATE_KEY
        == "safe_communication_context"
    )


def test_store_requires_exact_safe_context_and_writes_json_native():
    module = _module()

    ctx = FakeWorkflowContext()
    snapshot = _snapshot()

    module.store_safe_communication_context(
        ctx,
        snapshot,
    )

    assert len(ctx.writes) == 1

    key, payload = ctx.writes[0]

    assert key == (
        module.SAFE_COMMUNICATION_CONTEXT_STATE_KEY
    )

    assert type(payload) is dict

    assert payload == snapshot.model_dump(
        mode="json"
    )

    json.dumps(payload)


def test_store_rejects_non_safe_context_before_write():
    module = _module()

    ctx = FakeWorkflowContext()

    with pytest.raises(TypeError):
        module.store_safe_communication_context(
            ctx,
            object(),
        )

    assert ctx.writes == []


def test_load_returns_none_when_snapshot_is_absent():
    module = _module()

    ctx = FakeWorkflowContext()

    result = module.load_safe_communication_context(
        ctx
    )

    assert result is None


def test_load_rehydrates_exact_safe_context():
    module = _module()

    snapshot = _snapshot()

    ctx = FakeWorkflowContext(
        {
            module.SAFE_COMMUNICATION_CONTEXT_STATE_KEY:
                snapshot.model_dump(
                    mode="json"
                )
        }
    )

    result = module.load_safe_communication_context(
        ctx
    )

    assert type(result) is SafeCommunicationContext
    assert result == snapshot


def test_invalid_existing_payload_fails_closed():
    module = _module()

    snapshot = _snapshot().model_dump(
        mode="json"
    )

    snapshot["approval_id"] = (
        "approval-forbidden"
    )

    ctx = FakeWorkflowContext(
        {
            module.SAFE_COMMUNICATION_CONTEXT_STATE_KEY:
                snapshot
        }
    )

    with pytest.raises(ValidationError):
        module.load_safe_communication_context(
            ctx
        )


def test_store_then_load_round_trip_is_exact():
    module = _module()

    ctx = FakeWorkflowContext()

    original = _snapshot()

    module.store_safe_communication_context(
        ctx,
        original,
    )

    restored = (
        module.load_safe_communication_context(
            ctx
        )
    )

    assert restored == original
    assert restored.model_dump(
        mode="json"
    ) == original.model_dump(
        mode="json"
    )


def test_state_boundary_contains_no_channel_or_operational_authority():
    module = _module()

    source = inspect.getsource(
        module
    ).casefold()

    required = {
        "set_state",
        "get_state",
        "model_dump",
        "model_validate",
    }

    for value in required:
        assert value.casefold() in source

    forbidden = {
        "microsoft_teams",
        "src.channels.teams",
        "foundryagent",
        "agents.run_communication",
        "agentsession",
        "procedureruntimestate",
        "operationalcontext",
        "procedurecontinuationcontext",
        "subscription_id",
        "resource_group",
        "vm_name",
        "tenant_id",
        "approval_id",
        "conversation_id",
        "capability_id",
        "operation_action",
        "resolved_parameters",
        "mcp",
    }

    for value in forbidden:
        assert value.casefold() not in source