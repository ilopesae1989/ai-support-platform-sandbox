import pytest

from pydantic import (
    ValidationError,
)

from src.runtime.procedure.approval_channel import (
    ApprovalChannelAction,
    ApprovalDecision,
)

from src.runtime.procedure.approval_correlation import (
    ApprovalCorrelationNotFoundError,
    PendingApprovalCorrelation,
)

from src.runtime.procedure.approval_resolution import (
    ApprovalResumeInstruction,
    resolve_approval_channel_action,
)

from src.runtime.procedure.approval_store import (
    SqlitePendingApprovalStore,
)


APPROVAL_ID = (
    "apr-11111111-1111-4111-"
    "8111-111111111111"
)

WORKFLOW_ID = (
    "wf-11111111-1111-4111-"
    "8111-111111111111"
)

REQUEST_ID = (
    "req-agent-framework-001"
)

CHECKPOINT_ID = (
    "checkpoint-hitl-001"
)


def create_store(
    tmp_path,
) -> SqlitePendingApprovalStore:
    store = (
        SqlitePendingApprovalStore(
            tmp_path
            / "pending-approvals.db"
        )
    )

    store.register(
        PendingApprovalCorrelation(
            approval_id=(
                APPROVAL_ID
            ),

            workflow_id=(
                WORKFLOW_ID
            ),

            request_id=(
                REQUEST_ID
            ),

            checkpoint_id=(
                CHECKPOINT_ID
            ),
        )
    )

    return store


def test_approve_resolves_backend_resume_identity(
    tmp_path,
):
    store = (
        create_store(
            tmp_path
        )
    )

    action = (
        ApprovalChannelAction(
            approval_id=(
                APPROVAL_ID
            ),

            decision=(
                ApprovalDecision.APPROVE
            ),
        )
    )

    instruction = (
        resolve_approval_channel_action(
            action=action,
            store=store,
        )
    )

    assert (
        instruction
        == ApprovalResumeInstruction(
            approval_id=(
                APPROVAL_ID
            ),

            workflow_id=(
                WORKFLOW_ID
            ),

            request_id=(
                REQUEST_ID
            ),

            checkpoint_id=(
                CHECKPOINT_ID
            ),

            approved=True,
        )
    )


def test_reject_resolves_same_backend_identity(
    tmp_path,
):
    store = (
        create_store(
            tmp_path
        )
    )

    action = (
        ApprovalChannelAction(
            approval_id=(
                APPROVAL_ID
            ),

            decision=(
                ApprovalDecision.REJECT
            ),
        )
    )

    instruction = (
        resolve_approval_channel_action(
            action=action,
            store=store,
        )
    )

    assert (
        instruction.approval_id
        == APPROVAL_ID
    )

    assert (
        instruction.workflow_id
        == WORKFLOW_ID
    )

    assert (
        instruction.request_id
        == REQUEST_ID
    )

    assert (
        instruction.checkpoint_id
        == CHECKPOINT_ID
    )

    assert (
        instruction.approved
        is False
    )


def test_unknown_approval_id_fails_closed(
    tmp_path,
):
    store = (
        create_store(
            tmp_path
        )
    )

    action = (
        ApprovalChannelAction(
            approval_id=(
                "apr-attacker"
            ),

            decision=(
                ApprovalDecision.APPROVE
            ),
        )
    )

    with pytest.raises(
        ApprovalCorrelationNotFoundError,
    ):
        resolve_approval_channel_action(
            action=action,
            store=store,
        )


def test_channel_cannot_choose_request_or_checkpoint(
    tmp_path,
):
    store = (
        create_store(
            tmp_path
        )
    )

    action = (
        ApprovalChannelAction(
            approval_id=(
                APPROVAL_ID
            ),

            decision=(
                ApprovalDecision.APPROVE
            ),
        )
    )

    instruction = (
        resolve_approval_channel_action(
            action=action,
            store=store,
        )
    )

    # Estos valores sólo pueden proceder del store.
    assert (
        instruction.request_id
        == REQUEST_ID
    )

    assert (
        instruction.checkpoint_id
        == CHECKPOINT_ID
    )

    assert (
        instruction.workflow_id
        == WORKFLOW_ID
    )


def test_resume_instruction_contains_no_operational_authority(
    tmp_path,
):
    instruction = (
        resolve_approval_channel_action(
            action=(
                ApprovalChannelAction(
                    approval_id=(
                        APPROVAL_ID
                    ),

                    decision=(
                        ApprovalDecision.APPROVE
                    ),
                )
            ),

            store=(
                create_store(
                    tmp_path
                )
            ),
        )
    )

    assert set(
        instruction.model_dump()
    ) == {
        "approval_id",
        "workflow_id",
        "request_id",
        "checkpoint_id",
        "approved",
    }

    forbidden_fields = {
        "alert_id",
        "procedure_id",
        "procedure_version",
        "step_id",
        "capability_id",
        "operation_action",
        "operation_domain",
        "operation_kind",
        "target_resource",
        "required_parameters",
        "resolved_parameters",
        "subscription_id",
        "resource_group",
        "vm_name",
        "tenant_id",
    }

    assert (
        forbidden_fields
        .isdisjoint(
            instruction.model_dump()
        )
    )


def test_resume_instruction_is_immutable(
    tmp_path,
):
    instruction = (
        resolve_approval_channel_action(
            action=(
                ApprovalChannelAction(
                    approval_id=(
                        APPROVAL_ID
                    ),

                    decision=(
                        ApprovalDecision.APPROVE
                    ),
                )
            ),

            store=(
                create_store(
                    tmp_path
                )
            ),
        )
    )

    with pytest.raises(
        ValidationError,
    ):
        instruction.request_id = (
            "req-attacker"
        )


def test_resolution_requires_valid_channel_action(
    tmp_path,
):
    store = (
        create_store(
            tmp_path
        )
    )

    with pytest.raises(
        TypeError,
    ):
        resolve_approval_channel_action(
            action={
                "approval_id": (
                    APPROVAL_ID
                ),

                "decision": (
                    "approve"
                ),
            },
            store=store,
        )