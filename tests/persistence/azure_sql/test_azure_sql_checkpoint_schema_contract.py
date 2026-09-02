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
    / "002_workflow_checkpoints.sql"
)


ADAPTER_PATH = (
    REPO_ROOT
    / "src"
    / "persistence"
    / "azure_sql"
    / "checkpoint_storage.py"
)


def _migration_text() -> str:
    assert MIGRATION_PATH.is_file(), (
        "Debe existir "
        "platform/azure-sql/migrations/"
        "002_workflow_checkpoints.sql"
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


def _table_block() -> str:
    normalized = _normalized()

    match = re.search(
        (
            r"CREATE TABLE "
            r"DBO\.WORKFLOW_CHECKPOINTS "
            r"\((.*?)\);"
        ),
        normalized,
        flags=re.DOTALL,
    )

    assert match is not None, (
        "Falta CREATE TABLE "
        "dbo.workflow_checkpoints"
    )

    return match.group(
        1
    )


def test_migration_exists_and_is_sql_only():
    text = _migration_text()

    lower = text.lower()

    for forbidden in (
        "cosmos",
        "teams-poc",
        "poc-sbx",
        "func-agent-tools-teams-poc",
    ):
        assert forbidden not in lower


def test_migration_creates_exactly_one_checkpoint_table():
    normalized = _normalized()

    tables = re.findall(
        r"CREATE TABLE DBO\.([A-Z0-9_]+)",
        normalized,
    )

    assert tables == [
        "WORKFLOW_CHECKPOINTS",
    ]


def test_checkpoint_columns_match_adapter_contract():
    block = _table_block()

    assert re.search(
        (
            r"CHECKPOINT_ID "
            r"NVARCHAR\(256\) "
            r"NOT NULL"
        ),
        block,
    )

    assert re.search(
        (
            r"WORKFLOW_NAME "
            r"NVARCHAR\(256\) "
            r"NOT NULL"
        ),
        block,
    )

    assert (
        "CHECKPOINT_TIMESTAMP "
        "DATETIMEOFFSET(7) "
        "NOT NULL"
        in block
    )

    assert (
        "PAYLOAD_JSON "
        "NVARCHAR(MAX) "
        "NOT NULL"
        in block
    )


def test_checkpoint_id_is_primary_key():
    block = _table_block()

    assert (
        "PRIMARY KEY"
        in block
    )

    assert (
        "(CHECKPOINT_ID)"
        in block
    )


def test_payload_is_validated_as_json():
    block = _table_block()

    assert (
        "CHECK"
        in block
    )

    assert (
        "ISJSON(PAYLOAD_JSON) = 1"
        in block
    )


def test_workflow_order_index_matches_query_pattern():
    normalized = _normalized()

    pattern = (
        r"CREATE INDEX "
        r"IX_WORKFLOW_CHECKPOINTS_WORKFLOW_ORDER "
        r"ON DBO\.WORKFLOW_CHECKPOINTS "
        r"\(\s*"
        r"WORKFLOW_NAME\s+ASC\s*,\s*"
        r"CHECKPOINT_TIMESTAMP\s+DESC\s*,\s*"
        r"CHECKPOINT_ID\s+DESC"
        r"\s*\)"
    )

    assert re.search(
        pattern,
        normalized,
    )


def test_migration_is_atomic_and_fail_closed():
    normalized = _normalized()

    for required in (
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


def test_migration_fails_closed_if_table_already_exists():
    normalized = _normalized()

    assert (
        "OBJECT_ID("
        in normalized
    )

    assert (
        "DBO.WORKFLOW_CHECKPOINTS"
        in normalized
    )

    assert (
        "IS NOT NULL"
        in normalized
    )

    assert re.search(
        r"THROW\s+52\d{3}",
        normalized,
    )


def test_migration_has_no_destructive_security_or_batch_surface():
    text = _migration_text()

    normalized = " ".join(
        text.upper().split()
    )

    for forbidden in (
        "DROP TABLE",
        "TRUNCATE TABLE",
        "MERGE ",
        "CREATE DATABASE",
        "CREATE USER",
        "CREATE LOGIN",
        "ALTER ROLE",
        "PASSWORD=",
        "PASSWORD =",
        "AUTHENTICATION=SQLPASSWORD",
    ):
        assert forbidden not in normalized

    assert not re.search(
        r"(?m)^\s*GO\s*$",
        text,
        flags=re.IGNORECASE,
    )


def test_adapter_and_migration_use_same_table_and_column_names():
    migration = _normalized()

    adapter = ADAPTER_PATH.read_text(
        encoding="utf-8"
    ).upper()

    for token in (
        "DBO.WORKFLOW_CHECKPOINTS",
        "CHECKPOINT_ID",
        "WORKFLOW_NAME",
        "CHECKPOINT_TIMESTAMP",
        "PAYLOAD_JSON",
    ):
        assert token in migration
        assert token in adapter