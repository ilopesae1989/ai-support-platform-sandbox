from __future__ import annotations

import re

from pathlib import Path


REPO_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)


MIGRATION_PATH = (
    REPO_ROOT
    / "platform"
    / "azure-sql"
    / "migrations"
    / "001_persistence.sql"
)


def _migration_text() -> str:
    assert MIGRATION_PATH.is_file(), (
        "Debe existir "
        "platform/azure-sql/migrations/"
        "001_persistence.sql"
    )

    return MIGRATION_PATH.read_text(
        encoding="utf-8"
    )


def _normalized() -> str:
    return " ".join(
        _migration_text()
        .upper()
        .split()
    )


def _table_block(
    table_name: str,
) -> str:
    normalized = _normalized()

    pattern = (
        r"CREATE TABLE DBO\."
        + re.escape(
            table_name.upper()
        )
        + r"\s*\((.*?)\);"
    )

    match = re.search(
        pattern,
        normalized,
        flags=re.DOTALL,
    )

    assert match is not None, (
        "Falta CREATE TABLE dbo."
        + table_name
    )

    return match.group(
        1
    )


def test_migration_exists_and_is_not_poc_specific():
    text = _migration_text()

    lower = text.lower()

    assert "teams-poc" not in lower
    assert "poc-sbx" not in lower
    assert "func-agent-tools-teams-poc" not in lower


def test_migration_creates_exactly_four_persistence_tables():
    normalized = _normalized()

    tables = re.findall(
        r"CREATE TABLE DBO\.([A-Z0-9_]+)",
        normalized,
    )

    assert tables == [
        "OPERATION_DISPATCH_CLAIMS",
        "TEAMS_CONVERSATION_BINDINGS",
        "PENDING_APPROVALS",
        "INCIDENT_CONTINUATION_JOBS",
    ]


def test_operation_dispatch_claims_has_durable_unique_operation_authority():
    block = _table_block(
        "operation_dispatch_claims"
    )

    assert re.search(
        r"OPERATION_ID\s+NVARCHAR\(\d+\)\s+NOT NULL",
        block,
    )

    assert (
        "PRIMARY KEY"
        in block
    )

    assert (
        "(OPERATION_ID)"
        in block
    )


def test_conversation_bindings_use_exact_composite_identity():
    block = _table_block(
        "teams_conversation_bindings"
    )

    assert re.search(
        r"TENANT_ID\s+NVARCHAR\(\d+\)\s+NOT NULL",
        block,
    )

    assert re.search(
        r"CONVERSATION_ID\s+NVARCHAR\(\d+\)\s+NOT NULL",
        block,
    )

    assert re.search(
        r"SERVICE_URL\s+NVARCHAR\(\d+\)\s+NOT NULL",
        block,
    )

    assert (
        "PRIMARY KEY NONCLUSTERED "
        "(TENANT_ID, CONVERSATION_ID)"
        in block
    )


def test_pending_approvals_has_exact_correlation_columns_and_keys():
    block = _table_block(
        "pending_approvals"
    )

    for column in (
        "APPROVAL_ID",
        "WORKFLOW_ID",
        "REQUEST_ID",
        "CHECKPOINT_ID",
    ):
        assert re.search(
            column
            + r"\s+NVARCHAR\(\d+\)\s+NOT NULL",
            block,
        )

    assert (
        "PRIMARY KEY"
        in block
    )

    assert (
        "(APPROVAL_ID)"
        in block
    )

    assert (
        "UNIQUE (REQUEST_ID)"
        in block
    )


def test_pending_approvals_persists_state_and_decision_types():
    block = _table_block(
        "pending_approvals"
    )

    assert re.search(
        r"CONSUMPTION_STATUS\s+NVARCHAR\(\d+\)\s+NOT NULL",
        block,
    )

    assert re.search(
        r"APPROVED_DECISION\s+BIT\s+NULL",
        block,
    )


def test_pending_approval_state_machine_is_enforced_by_check_constraints():
    block = _table_block(
        "pending_approvals"
    )

    for status in (
        "'PENDING'",
        "'CLAIMED'",
        "'COMPLETED'",
    ):
        assert status in block

    assert (
        "CHECK"
        in block
    )

    assert (
        "CONSUMPTION_STATUS"
        in block
    )

    assert (
        "APPROVED_DECISION"
        in block
    )

    assert (
        "IS NULL"
        in block
    )

    assert (
        "IS NOT NULL"
        in block
    )


def test_continuation_jobs_has_required_durable_columns():
    block = _table_block(
        "incident_continuation_jobs"
    )

    assert re.search(
        r"APPROVAL_ID\s+NVARCHAR\(\d+\)\s+NOT NULL",
        block,
    )

    assert (
        "PAYLOAD_JSON NVARCHAR(MAX) NOT NULL"
        in block
    )

    assert re.search(
        r"STATUS\s+NVARCHAR\(\d+\)\s+NOT NULL",
        block,
    )

    assert (
        "ATTEMPT_COUNT INT NOT NULL"
        in block
    )

    assert re.search(
        r"CLAIMED_BY\s+NVARCHAR\(\d+\)\s+NULL",
        block,
    )

    assert (
        "LAST_ERROR NVARCHAR(MAX) NULL"
        in block
    )

    assert (
        "CREATED_AT FLOAT(53) NOT NULL"
        in block
    )

    assert (
        "UPDATED_AT FLOAT(53) NOT NULL"
        in block
    )

    assert (
        "(APPROVAL_ID)"
        in block
    )


def test_continuation_status_and_claim_owner_invariants_are_enforced():
    block = _table_block(
        "incident_continuation_jobs"
    )

    for status in (
        "'PENDING'",
        "'CLAIMED'",
        "'COMPLETED'",
        "'FAILED'",
    ):
        assert status in block

    assert (
        "ATTEMPT_COUNT >= 0"
        in block
    )

    assert (
        "CLAIMED_BY IS NOT NULL"
        in block
    )

    assert (
        "CLAIMED_BY IS NULL"
        in block
    )


def test_continuation_payload_is_database_validated_as_json():
    block = _table_block(
        "incident_continuation_jobs"
    )

    assert (
        "ISJSON(PAYLOAD_JSON) = 1"
        in block
    )


def test_queue_has_ordered_pending_index_for_claim_pattern():
    normalized = _normalized()

    assert re.search(
        (
            r"CREATE INDEX "
            r"IX_INCIDENT_CONTINUATION_PENDING_QUEUE "
            r"ON DBO\.INCIDENT_CONTINUATION_JOBS "
            r"\(\s*STATUS\s*,\s*"
            r"CREATED_AT\s*,\s*"
            r"APPROVAL_ID\s*\)"
        ),
        normalized,
    )

    assert (
        "WHERE STATUS = 'PENDING'"
        in normalized
    )


def test_migration_is_atomic_and_fail_closed():
    normalized = _normalized()

    for required in (
        "SET ANSI_NULLS ON",
        "SET ANSI_PADDING ON",
        "SET ANSI_WARNINGS ON",
        "SET ARITHABORT ON",
        "SET CONCAT_NULL_YIELDS_NULL ON",
        "SET NUMERIC_ROUNDABORT OFF",
        "SET QUOTED_IDENTIFIER ON",
        "SET XACT_ABORT ON",
        "BEGIN TRY",
        "BEGIN TRANSACTION",
        "COMMIT TRANSACTION",
        "BEGIN CATCH",
        "@@TRANCOUNT",
        "ROLLBACK TRANSACTION",
        "THROW",
    ):
        assert required in normalized


def test_migration_has_no_destructive_or_security_grant_surface():
    text = _migration_text()

    normalized = " ".join(
        text.upper().split()
    )

    forbidden = (
        "DROP TABLE",
        "TRUNCATE TABLE",
        "MERGE ",
        "CREATE USER",
        "ALTER ROLE",
        "CREATE LOGIN",
        "PASSWORD=",
        "PASSWORD =",
        "SECRET",
        "AUTHENTICATION=SQLPASSWORD",
    )

    for token in forbidden:
        assert token not in normalized

    assert not re.search(
        r"(?m)^\s*GO\s*$",
        text,
        flags=re.IGNORECASE,
    )


def test_adapter_table_names_are_materialized_by_migration():
    migration = _normalized()

    adapter_paths = (
        REPO_ROOT
        / "src"
        / "persistence"
        / "azure_sql"
    )

    expected = {
        "operation_dispatch_ledger.py": (
            "DBO.OPERATION_DISPATCH_CLAIMS"
        ),
        "conversation_binding_store.py": (
            "DBO.TEAMS_CONVERSATION_BINDINGS"
        ),
        "pending_approval_store.py": (
            "DBO.PENDING_APPROVALS"
        ),
        "incident_continuation_store.py": (
            "DBO.INCIDENT_CONTINUATION_JOBS"
        ),
    }

    for filename, table_name in expected.items():
        source = (
            adapter_paths
            / filename
        ).read_text(
            encoding="utf-8"
        ).upper()

        assert table_name in source
        assert table_name in migration