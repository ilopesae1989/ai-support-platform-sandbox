from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace

import inspect

import pytest

from src.communication.context import (
    SafeCommunicationContext,
)

from src.communication.context_state import (
    SAFE_COMMUNICATION_CONTEXT_STATE_KEY,
)


class FakeCheckpointStorage:
    def __init__(
        self,
        checkpoints,
    ) -> None:
        self.checkpoints = list(
            checkpoints
        )
        self.calls = []

    async def list_checkpoints(
        self,
        *,
        workflow_name,
    ):
        self.calls.append(
            workflow_name
        )

        return list(
            self.checkpoints
        )


def _module():
    try:
        return import_module(
            "src.communication.checkpoint_recovery"
        )
    except ModuleNotFoundError as exc:
        if (
            exc.name
            != "src.communication.checkpoint_recovery"
        ):
            raise

        pytest.fail(
            "Safe communication checkpoint recovery "
            "is not implemented.",
            pytrace=False,
        )


def _safe_payload():
    return SafeCommunicationContext(
        alert_id="ALERT-SAFE-001",
        technical_domain="azure",
        corporate_criticality="high",
        affected_resource="vm-display-safe",
        technical_summary=(
            "Synthetic governed incident."
        ),
        procedure_id="PROC-SAFE-001",
        procedure_name="Safe recovery procedure",
    ).model_dump(
        mode="json"
    )


def _checkpoint(
    *,
    checkpoint_id,
    state=None,
):
    return SimpleNamespace(
        checkpoint_id=checkpoint_id,
        state=(
            state
            if state is not None
            else {}
        ),
    )


@pytest.mark.asyncio
async def test_recovers_exact_safe_context_from_exact_checkpoint():
    module = _module()

    payload = _safe_payload()

    storage = FakeCheckpointStorage(
        [
            _checkpoint(
                checkpoint_id="cp-other",
                state={},
            ),
            _checkpoint(
                checkpoint_id="cp-target",
                state={
                    SAFE_COMMUNICATION_CONTEXT_STATE_KEY:
                        payload
                },
            ),
        ]
    )

    result = await (
        module
        .recover_safe_communication_context_from_checkpoint(
            checkpoint_storage=storage,
            workflow_name="incident-resolution",
            checkpoint_id="cp-target",
        )
    )

    assert (
        type(result)
        is SafeCommunicationContext
    )

    assert result.model_dump(
        mode="json"
    ) == payload

    assert storage.calls == [
        "incident-resolution"
    ]


@pytest.mark.asyncio
async def test_missing_checkpoint_fails_closed():
    module = _module()

    storage = FakeCheckpointStorage(
        [
            _checkpoint(
                checkpoint_id="cp-other",
                state={},
            )
        ]
    )

    with pytest.raises(
        module.CommunicationCheckpointRecoveryError
    ):
        await (
            module
            .recover_safe_communication_context_from_checkpoint(
                checkpoint_storage=storage,
                workflow_name="incident-resolution",
                checkpoint_id="cp-target",
            )
        )


@pytest.mark.asyncio
async def test_duplicate_exact_checkpoint_id_fails_closed():
    module = _module()

    payload = _safe_payload()

    storage = FakeCheckpointStorage(
        [
            _checkpoint(
                checkpoint_id="cp-target",
                state={
                    SAFE_COMMUNICATION_CONTEXT_STATE_KEY:
                        payload
                },
            ),
            _checkpoint(
                checkpoint_id="cp-target",
                state={
                    SAFE_COMMUNICATION_CONTEXT_STATE_KEY:
                        payload
                },
            ),
        ]
    )

    with pytest.raises(
        module.CommunicationCheckpointRecoveryError
    ):
        await (
            module
            .recover_safe_communication_context_from_checkpoint(
                checkpoint_storage=storage,
                workflow_name="incident-resolution",
                checkpoint_id="cp-target",
            )
        )


@pytest.mark.asyncio
async def test_missing_safe_context_state_fails_closed():
    module = _module()

    storage = FakeCheckpointStorage(
        [
            _checkpoint(
                checkpoint_id="cp-target",
                state={
                    "procedure_runtime_state": {}
                },
            )
        ]
    )

    with pytest.raises(
        module.CommunicationCheckpointRecoveryError
    ):
        await (
            module
            .recover_safe_communication_context_from_checkpoint(
                checkpoint_storage=storage,
                workflow_name="incident-resolution",
                checkpoint_id="cp-target",
            )
        )


@pytest.mark.asyncio
async def test_invalid_safe_context_payload_fails_closed():
    module = _module()

    payload = _safe_payload()

    payload[
        "approval_id"
    ] = "must-not-be-accepted"

    storage = FakeCheckpointStorage(
        [
            _checkpoint(
                checkpoint_id="cp-target",
                state={
                    SAFE_COMMUNICATION_CONTEXT_STATE_KEY:
                        payload
                },
            )
        ]
    )

    with pytest.raises(
        module.CommunicationCheckpointRecoveryError
    ):
        await (
            module
            .recover_safe_communication_context_from_checkpoint(
                checkpoint_storage=storage,
                workflow_name="incident-resolution",
                checkpoint_id="cp-target",
            )
        )


@pytest.mark.asyncio
async def test_requires_checkpoint_storage_list_protocol():
    module = _module()

    with pytest.raises(TypeError):
        await (
            module
            .recover_safe_communication_context_from_checkpoint(
                checkpoint_storage=object(),
                workflow_name="incident-resolution",
                checkpoint_id="cp-target",
            )
        )


def test_checkpoint_recovery_boundary_is_channel_agnostic():
    module = _module()

    source = inspect.getsource(
        module
    ).casefold()

    required = {
        "list_checkpoints",
        "checkpoint_id",
        "safe_communication_context",
        "model_validate",
    }

    for value in required:
        assert value.casefold() in source

    forbidden = {
        "src.channels.teams",
        "microsoft_teams",
        "authorizedteamsapprovalinvocation",
        "approvalrequest",
        "procedureruntimestate",
        "approval_id",
        "conversation_id",
        "tenant_id",
        "foundryagent",
        "agentsession",
        "mcp",
        "get_latest",
    }

    for value in forbidden:
        assert value.casefold() not in source