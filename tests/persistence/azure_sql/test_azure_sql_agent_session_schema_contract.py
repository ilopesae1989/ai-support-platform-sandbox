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
    / "003_agent_sessions.sql"
)


def _migration_text() -> str:
    assert MIGRATION_PATH.is_file(), (
        "Debe existir "
        "platform/azure-sql/migrations/"
        "003_agent_sessions.sql"
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
            r"DBO\.AGENT_SESSIONS "
            r"\((.*?)\);"
        ),
        normalized,
        flags=re.DOTALL,
    )

    assert match is not None, (
        "Falta CREATE TABLE "
        "dbo.agent_sessions"
    )

    return match.group(
        1
    )


def test_migration_exists_and_is_sql_only():
    text = _migration_text()

    lower = text.lower()

    for forbidden in (
        "cosmos",
        "redis",
        "sqlite",
        "teams-poc",
        "poc-sbx",
        "func-agent-tools-teams-poc",
    ):
        assert forbidden not in lower


def test_migration_creates_exactly_one_agent_session_table():
    normalized = _normalized()

    tables = re.findall(
        r"CREATE TABLE DBO\.([A-Z0-9_]+)",
        normalized,
    )

    assert tables == [
        "AGENT_SESSIONS",
    ]


def test_agent_session_columns_are_exact_and_minimal():
    block = _table_block()

    assert re.search(
        (
            r"SESSION_STORE_ID "
            r"NVARCHAR\(256\) "
            r"NOT NULL"
        ),
        block,
    )

    assert (
        "PAYLOAD_JSON "
        "NVARCHAR(MAX) "
        "NOT NULL"
        in block
    )

    forbidden_columns = (
        "TENANT_ID",
        "CONVERSATION_ID",
        "AGENT_KEY",
        "SERVICE_SESSION_ID",
        "SESSION_ID ",
        "CREATED_AT",
        "UPDATED_AT",
        "USER_ID",
    )

    for forbidden in forbidden_columns:
        assert forbidden not in block


def test_session_store_id_is_clustered_primary_key():
    block = _table_block()

    assert (
        "CONSTRAINT PK_AGENT_SESSIONS"
        in block
    )

    assert (
        "PRIMARY KEY CLUSTERED "
        "(SESSION_STORE_ID)"
        in block
    )


def test_payload_json_is_fail_closed_validated():
    block = _table_block()

    assert (
        "CONSTRAINT CK_AGENT_SESSIONS_PAYLOAD_JSON"
        in block
    )

    assert (
        "CHECK"
        in block
    )

    assert (
        "ISJSON(PAYLOAD_JSON) = 1"
        in block
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
        "DBO.AGENT_SESSIONS"
        in normalized
    )

    assert (
        "IS NOT NULL"
        in normalized
    )

    assert re.search(
        r"THROW\s+53\d{3}",
        normalized,
    )


def test_migration_has_no_runtime_dml_or_security_authority():
    text = _migration_text()

    normalized = " ".join(
        text.upper().split()
    )

    for forbidden in (
        "INSERT INTO",
        "UPDATE ",
        "DELETE FROM",
        "MERGE ",
        "DROP TABLE",
        "TRUNCATE TABLE",
        "CREATE DATABASE",
        "CREATE USER",
        "CREATE LOGIN",
        "ALTER ROLE",
        "GRANT ",
        "DENY ",
        "REVOKE ",
        "PASSWORD=",
        "PASSWORD =",
        "AUTHENTICATION=SQLPASSWORD",
        "AUTHENTICATION = SQLPASSWORD",
    ):
        assert forbidden not in normalized

    assert not re.search(
        r"(?m)^\s*GO\s*$",
        text,
        flags=re.IGNORECASE,
    )


def test_migration_does_not_duplicate_agent_session_payload_fields():
    block = _table_block()

    assert (
        block.count(
            "SESSION_STORE_ID"
        )
        >= 2
    )

    assert (
        block.count(
            "PAYLOAD_JSON"
        )
        >= 2
    )

    for forbidden in (
        "SERVICE_SESSION_ID",
        "AGENT_SESSION_ID",
        "SESSION_STATE",
        "STATE_JSON",
        "HISTORY_JSON",
        "MESSAGES_JSON",
    ):
        assert forbidden not in block
