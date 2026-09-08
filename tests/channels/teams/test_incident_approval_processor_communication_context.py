from __future__ import annotations

from dataclasses import fields
import inspect
from types import SimpleNamespace

import pytest

from src.channels.teams.incident_approval_processor import (
    TeamsIncidentApprovalProcessingResult,
)

from src.communication.checkpoint_recovery import (
    CommunicationCheckpointRecoveryError,
)

from src.communication.context import (
    SafeCommunicationContext,
)

from tests.channels.teams.test_incident_approval_processor import (
    CHECKPOINT_ID,
    FakeStore,
    FakeWorkflow,
    create_instruction,
    create_invocation,
)


WORKFLOW_NAME = "incident-resolution"


def _safe_context() -> SafeCommunicationContext:
    return SafeCommunicationContext(
        alert_id="ALERT-SAFE-HANDOFF-001",
        technical_domain="azure",
        corporate_criticality="high",
        affected_resource="vm-display-safe",
        technical_summary=(
            "Synthetic governed incident."
        ),
        procedure_id="PROC-SAFE-HANDOFF-001",
        procedure_name="Safe handoff procedure",
    )


def _workflow(events):
    workflow = FakeWorkflow(
        events
    )

    workflow.name = WORKFLOW_NAME

    return workflow


def test_processing_result_contract_carries_safe_context():
    names = {
        item.name
        for item in fields(
            TeamsIncidentApprovalProcessingResult
        )
    }

    assert names == {
        "workflow_result",
        "approval_evidence",
        "safe_communication_context",
    }


@pytest.mark.asyncio
async def test_processor_recovers_exact_checkpoint_context_and_returns_it(
    monkeypatch,
):
    import src.channels.teams.incident_approval_processor as processor

    invocation = create_invocation()
    instruction = create_instruction(
        approved=True
    )

    restored_request = object()
    approval_evidence = object()
    workflow_result = object()
    safe_context = _safe_context()

    checkpoint_storage = object()

    workflow = _workflow(
        [
            SimpleNamespace(
                type="output",
                data=workflow_result,
            )
        ]
    )

    store = FakeStore()

    recovery_calls = []

    monkeypatch.setattr(
        processor,
        "resolve_approval_channel_action",
        lambda **kwargs: instruction,
        raising=False,
    )

    async def fake_restore(
        **kwargs,
    ):
        return restored_request

    async def fake_recover(
        **kwargs,
    ):
        recovery_calls.append(
            kwargs
        )

        return safe_context

    monkeypatch.setattr(
        processor,
        "restore_and_verify_pending_request",
        fake_restore,
        raising=False,
    )

    monkeypatch.setattr(
        processor,
        "recover_safe_communication_context_from_checkpoint",
        fake_recover,
        raising=False,
    )

    monkeypatch.setattr(
        processor,
        "build_teams_approval_evidence_from_request",
        lambda **kwargs: approval_evidence,
        raising=False,
    )

    result = await (
        processor
        .process_authorized_teams_incident_approval(
            invocation=invocation,
            store=store,
            workflow=workflow,
            checkpoint_storage=checkpoint_storage,
        )
    )

    assert (
        result.safe_communication_context
        is safe_context
    )

    assert recovery_calls == [
        {
            "checkpoint_storage":
                checkpoint_storage,
            "workflow_name":
                WORKFLOW_NAME,
            "checkpoint_id":
                CHECKPOINT_ID,
        }
    ]


@pytest.mark.asyncio
async def test_safe_context_recovery_occurs_after_restore_before_claim(
    monkeypatch,
):
    import src.channels.teams.incident_approval_processor as processor

    invocation = create_invocation()
    instruction = create_instruction(
        approved=True
    )

    safe_context = _safe_context()

    sequence = []

    class SequencedStore(
        FakeStore
    ):
        def claim(
            self,
            *,
            approval_id,
            approved,
        ):
            sequence.append(
                "claim"
            )

            return super().claim(
                approval_id=approval_id,
                approved=approved,
            )

        def complete(
            self,
            approval_id,
        ):
            sequence.append(
                "complete"
            )

            return super().complete(
                approval_id
            )

    class SequencedWorkflow(
        FakeWorkflow
    ):
        def __init__(
            self,
        ):
            super().__init__(
                [
                    SimpleNamespace(
                        type="output",
                        data=object(),
                    )
                ]
            )

            self.name = WORKFLOW_NAME

        async def run(
            self,
            **kwargs,
        ):
            sequence.append(
                "response"
            )

            async for event in super().run(
                **kwargs
            ):
                yield event

    store = SequencedStore()
    workflow = SequencedWorkflow()
    checkpoint_storage = object()

    def fake_resolve(
        **kwargs,
    ):
        sequence.append(
            "resolve"
        )

        return instruction

    async def fake_restore(
        **kwargs,
    ):
        sequence.append(
            "restore"
        )

        return object()

    async def fake_recover(
        **kwargs,
    ):
        sequence.append(
            "recover"
        )

        return safe_context

    def fake_evidence(
        **kwargs,
    ):
        sequence.append(
            "evidence"
        )

        return object()

    monkeypatch.setattr(
        processor,
        "resolve_approval_channel_action",
        fake_resolve,
        raising=False,
    )

    monkeypatch.setattr(
        processor,
        "restore_and_verify_pending_request",
        fake_restore,
        raising=False,
    )

    monkeypatch.setattr(
        processor,
        "recover_safe_communication_context_from_checkpoint",
        fake_recover,
        raising=False,
    )

    monkeypatch.setattr(
        processor,
        "build_teams_approval_evidence_from_request",
        fake_evidence,
        raising=False,
    )

    await (
        processor
        .process_authorized_teams_incident_approval(
            invocation=invocation,
            store=store,
            workflow=workflow,
            checkpoint_storage=checkpoint_storage,
        )
    )

    assert sequence == [
        "resolve",
        "restore",
        "recover",
        "claim",
        "response",
        "evidence",
        "complete",
    ]


@pytest.mark.asyncio
async def test_safe_context_recovery_failure_blocks_approval_claim(
    monkeypatch,
):
    import src.channels.teams.incident_approval_processor as processor

    invocation = create_invocation()
    instruction = create_instruction(
        approved=True
    )

    workflow = _workflow(
        [
            SimpleNamespace(
                type="output",
                data=object(),
            )
        ]
    )

    store = FakeStore()
    checkpoint_storage = object()

    evidence_calls = []

    monkeypatch.setattr(
        processor,
        "resolve_approval_channel_action",
        lambda **kwargs: instruction,
        raising=False,
    )

    async def fake_restore(
        **kwargs,
    ):
        return object()

    async def fake_recover(
        **kwargs,
    ):
        raise CommunicationCheckpointRecoveryError(
            "synthetic communication context "
            "recovery failure"
        )

    monkeypatch.setattr(
        processor,
        "restore_and_verify_pending_request",
        fake_restore,
        raising=False,
    )

    monkeypatch.setattr(
        processor,
        "recover_safe_communication_context_from_checkpoint",
        fake_recover,
        raising=False,
    )

    monkeypatch.setattr(
        processor,
        "build_teams_approval_evidence_from_request",
        lambda **kwargs: evidence_calls.append(
            kwargs
        ),
        raising=False,
    )

    with pytest.raises(
        CommunicationCheckpointRecoveryError,
        match=(
            "synthetic communication context "
            "recovery failure"
        ),
    ):
        await (
            processor
            .process_authorized_teams_incident_approval(
                invocation=invocation,
                store=store,
                workflow=workflow,
                checkpoint_storage=checkpoint_storage,
            )
        )

    assert store.claim_calls == []
    assert store.complete_calls == []
    assert workflow.run_calls == []
    assert evidence_calls == []


def test_processor_only_transports_safe_context_without_presenting_it():
    import src.channels.teams.incident_approval_processor as processor

    source = inspect.getsource(
        processor
    ).casefold()

    assert (
        "recover_safe_communication_context_from_checkpoint"
        in source
    )

    assert (
        "safe_communication_context"
        in source
    )

    forbidden = {
        "build_runtime_communication_request",
        "run_communication",
        "communicationagentadapter",
        "send_teams_message",
        "render_incident_terminal_result",
    }

    for value in forbidden:
        assert value.casefold() not in source