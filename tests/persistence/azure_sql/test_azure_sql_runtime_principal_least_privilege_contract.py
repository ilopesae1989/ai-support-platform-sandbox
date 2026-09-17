from __future__ import annotations

import re

from pathlib import Path


REPO_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)


RUNTIME_PRINCIPAL_SQL = (
    REPO_ROOT
    / "platform"
    / "azure-sql"
    / "security"
    / "runtime-principal.sql"
)


EXPECTED_PERMISSIONS = {
    "WORKFLOW_CHECKPOINTS": {
        "SELECT",
        "INSERT",
        "UPDATE",
        "DELETE",
    },
    "TEAMS_CONVERSATION_BINDINGS": {
        "SELECT",
        "INSERT",
        "UPDATE",
    },
    "PENDING_APPROVALS": {
        "SELECT",
        "INSERT",
        "UPDATE",
    },
    "INCIDENT_CONTINUATION_JOBS": {
        "SELECT",
        "INSERT",
        "UPDATE",
    },
    "OPERATION_DISPATCH_CLAIMS": {
        "SELECT",
        "INSERT",
    },
    "AGENT_SESSIONS": {
        "SELECT",
        "INSERT",
        "UPDATE",
        "DELETE",
    },
    "WAIT_RECHECK_CONSUMPTION_CLAIMS": {
        "SELECT",
        "INSERT",
        "UPDATE",
    },
}


GUID_PATTERN = re.compile(
    r"\b"
    r"[0-9A-F]{8}-"
    r"[0-9A-F]{4}-"
    r"[0-9A-F]{4}-"
    r"[0-9A-F]{4}-"
    r"[0-9A-F]{12}"
    r"\b",
    flags=re.IGNORECASE,
)


GRANT_PATTERN = re.compile(
    (
        r"GRANT\s+"
        r"(?P<permissions>"
        r"(?:SELECT|INSERT|UPDATE|DELETE)"
        r"(?:\s*,\s*"
        r"(?:SELECT|INSERT|UPDATE|DELETE)"
        r")*"
        r")"
        r"\s+ON\s+OBJECT::DBO\."
        r"(?P<table>[A-Z0-9_]+)"
        r"\s+TO\s+"
        r"(?P<principal>"
        r"\[[^\]]+\]"
        r"|[A-Z0-9_.$()]+"
        r")"
        r"\s*;"
    ),
    flags=re.IGNORECASE,
)


def _script_text() -> str:
    assert RUNTIME_PRINCIPAL_SQL.is_file(), (
        "Debe existir "
        "platform/azure-sql/security/"
        "runtime-principal.sql"
    )

    return RUNTIME_PRINCIPAL_SQL.read_text(
        encoding="utf-8"
    )


def _normalized(
    text: str,
) -> str:
    return " ".join(
        text
        .upper()
        .split()
    )


def test_runtime_principal_is_exact_least_privilege_contract():
    text = _script_text()

    normalized = _normalized(
        text
    )

    assert (
        normalized.count(
            "CREATE USER "
        )
        == 1
    )

    assert (
        " WITH SID "
        in normalized
    )

    assert (
        "TYPE = E"
        in normalized
    )

    assert (
        "FROM EXTERNAL PROVIDER"
        not in normalized
    )

    assert (
        GUID_PATTERN.search(
            text
        )
        is None
    )

    assert (
        "ID-SQL-RUNTIME-ICENTER-SBX"
        not in normalized
    )

    forbidden = (
        "ALTER ROLE",
        "DB_DATAREADER",
        "DB_DATAWRITER",
        "DB_OWNER",
        "ON SCHEMA::",
        "GRANT ALL",
        "GRANT CONTROL",
        "GRANT ALTER",
        "GRANT EXECUTE",
        "GRANT REFERENCES",
        "GRANT VIEW DEFINITION",
        "WITH GRANT OPTION",
        "CREATE LOGIN",
        "CREATE ROLE",
        "DROP ",
        "TRUNCATE ",
    )

    for token in forbidden:
        assert token not in normalized

    actual_permissions: dict[
        str,
        set[str],
    ] = {}

    principals: set[str] = set()

    for match in GRANT_PATTERN.finditer(
        normalized
    ):
        table = (
            match
            .group("table")
            .upper()
        )

        permissions = {
            value.strip().upper()
            for value in (
                match
                .group("permissions")
                .split(",")
            )
        }

        assert table not in actual_permissions, (
            "Cada tabla debe tener "
            "un único GRANT consolidado: "
            + table
        )

        actual_permissions[
            table
        ] = permissions

        principals.add(
            match
            .group("principal")
            .upper()
        )

    assert actual_permissions == (
        EXPECTED_PERMISSIONS
    )

    assert len(principals) == 1

    assert (
        "DELETE"
        in actual_permissions[
            "WORKFLOW_CHECKPOINTS"
        ]
    )

    assert (
        "DELETE"
        in actual_permissions[
            "AGENT_SESSIONS"
        ]
    )

    for table in (
        "TEAMS_CONVERSATION_BINDINGS",
        "PENDING_APPROVALS",
        "INCIDENT_CONTINUATION_JOBS",
        "OPERATION_DISPATCH_CLAIMS",
        "WAIT_RECHECK_CONSUMPTION_CLAIMS",
    ):
        assert (
            "DELETE"
            not in actual_permissions[
                table
            ]
        )