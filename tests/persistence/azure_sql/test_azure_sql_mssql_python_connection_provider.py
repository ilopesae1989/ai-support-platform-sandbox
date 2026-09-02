from __future__ import annotations

import importlib
import inspect
import sys
import types

from dataclasses import (
    FrozenInstanceError,
    fields,
    is_dataclass,
)

from pathlib import Path

import pytest


MODULE_NAME = (
    "src.persistence.azure_sql."
    "connection_provider"
)


REPO_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)


MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "persistence"
    / "azure_sql"
    / "connection_provider.py"
)


SERVER = (
    "sql-ai-support-platform-sbx."
    "database.windows.net"
)

DATABASE = (
    "sqldb-ai-support-platform-sbx"
)

MANAGED_IDENTITY_CLIENT_ID = (
    "11111111-2222-4333-8444-"
    "555555555555"
)


class FakeConnection:
    pass


class ConnectRecorder:
    def __init__(
        self,
        *,
        result=None,
        error=None,
    ):
        self.result = (
            result
            if result is not None
            else FakeConnection()
        )

        self.error = error
        self.calls = []

    def __call__(
        self,
        *args,
        **kwargs,
    ):
        self.calls.append(
            (
                args,
                kwargs,
            )
        )

        if self.error is not None:
            raise self.error

        return self.result


def _load_provider(
    monkeypatch,
    *,
    connect=None,
):
    assert MODULE_PATH.is_file(), (
        "Debe existir "
        "src/persistence/azure_sql/"
        "connection_provider.py"
    )

    if connect is None:
        connect = ConnectRecorder()

    fake_driver = types.ModuleType(
        "mssql_python"
    )

    fake_driver.connect = connect

    monkeypatch.setitem(
        sys.modules,
        "mssql_python",
        fake_driver,
    )

    sys.modules.pop(
        MODULE_NAME,
        None,
    )

    module = importlib.import_module(
        MODULE_NAME
    )

    return (
        module,
        connect,
    )


def _settings_type(
    module,
):
    settings_type = getattr(
        module,
        "AzureSqlManagedIdentitySettings",
        None,
    )

    assert inspect.isclass(
        settings_type
    )

    return settings_type


def _build_connection_string(
    module,
):
    builder = getattr(
        module,
        "build_azure_sql_connection_string",
        None,
    )

    assert callable(
        builder
    )

    return builder


def _build_factory(
    module,
):
    builder = getattr(
        module,
        "build_mssql_python_connection_factory",
        None,
    )

    assert callable(
        builder
    )

    return builder


def test_provider_surface_and_frozen_structured_settings(
    monkeypatch,
):
    module, _ = _load_provider(
        monkeypatch
    )

    settings_type = _settings_type(
        module
    )

    assert is_dataclass(
        settings_type
    )

    assert [
        item.name
        for item in fields(
            settings_type
        )
    ] == [
        "server",
        "database",
        "managed_identity_client_id",
    ]

    settings = settings_type(
        server=SERVER,
        database=DATABASE,
    )

    with pytest.raises(
        FrozenInstanceError
    ):
        settings.server = "other"


def test_system_assigned_connection_string_is_passwordless_and_fixed(
    monkeypatch,
):
    module, _ = _load_provider(
        monkeypatch
    )

    settings_type = _settings_type(
        module
    )

    builder = _build_connection_string(
        module
    )

    connection_string = builder(
        settings_type(
            server=SERVER,
            database=DATABASE,
        )
    )

    assert (
        f"Server={SERVER};"
        in connection_string
    )

    assert (
        f"Database={DATABASE};"
        in connection_string
    )

    assert (
        "Authentication=ActiveDirectoryMSI;"
        in connection_string
    )

    assert "Encrypt=yes;" in connection_string

    assert (
        "TrustServerCertificate=no;"
        in connection_string
    )

    assert "UID=" not in connection_string

    forbidden = (
        "PWD=",
        "Password=",
        "User ID=",
        "ActiveDirectoryDefault",
        "ActiveDirectoryPassword",
        "TrustServerCertificate=yes",
    )

    for token in forbidden:
        assert token not in connection_string


def test_user_assigned_connection_string_adds_only_managed_identity_uid(
    monkeypatch,
):
    module, _ = _load_provider(
        monkeypatch
    )

    settings_type = _settings_type(
        module
    )

    builder = _build_connection_string(
        module
    )

    connection_string = builder(
        settings_type(
            server=SERVER,
            database=DATABASE,
            managed_identity_client_id=(
                MANAGED_IDENTITY_CLIENT_ID
            ),
        )
    )

    assert (
        "Authentication=ActiveDirectoryMSI;"
        in connection_string
    )

    assert (
        "UID="
        + MANAGED_IDENTITY_CLIENT_ID
        + ";"
        in connection_string
    )

    assert "PWD=" not in connection_string
    assert "Password=" not in connection_string


@pytest.mark.parametrize(
    (
        "field_name",
        "value",
    ),
    [
        (
            "server",
            "",
        ),
        (
            "server",
            " bad.database.windows.net",
        ),
        (
            "server",
            "sql.example.com",
        ),
        (
            "server",
            "sql.database.windows.net;"
            "Authentication=SqlPassword",
        ),
        (
            "database",
            "",
        ),
        (
            "database",
            " bad ",
        ),
        (
            "database",
            "db;Encrypt=no",
        ),
        (
            "managed_identity_client_id",
            "not-a-guid",
        ),
    ],
)
def test_structured_settings_reject_connection_string_injection(
    monkeypatch,
    field_name,
    value,
):
    module, _ = _load_provider(
        monkeypatch
    )

    settings_type = _settings_type(
        module
    )

    kwargs = {
        "server": SERVER,
        "database": DATABASE,
    }

    kwargs[
        field_name
    ] = value

    with pytest.raises(
        ValueError
    ):
        settings_type(
            **kwargs
        )


def test_connection_factory_calls_mssql_python_with_autocommit_false(
    monkeypatch,
):
    recorder = ConnectRecorder()

    module, recorder = _load_provider(
        monkeypatch,
        connect=recorder,
    )

    settings_type = _settings_type(
        module
    )

    builder = _build_factory(
        module
    )

    factory = builder(
        settings_type(
            server=SERVER,
            database=DATABASE,
        )
    )

    assert callable(
        factory
    )

    result = factory()

    assert result is recorder.result

    assert len(
        recorder.calls
    ) == 1

    args, kwargs = (
        recorder.calls[0]
    )

    assert len(args) == 1

    connection_string = (
        args[0]
    )

    assert (
        "Authentication=ActiveDirectoryMSI;"
        in connection_string
    )

    assert kwargs == {
        "autocommit": False
    }


def test_connection_factory_creates_fresh_connection_per_call(
    monkeypatch,
):
    recorder = ConnectRecorder()

    module, recorder = _load_provider(
        monkeypatch,
        connect=recorder,
    )

    settings_type = _settings_type(
        module
    )

    factory = _build_factory(
        module
    )(
        settings_type(
            server=SERVER,
            database=DATABASE,
        )
    )

    factory()
    factory()

    assert len(
        recorder.calls
    ) == 2


def test_driver_connection_failure_propagates_unchanged(
    monkeypatch,
):
    expected_error = RuntimeError(
        "mssql connection failed"
    )

    recorder = ConnectRecorder(
        error=expected_error
    )

    module, _ = _load_provider(
        monkeypatch,
        connect=recorder,
    )

    settings_type = _settings_type(
        module
    )

    factory = _build_factory(
        module
    )(
        settings_type(
            server=SERVER,
            database=DATABASE,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="mssql connection failed",
    ) as exc_info:
        factory()

    assert (
        exc_info.value
        is expected_error
    )


def test_provider_does_not_read_environment_or_use_azure_identity(
    monkeypatch,
):
    _load_provider(
        monkeypatch
    )

    source = MODULE_PATH.read_text(
        encoding="utf-8"
    )

    lower_source = source.lower()

    forbidden = (
        "defaultazurecredential",
        "managedidentitycredential",
        "azure.identity",
        "activeDirectoryDefault".lower(),
        "os.getenv",
        "os.environ",
        "getenv(",
    )

    for token in forbidden:
        assert token.lower() not in lower_source


def test_provider_imports_mssql_python_and_no_password_auth_surface(
    monkeypatch,
):
    _load_provider(
        monkeypatch
    )

    source = MODULE_PATH.read_text(
        encoding="utf-8"
    )

    lower_source = source.lower()

    assert (
        "import mssql_python"
        in lower_source
    )

    forbidden = (
        "sqlpassword",
        "activedirectorypassword",
        "pwd=",
        "password=",
        "trustservercertificate=yes",
    )

    for token in forbidden:
        assert token not in lower_source


def test_public_provider_has_no_arbitrary_connection_string_parameter(
    monkeypatch,
):
    module, _ = _load_provider(
        monkeypatch
    )

    settings_type = _settings_type(
        module
    )

    settings_fields = {
        item.name
        for item in fields(
            settings_type
        )
    }

    assert settings_fields == {
        "server",
        "database",
        "managed_identity_client_id",
    }

    builder = _build_factory(
        module
    )

    signature = inspect.signature(
        builder
    )

    assert (
        "connection_string"
        not in signature.parameters
    )

    assert (
        "connection_str"
        not in signature.parameters
    )