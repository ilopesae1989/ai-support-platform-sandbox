from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from src.channels.teams.bootstrap import (
    TeamsManagedIdentityAppSettings,
)

from src.persistence.azure_sql.connection_provider import (
    AzureSqlManagedIdentitySettings,
)


class TeamsProductionHostConfigurationError(
    ValueError
):
    pass


@dataclass(
    frozen=True
)
class TeamsProductionHostSettings:
    app_settings: TeamsManagedIdentityAppSettings
    azure_sql_settings: AzureSqlManagedIdentitySettings


def _required_value(
    *,
    environment: Mapping,
    name: str,
) -> str:
    value = environment.get(
        name
    )

    if (
        not isinstance(
            value,
            str,
        )
        or not value
        or not value.strip()
        or value != value.strip()
    ):
        raise TeamsProductionHostConfigurationError(
            f"{name} debe existir y contener "
            "un valor exacto no vacío."
        )

    return value


def _optional_value(
    *,
    environment: Mapping,
    name: str,
) -> str | None:
    if name not in environment:
        return None

    value = environment[
        name
    ]

    if (
        not isinstance(
            value,
            str,
        )
        or not value
        or not value.strip()
        or value != value.strip()
    ):
        raise TeamsProductionHostConfigurationError(
            f"{name}, cuando existe, debe "
            "contener un valor exacto no vacío."
        )

    return value


def build_production_teams_host_settings(
    environment,
) -> TeamsProductionHostSettings:
    """
    Convierte un mapping explícito recibido por el
    caller en configuración productiva tipada.

    No lee configuración global.
    No selecciona credenciales.
    No abre conexiones.
    No compone persistencia.
    No arranca runtime.
    """
    if not isinstance(
        environment,
        Mapping,
    ):
        raise TypeError(
            "environment debe implementar Mapping."
        )

    if "CLIENT_SECRET" in environment:
        raise TeamsProductionHostConfigurationError(
            "CLIENT_SECRET está prohibido "
            "en el host productivo."
        )

    app_settings = TeamsManagedIdentityAppSettings(
        client_id=_required_value(
            environment=environment,
            name="CLIENT_ID",
        ),
        managed_identity_client_id=_required_value(
            environment=environment,
            name="MANAGED_IDENTITY_CLIENT_ID",
        ),
        bot_tenant_id=_required_value(
            environment=environment,
            name="TENANT_ID",
        ),
        teams_channel_tenant_id=_required_value(
            environment=environment,
            name="TEAMS_CHANNEL_TENANT_ID",
        ),
        approver_aad_object_id=_required_value(
            environment=environment,
            name="TEAMS_HITL_APPROVER_AAD_OBJECT_ID",
        ),
    )

    azure_sql_settings = AzureSqlManagedIdentitySettings(
        server=_required_value(
            environment=environment,
            name="AZURE_SQL_SERVER",
        ),
        database=_required_value(
            environment=environment,
            name="AZURE_SQL_DATABASE",
        ),
        managed_identity_client_id=_optional_value(
            environment=environment,
            name="AZURE_SQL_MANAGED_IDENTITY_CLIENT_ID",
        ),
    )

    return TeamsProductionHostSettings(
        app_settings=app_settings,
        azure_sql_settings=azure_sql_settings,
    )
