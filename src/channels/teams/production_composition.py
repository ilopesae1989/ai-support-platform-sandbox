from __future__ import annotations

from collections.abc import Mapping

from src.channels.teams.production_bootstrap import (
    build_production_teams_hitl_app,
)

from src.channels.teams.production_settings import (
    build_production_teams_host_settings,
)

from src.workflows.incident_resolution.azure_vm_observation_reader import (
    build_azure_vm_observation_reader,
)

from src.workflows.incident_resolution.azure_vm_observation_settings import (
    build_azure_vm_observation_settings,
)


def build_production_teams_host(
    environment,
):
    if not isinstance(
        environment,
        Mapping,
    ):
        raise TypeError(
            "environment debe implementar Mapping."
        )

    host_settings = (
        build_production_teams_host_settings(
            environment
        )
    )

    observation_settings = (
        build_azure_vm_observation_settings(
            environment
        )
    )

    reader = (
        build_azure_vm_observation_reader(
            observation_settings
        )
    )

    return build_production_teams_hitl_app(
        host_settings.app_settings,
        host_settings.azure_sql_settings,
        azure_vm_power_state_reader=reader,
    )
