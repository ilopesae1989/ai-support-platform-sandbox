from __future__ import annotations

import ast

from pathlib import Path

from src.channels.teams.conversation_binding_store import (
    SqliteTeamsConversationBindingStore,
)

from src.channels.teams.incident_continuation_store import (
    SqliteIncidentContinuationStore,
)

from src.runtime.procedure.approval_correlation import (
    PendingApprovalCorrelation,
)

from src.runtime.procedure.approval_store import (
    SqlitePendingApprovalStore,
)

from src.workflows.incident_resolution.operation_dispatch_ledger import (
    SqliteOperationDispatchLedger,
)


SQLITE_SOURCES = (
    "src/runtime/procedure/approval_store.py",
    "src/workflows/incident_resolution/operation_dispatch_ledger.py",
    "src/channels/teams/incident_continuation_store.py",
    "src/channels/teams/conversation_binding_store.py",
)


def test_every_connect_context_uses_closing():
    expected = {
        "src/runtime/procedure/approval_store.py": 7,
        "src/workflows/incident_resolution/operation_dispatch_ledger.py": 2,
        "src/channels/teams/incident_continuation_store.py": 5,
        "src/channels/teams/conversation_binding_store.py": 3,
    }

    total = 0

    for relative in SQLITE_SOURCES:
        text = Path(
            relative
        ).read_text(
            encoding="utf-8"
        )

        tree = ast.parse(
            text
        )

        count = 0

        assert "contextlib" in text
        assert "closing" in text

        for node in ast.walk(
            tree
        ):
            if not isinstance(
                node,
                ast.With,
            ):
                continue

            expressions = [
                ast.unparse(
                    item.context_expr
                )
                for item
                in node.items
            ]

            if not any(
                "_connect()"
                in expression
                for expression
                in expressions
            ):
                continue

            count += 1
            total += 1

            assert any(
                "closing("
                in expression
                for expression
                in expressions
            )

            assert (
                "connection"
                in expressions
            )

        assert count == expected[
            relative
        ]

    assert total == 17


def test_database_handles_are_released_after_operations(
    tmp_path,
):
    approval_db = (
        tmp_path
        / "approvals.db"
    )

    dispatch_db = (
        tmp_path
        / "dispatch.db"
    )

    continuation_db = (
        tmp_path
        / "continuation.db"
    )

    conversation_db = (
        tmp_path
        / "conversation.db"
    )

    approval = SqlitePendingApprovalStore(
        approval_db
    )

    approval.register(
        PendingApprovalCorrelation(
            approval_id="apr-close-test",
            workflow_id="wf-close-test",
            request_id="req-close-test",
            checkpoint_id="cp-close-test",
        )
    )

    assert (
        approval.get_consumption_record(
            "apr-close-test"
        )
        == (
            "pending",
            None,
        )
    )

    approval.claim(
        approval_id="apr-close-test",
        approved=True,
    )

    assert (
        approval.get_consumption_record(
            "apr-close-test"
        )
        == (
            "claimed",
            True,
        )
    )

    approval.complete(
        "apr-close-test"
    )

    dispatch = (
        SqliteOperationDispatchLedger(
            dispatch_db
        )
    )

    assert (
        dispatch.contains(
            "op-close-test"
        )
        is False
    )

    dispatch.claim(
        "op-close-test"
    )

    assert (
        dispatch.contains(
            "op-close-test"
        )
        is True
    )

    SqliteIncidentContinuationStore(
        continuation_db
    )

    SqliteTeamsConversationBindingStore(
        conversation_db
    )

    databases = (
        approval_db,
        dispatch_db,
        continuation_db,
        conversation_db,
    )

    for database in databases:
        assert database.exists()

        database.unlink()

        assert not database.exists()