from dataclasses import (
    dataclass,
    field,
)

import pytest

from src.channels.teams.approval_bridge import (
    TeamsApprovalBridgeError,
    resolve_pending_approval_checkpoint,
)


REQUEST_ID = (
    "request-info-phase18-001"
)


@dataclass
class FakeCheckpoint:
    checkpoint_id: str

    pending_request_info_events: (
        dict[str, object]
    ) = field(
        default_factory=dict
    )


def create_checkpoint(
    *,
    checkpoint_id: str,
    request_ids: tuple[str, ...] = (),
) -> FakeCheckpoint:
    return FakeCheckpoint(
        checkpoint_id=checkpoint_id,

        pending_request_info_events={
            request_id: {
                "request_id": request_id,
            }
            for request_id in request_ids
        },
    )


def test_resolves_checkpoint_by_exact_pending_request_id():
    unrelated = create_checkpoint(
        checkpoint_id="checkpoint-unrelated",

        request_ids=(
            "other-request",
        ),
    )

    expected = create_checkpoint(
        checkpoint_id="checkpoint-hitl",

        request_ids=(
            REQUEST_ID,
        ),
    )

    result = (
        resolve_pending_approval_checkpoint(
            checkpoints=[
                unrelated,
                expected,
            ],

            request_id=REQUEST_ID,
        )
    )

    assert result is expected

    assert (
        result.checkpoint_id
        == "checkpoint-hitl"
    )


def test_missing_pending_request_fails_closed():
    checkpoints = [
        create_checkpoint(
            checkpoint_id="checkpoint-001",

            request_ids=(
                "other-request",
            ),
        )
    ]

    with pytest.raises(
        TeamsApprovalBridgeError
    ):
        resolve_pending_approval_checkpoint(
            checkpoints=checkpoints,
            request_id=REQUEST_ID,
        )


def test_duplicate_pending_request_fails_closed():
    checkpoints = [
        create_checkpoint(
            checkpoint_id="checkpoint-001",

            request_ids=(
                REQUEST_ID,
            ),
        ),

        create_checkpoint(
            checkpoint_id="checkpoint-002",

            request_ids=(
                REQUEST_ID,
            ),
        ),
    ]

    with pytest.raises(
        TeamsApprovalBridgeError
    ):
        resolve_pending_approval_checkpoint(
            checkpoints=checkpoints,
            request_id=REQUEST_ID,
        )

class FakePendingApprovalStore:
    def __init__(self):
        self.registered = []

    def register(
        self,
        correlation,
    ) -> None:
        self.registered.append(
            correlation
        )


def test_registers_exact_pending_approval_correlation(
    monkeypatch,
):
    import src.channels.teams.approval_bridge as approval_bridge

    request = object()

    checkpoint = create_checkpoint(
        checkpoint_id="checkpoint-hitl-001",

        request_ids=(
            REQUEST_ID,
        ),
    )

    expected_correlation = object()

    builder_calls = []

    def fake_build_pending_approval_correlation(
        *,
        request,
        request_id,
        checkpoint_id,
    ):
        builder_calls.append(
            (
                request,
                request_id,
                checkpoint_id,
            )
        )

        return expected_correlation

    monkeypatch.setattr(
        approval_bridge,
        "build_pending_approval_correlation",
        fake_build_pending_approval_correlation,
    )

    store = FakePendingApprovalStore()

    result = (
        approval_bridge
        .register_pending_approval_correlation(
            request=request,
            request_id=REQUEST_ID,
            checkpoints=[
                create_checkpoint(
                    checkpoint_id="checkpoint-other",

                    request_ids=(
                        "other-request",
                    ),
                ),
                checkpoint,
            ],
            store=store,
        )
    )

    assert result is expected_correlation

    assert builder_calls == [
        (
            request,
            REQUEST_ID,
            "checkpoint-hitl-001",
        )
    ]

    assert store.registered == [
        expected_correlation
    ]


def test_registration_does_not_occur_when_checkpoint_resolution_fails(
    monkeypatch,
):
    import src.channels.teams.approval_bridge as approval_bridge

    builder_calls = []

    def fake_build_pending_approval_correlation(
        **kwargs,
    ):
        builder_calls.append(
            kwargs
        )

        return object()

    monkeypatch.setattr(
        approval_bridge,
        "build_pending_approval_correlation",
        fake_build_pending_approval_correlation,
    )

    store = FakePendingApprovalStore()

    with pytest.raises(
        TeamsApprovalBridgeError
    ):
        approval_bridge.register_pending_approval_correlation(
            request=object(),
            request_id=REQUEST_ID,
            checkpoints=[
                create_checkpoint(
                    checkpoint_id="checkpoint-other",

                    request_ids=(
                        "other-request",
                    ),
                )
            ],
            store=store,
        )

    assert builder_calls == []
    assert store.registered == []
