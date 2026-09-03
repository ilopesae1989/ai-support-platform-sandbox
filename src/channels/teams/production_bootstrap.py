from __future__ import annotations

from src.channels.teams.azure_sql_persistence import (
    build_azure_sql_teams_hitl_persistence,
)

from src.channels.teams.bootstrap import (
    TeamsHitlAppSettings,
    TeamsHitlBootstrap,
    TeamsManagedIdentityAppSettings,
    build_teams_hitl_app,
)

from src.persistence.azure_sql.connection_provider import (
    AzureSqlManagedIdentitySettings,
)

from src.workflows.incident_resolution.azure_vm_instance_view import (
    AzureVmPowerStateReader,
)


def build_production_teams_hitl_app(
    app_settings: (
        TeamsHitlAppSettings
        | TeamsManagedIdentityAppSettings
    ),
    azure_sql_settings: AzureSqlManagedIdentitySettings,
    *,
    azure_vm_power_state_reader: AzureVmPowerStateReader,
) -> TeamsHitlBootstrap:
    """
    Compone el boundary Teams productivo.

    Responsabilidades:

    - recibe settings Teams ya resueltos;
    - recibe settings Azure SQL estructurados;
    - exige un reader read-only explícito;
    - compone persistencia Azure SQL una vez;
    - inyecta todas las dependencias en Teams.

    No:

    - lee variables de entorno;
    - selecciona credenciales;
    - construye persistencia local;
    - abre conexiones SQL;
    - llama Azure;
    - arranca Teams.
    """
    if not isinstance(
        app_settings,
        (
            TeamsHitlAppSettings,
            TeamsManagedIdentityAppSettings,
        ),
    ):
        raise TypeError(
            "app_settings debe ser "
            "TeamsHitlAppSettings o "
            "TeamsManagedIdentityAppSettings."
        )

    if not isinstance(
        azure_sql_settings,
        AzureSqlManagedIdentitySettings,
    ):
        raise TypeError(
            "azure_sql_settings debe ser "
            "AzureSqlManagedIdentitySettings."
        )

    read_power_state = getattr(
        azure_vm_power_state_reader,
        "read_power_state",
        None,
    )

    if not callable(
        read_power_state
    ):
        raise TypeError(
            "azure_vm_power_state_reader debe "
            "implementar read_power_state()."
        )

    persistence = (
        build_azure_sql_teams_hitl_persistence(
            azure_sql_settings
        )
    )

    return build_teams_hitl_app(
        app_settings,
        persistence=persistence,
        azure_vm_power_state_reader=(
            azure_vm_power_state_reader
        ),
    )
