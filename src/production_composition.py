from __future__ import annotations

from collections.abc import Mapping

from src.agents.production_communication_runner import (
    build_foundry_production_communication_runner,
    build_foundry_production_agents,
)

from src.agents.production_settings import (
    build_foundry_production_settings,
)

from src.channels.teams.production_composition import (
    build_production_teams_host_with_communication,
    build_production_teams_host_with_communication_and_incident_agents,
)


def build_production_application(
    environment,
):
    if not isinstance(
        environment,
        Mapping,
    ):
        raise TypeError(
            "environment debe implementar Mapping."
        )

    foundry_settings = (
        build_foundry_production_settings(
            environment
        )
    )

    incident_agents = (
        build_foundry_production_agents(
            foundry_settings
        )
    )

    communication_runner = getattr(
        incident_agents,
        "run_communication",
        None,
    )

    if not callable(
        communication_runner
    ):
        raise TypeError(
            "incident_agents debe exponer "
            "run_communication callable."
        )

    return (
        build_production_teams_host_with_communication_and_incident_agents(
            environment,
            communication_runner=(
                communication_runner
            ),
            incident_agents=(
                incident_agents
            ),
        )
    )
