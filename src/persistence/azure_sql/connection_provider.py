from __future__ import annotations

from collections.abc import (
    Callable,
)

from dataclasses import (
    dataclass,
)

import re

from typing import (
    Any,
)

from uuid import (
    UUID,
)

import mssql_python


ConnectionFactory = Callable[
    [],
    Any,
]


_AZURE_SQL_FQDN_SUFFIX = (
    ".database.windows.net"
)


_DNS_NAME = re.compile(
    r"^[A-Za-z0-9]"
    r"(?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\."
    r"[A-Za-z0-9]"
    r"(?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r")*$"
)


def _require_exact_string(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
        or not value.strip()
        or value != value.strip()
    ):
        raise ValueError(
            f"{name} debe ser un string "
            "exacto no vacio."
        )

    return value


def _validate_server(
    value: object,
) -> str:
    server = _require_exact_string(
        name="server",
        value=value,
    )

    if len(server) > 253:
        raise ValueError(
            "server excede longitud DNS."
        )

    if (
        ";" in server
        or "\r" in server
        or "\n" in server
        or "\x00" in server
    ):
        raise ValueError(
            "server contiene caracteres "
            "no permitidos."
        )

    if not _DNS_NAME.fullmatch(
        server
    ):
        raise ValueError(
            "server no es un FQDN valido."
        )

    if not server.lower().endswith(
        _AZURE_SQL_FQDN_SUFFIX
    ):
        raise ValueError(
            "server debe pertenecer a "
            "database.windows.net."
        )

    prefix = server[
        :-len(
            _AZURE_SQL_FQDN_SUFFIX
        )
    ]

    if not prefix:
        raise ValueError(
            "server Azure SQL incompleto."
        )

    return server


def _validate_database(
    value: object,
) -> str:
    database = _require_exact_string(
        name="database",
        value=value,
    )

    if len(database) > 128:
        raise ValueError(
            "database excede 128 caracteres."
        )

    if (
        ";" in database
        or "\r" in database
        or "\n" in database
        or "\x00" in database
    ):
        raise ValueError(
            "database contiene caracteres "
            "no permitidos."
        )

    return database


def _validate_managed_identity_client_id(
    value: object,
) -> str | None:
    if value is None:
        return None

    client_id = _require_exact_string(
        name="managed_identity_client_id",
        value=value,
    )

    if (
        ";" in client_id
        or "\r" in client_id
        or "\n" in client_id
        or "\x00" in client_id
    ):
        raise ValueError(
            "managed_identity_client_id "
            "contiene caracteres no permitidos."
        )

    try:
        parsed = UUID(
            client_id
        )

    except (
        TypeError,
        ValueError,
        AttributeError,
    ) as error:
        raise ValueError(
            "managed_identity_client_id "
            "debe ser un UUID valido."
        ) from error

    if (
        str(
            parsed
        )
        != client_id.lower()
    ):
        raise ValueError(
            "managed_identity_client_id "
            "debe usar formato UUID canonico."
        )

    return client_id


@dataclass(
    frozen=True
)
class AzureSqlManagedIdentitySettings:
    server: str

    database: str

    managed_identity_client_id: (
        str | None
    ) = None

    def __post_init__(
        self,
    ) -> None:
        _validate_server(
            self.server
        )

        _validate_database(
            self.database
        )

        _validate_managed_identity_client_id(
            self.managed_identity_client_id
        )


def build_azure_sql_connection_string(
    settings: AzureSqlManagedIdentitySettings,
) -> str:
    if not isinstance(
        settings,
        AzureSqlManagedIdentitySettings,
    ):
        raise TypeError(
            "settings debe ser "
            "AzureSqlManagedIdentitySettings."
        )

    parts = [
        "Server="
        + settings.server,
        "Database="
        + settings.database,
        "Authentication="
        "ActiveDirectoryMSI",
    ]

    if (
        settings
        .managed_identity_client_id
        is not None
    ):
        parts.append(
            "UID="
            + settings
            .managed_identity_client_id
        )

    parts.extend(
        [
            "Encrypt=yes",
            "TrustServerCertificate=no",
        ]
    )

    return (
        ";".join(
            parts
        )
        + ";"
    )


def build_mssql_python_connection_factory(
    settings: AzureSqlManagedIdentitySettings,
) -> ConnectionFactory:
    if not isinstance(
        settings,
        AzureSqlManagedIdentitySettings,
    ):
        raise TypeError(
            "settings debe ser "
            "AzureSqlManagedIdentitySettings."
        )

    hardened_connection_string = (
        build_azure_sql_connection_string(
            settings
        )
    )

    def connection_factory():
        return mssql_python.connect(
            hardened_connection_string,
            autocommit=False,
        )

    return connection_factory