from __future__ import annotations

import json

from collections.abc import Mapping
from dataclasses import dataclass

from src.channels.teams.authorization_identity_resolver import (
    ExactTeamsAuthorizationIdentityMapping,
)

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
    authorization_identity_mappings: tuple[
        ExactTeamsAuthorizationIdentityMapping,
        ...,
    ] = ()


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


def _parse_authorization_identity_mappings(
    *,
    environment: Mapping,
    source_tenant_id: str,
    target_tenant_id: str,
) -> tuple[
    ExactTeamsAuthorizationIdentityMapping,
    ...,
]:
    name = (
        "TEAMS_AUTHORIZATION_IDENTITY_MAPPINGS_JSON"
    )

    raw = _optional_value(
        environment=environment,
        name=name,
    )

    cross_tenant = (
        source_tenant_id
        != target_tenant_id
    )

    if raw is None:
        if cross_tenant:
            raise TeamsProductionHostConfigurationError(
                f"{name} es obligatorio cuando "
                "el directorio de autorización "
                "es distinto del tenant Teams."
            )

        return ()

    try:
        payload = json.loads(
            raw
        )
    except Exception:
        raise TeamsProductionHostConfigurationError(
            f"{name} debe contener JSON válido."
        ) from None

    if not isinstance(
        payload,
        list,
    ):
        raise TeamsProductionHostConfigurationError(
            f"{name} debe contener una lista JSON."
        )

    expected_keys = {
        "sourceTenantId",
        "sourceUserObjectId",
        "targetTenantId",
        "targetUserObjectId",
    }

    mappings = []

    for item in payload:
        if (
            not isinstance(
                item,
                dict,
            )
            or set(item) != expected_keys
        ):
            raise TeamsProductionHostConfigurationError(
                f"{name} contiene una entrada inválida."
            )

        try:
            mapping = (
                ExactTeamsAuthorizationIdentityMapping(
                    source_tenant_id=(
                        item[
                            "sourceTenantId"
                        ]
                    ),
                    source_user_object_id=(
                        item[
                            "sourceUserObjectId"
                        ]
                    ),
                    target_tenant_id=(
                        item[
                            "targetTenantId"
                        ]
                    ),
                    target_user_object_id=(
                        item[
                            "targetUserObjectId"
                        ]
                    ),
                )
            )
        except Exception:
            raise TeamsProductionHostConfigurationError(
                f"{name} contiene una correlación inválida."
            ) from None

        if (
            mapping.source_tenant_id
            != source_tenant_id
        ):
            raise TeamsProductionHostConfigurationError(
                f"{name} contiene un source tenant "
                "fuera de la autoridad configurada."
            )

        if (
            mapping.target_tenant_id
            != target_tenant_id
        ):
            raise TeamsProductionHostConfigurationError(
                f"{name} contiene un target tenant "
                "fuera de la autoridad configurada."
            )

        mappings.append(
            mapping
        )

    if (
        cross_tenant
        and not mappings
    ):
        raise TeamsProductionHostConfigurationError(
            f"{name} no puede estar vacío "
            "en autorización cross-tenant."
        )

    keys = [
        (
            mapping.source_tenant_id,
            mapping.source_user_object_id,
            mapping.target_tenant_id,
        )
        for mapping in mappings
    ]

    if len(keys) != len(set(keys)):
        raise TeamsProductionHostConfigurationError(
            f"{name} contiene correlaciones duplicadas."
        )

    return tuple(
        mappings
    )


def build_production_teams_host_settings(
    environment,
) -> TeamsProductionHostSettings:
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

    teams_channel_tenant_id = _required_value(
        environment=environment,
        name="TEAMS_CHANNEL_TENANT_ID",
    )

    authorization_directory_tenant_id = (
        _optional_value(
            environment=environment,
            name=(
                "TEAMS_AUTHORIZATION_DIRECTORY_TENANT_ID"
            ),
        )
    )

    if authorization_directory_tenant_id is None:
        authorization_directory_tenant_id = (
            teams_channel_tenant_id
        )

    authorization_identity_mappings = (
        _parse_authorization_identity_mappings(
            environment=environment,
            source_tenant_id=(
                teams_channel_tenant_id
            ),
            target_tenant_id=(
                authorization_directory_tenant_id
            ),
        )
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
        teams_channel_tenant_id=(
            teams_channel_tenant_id
        ),
        authorized_technicians_group_object_id=_required_value(
            environment=environment,
            name="TEAMS_AUTHORIZED_TECHNICIANS_GROUP_OBJECT_ID",
        ),
        authorization_directory_tenant_id=(
            authorization_directory_tenant_id
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
        authorization_identity_mappings=(
            authorization_identity_mappings
        ),
    )
