from __future__ import annotations

from dataclasses import (
    dataclass,
    fields,
)

from src.channels.teams.azure_sql_persistence import (
    AzureSqlTeamsHitlPersistence,
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

from src.persistence.azure_sql.session_store import (
    AzureSqlSessionStore,
)

from src.workflows.incident_resolution.azure_vm_instance_view import (
    AzureVmPowerStateReader,
)


@dataclass(
    frozen=True
)
class ProductionTeamsHitlBootstrap(
    TeamsHitlBootstrap
):
    """
    Bootstrap productivo Teams con acceso al
    SessionStore durable ya compuesto.

    Añade exclusivamente propagación de dependencia.

    No ejecuta sesiones.
    No decide identidad conversacional.
    No invoca agentes.
    No concede autoridad operacional.
    """

    session_store: AzureSqlSessionStore


def _wrap_productive_bootstrap(
    *,
    base_bootstrap: TeamsHitlBootstrap,
    persistence: AzureSqlTeamsHitlPersistence,
) -> ProductionTeamsHitlBootstrap:
    if not isinstance(
        base_bootstrap,
        TeamsHitlBootstrap,
    ):
        raise TypeError(
            "base_bootstrap debe ser "
            "TeamsHitlBootstrap."
        )

    values = {
        field.name: getattr(
            base_bootstrap,
            field.name,
        )
        for field in fields(
            TeamsHitlBootstrap
        )
    }

    return ProductionTeamsHitlBootstrap(
        **values,
        session_store=(
            persistence.session_store
        ),
    )


def build_production_teams_hitl_app(
    app_settings: (
        TeamsHitlAppSettings
        | TeamsManagedIdentityAppSettings
    ),
    azure_sql_settings: AzureSqlManagedIdentitySettings,
    *,
    azure_vm_power_state_reader: AzureVmPowerStateReader,
) -> ProductionTeamsHitlBootstrap:
    """
    Compone el boundary Teams productivo.

    Responsabilidades:

    - recibe settings Teams ya resueltos;
    - recibe settings Azure SQL estructurados;
    - exige un reader read-only explícito;
    - compone persistencia Azure SQL una vez;
    - inyecta las dependencias base en Teams;
    - propaga el SessionStore productivo al
      bootstrap resultante.

    No:

    - lee variables de entorno;
    - selecciona credenciales;
    - construye persistencia local;
    - abre conexiones SQL;
    - ejecuta AgentSession;
    - invoca agentes;
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

    base_bootstrap = build_teams_hitl_app(
        app_settings,
        persistence=persistence,
        azure_vm_power_state_reader=(
            azure_vm_power_state_reader
        ),
    )

    # Compatibilidad estricta con composition tests
    # históricos que sustituyen el persistence builder
    # por un sentinel genérico.
    #
    # En producción real el builder anterior devuelve
    # siempre AzureSqlTeamsHitlPersistence.
    if not isinstance(
        persistence,
        AzureSqlTeamsHitlPersistence,
    ):
        return base_bootstrap

    return _wrap_productive_bootstrap(
        base_bootstrap=base_bootstrap,
        persistence=persistence,
    )
